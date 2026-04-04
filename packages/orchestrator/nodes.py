"""
LangGraph 节点：Planner + 复用 legacy execute_workflow + 轻量校验。
后续 Phase 可将 monolithic pipeline 拆成 retriever / cleaner / section_generator 等独立节点。
"""
from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable

from packages.orchestrator.prompts import (
    CLASSIFIER_FEW_SHOT_EXAMPLES,
    CLASSIFIER_LLM_SYSTEM_PROMPT,
    MEDIA_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
)
from packages.orchestrator.state import ReportState
from packages.orchestrator.workflow import (
    WorkflowState,
    execute_workflow,
    plan_sources,
    crawl_sources,
    clean_documents,
    deduplicate_documents,
    classify_documents,
    generate_sections,
    generate_citations,
    generate_charts,
    assemble_report,
)

logger = logging.getLogger(__name__)

PersistFn = Callable[[WorkflowState], None]

persist_fn_var: ContextVar[PersistFn | None] = ContextVar("report_agent_persist_fn", default=None)


@contextmanager
def with_persist_fn(fn: PersistFn | None):
    token = persist_fn_var.set(fn)
    try:
        yield
    finally:
        persist_fn_var.reset(token)


def _call_llm_json(user_prompt: str, system_prompt: str | None = None) -> dict[str, Any] | None:
    model_name = os.getenv("LITELLM_MODEL", "").strip()
    api_key = os.getenv("LITELLM_API_KEY", "").strip()
    if not model_name or not api_key or api_key == "replace_me":
        return None
    try:
        from litellm import completion  # type: ignore

        resp = completion(
            model=model_name,
            api_key=api_key,
            base_url=os.getenv("LITELLM_BASE_URL") or None,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt or f"{MEDIA_SYSTEM_PROMPT}\n{PLANNER_SYSTEM_PROMPT}",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=800,
            timeout=45,
        )
        raw = (resp.choices[0].message.content or "").strip()  # type: ignore[index]
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("planner_llm_failed: %s", exc)
        return None


def _call_groundedness_llm_json(user_prompt: str) -> dict[str, Any] | None:
    model_name = os.getenv("MOONSHOT_GROUNDED_MODEL", "").strip() or os.getenv("LITELLM_MODEL", "").strip()
    api_key = os.getenv("LITELLM_API_KEY", "").strip()
    if not model_name or not api_key or api_key == "replace_me":
        return None
    try:
        from litellm import completion  # type: ignore

        resp = completion(
            model=model_name,
            api_key=api_key,
            base_url=os.getenv("LITELLM_BASE_URL") or None,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 Groundedness 审查器。请判断回答是否忠实于证据片段。"
                        "只输出 JSON：{\"grounded_score\":0~1,\"needs_human\":bool,\"reason\":\"...\"}。"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=300,
            timeout=45,
        )
        raw = (resp.choices[0].message.content or "").strip()  # type: ignore[index]
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("groundedness_llm_failed: %s", exc)
        return None


def _heuristic_keywords(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return ["AI", "媒体", "AIGC"]
    parts = re.split(r"[,，、;；\s]+", q)
    kws = [p.strip() for p in parts if len(p.strip()) >= 2][:12]
    if len(kws) < 3:
        kws.extend(["人工智能", "传媒", "技术趋势"])
    return list(dict.fromkeys(kws))[:12]


def _default_sources() -> list[str]:
    raw = os.getenv("AGENT_DEFAULT_SOURCES", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data if x]
        except json.JSONDecodeError:
            pass
    return [
        "https://arstechnica.com/",
        "https://www.anthropic.com/news/announcing-our-updated-responsible-scaling-policy",
    ]


def _infer_need_internal_kb(query: str) -> bool:
    """
    Phase 3：根据用户 query 智能判断是否需要内部知识库（混合 RAG）。
    验收规则：query 带“结合我们内部宣传要点”时必须为 True。
    """
    q = (query or "").strip()
    if not q:
        return False

    flags = [
        "内部宣传要点",
        "内部宣传",
        "我们内部",
        "结合我们内部",
        "内部要点",
        "内部材料",
        "内部文档",
        "知识库",
        "宣教要点",
        "宣传要点",
    ]
    return any(flag in q for flag in flags)


def _token_overlap_score(query: str, text: str) -> float:
    q_tokens = set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{2,}", (query or "").lower()))
    t_tokens = set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{2,}", (text or "").lower()))
    if not q_tokens or not t_tokens:
        return 0.0
    inter = len(q_tokens.intersection(t_tokens))
    return inter / max(len(q_tokens), 1)


def planner_node(state: ReportState) -> dict[str, Any]:
    """根据 query 生成 plan，并写回 keywords / whitelist（后续可接结构化输出）。"""
    query = state.get("query") or ""
    need_internal_kb = _infer_need_internal_kb(query)
    plan: dict[str, Any] = {
        "strategy": "crawl_then_legacy_pipeline",
        "keywords": _heuristic_keywords(query),
        "report_focus": query[:200] or "媒体行业 AI 动态",
        "need_kb": True,
        "need_internal_kb": need_internal_kb,
    }
    llm_plan = _call_llm_json(f"用户需求：\n{query}\n请输出规划 JSON。")
    if llm_plan and isinstance(llm_plan, dict):
        if isinstance(llm_plan.get("keywords"), list):
            merged = [str(x) for x in llm_plan["keywords"] if str(x).strip()]
            if merged:
                plan["keywords"] = merged[:12]
        if llm_plan.get("report_focus"):
            plan["report_focus"] = str(llm_plan["report_focus"])[:500]
        ps = llm_plan.get("prefer_sources")
        if isinstance(ps, list) and ps:
            plan["prefer_sources"] = [str(x) for x in ps if str(x).strip().startswith("http")]
        else:
            plan["prefer_sources"] = []
    else:
        plan["prefer_sources"] = []

    keywords = plan["keywords"]
    whitelist = state.get("source_whitelist") or []
    if plan.get("prefer_sources"):
        whitelist = list(dict.fromkeys([*plan["prefer_sources"], *whitelist]))
    if not whitelist:
        whitelist = _default_sources()

    return {
        "plan": plan,
        "keywords": keywords,
        "source_whitelist": whitelist,
        "need_internal_kb": need_internal_kb,
        "status": "running",
        "status_message": "planner_done",
    }


def _to_workflow(state: ReportState) -> WorkflowState:
    writing_mode = str(os.getenv("REPORT_WRITING_MODE", "llm")).lower().strip()
    use_llm = state.get("use_llm_writing")
    if use_llm is None:
        use_llm = writing_mode != "rule"
    return WorkflowState(
        job_id=state["job_id"],
        organization_id=state["organization_id"],
        report_type=state.get("report_type") or "weekly",
        keywords=state.get("keywords") or [],
        time_range_start=state.get("time_range_start") or "",
        time_range_end=state.get("time_range_end") or "",
        source_whitelist=state.get("source_whitelist") or [],
        use_llm_writing=bool(use_llm),
        language=state.get("language") or "zh-CN",
        kb_chunks=state.get("kb_chunks") or [],
    )


def _from_workflow(ws: WorkflowState) -> dict[str, Any]:
    st = "completed" if ws.status == "success" else ("failed" if ws.status == "failed" else ws.status)
    return {
        "collected_docs": ws.documents,
        "cleaned_docs": ws.cleaned_documents,
        "deduplicated_docs": ws.deduplicated_documents,
        "section_map": ws.section_map,
        "sections": ws.section_markdown,
        "section_paragraphs": ws.section_paragraphs,
        "citations": ws.citations,
        "citation_metrics": ws.citation_metrics,
        "charts": ws.charts,
        "markdown": ws.markdown,
        "final_report": ws.markdown,
        "stats": ws.stats,
        "errors": list(ws.errors),
        "status": st,
        "status_message": ws.status_message,
    }


def legacy_pipeline_node(state: ReportState) -> dict[str, Any]:
    """
    Phase 1：整段调用 execute_workflow，等价于原固定流水线，便于稳定交付；
    Phase 2+：拆分为 retriever / cleaner / section_generator 等节点并加条件边。
    """
    persist_fn = persist_fn_var.get()
    ws = _to_workflow(state)
    final = execute_workflow(ws, persist_fn=persist_fn)
    out = _from_workflow(final)
    if final.status != "success" and final.errors:
        out["needs_human"] = False
    return out


def _call_consistency_llm_json(user_prompt: str) -> dict[str, Any] | None:
    """调用 LLM 进行跨章节一致性校验。"""
    model_name = os.getenv("LITELLM_MODEL", "").strip()
    api_key = os.getenv("LITELLM_API_KEY", "").strip()
    if not model_name or not api_key or api_key == "replace_me":
        return None
    try:
        from litellm import completion
        resp = completion(
            model=model_name,
            api_key=api_key,
            base_url=os.getenv("LITELLM_BASE_URL") or None,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是报告一致性审查专家。请检查报告各章节之间是否存在逻辑矛盾、内容重复或观点不一致。\n"
                        "输出 JSON 格式：{\"consistency_score\": 0-1, \"has_contradiction\": bool, \"contradictions\": [{\"sections\": \"章节A vs 章节B\", \"issue\": \"具体问题\"}], \"repeated_content\": [{\"sections\": \"章节A vs 章节B\", \"description\": \"重复内容摘要\"}], \"suggestions\": [\"改进建议1\", \"改进建议2\"]}"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=800,
            timeout=45,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("consistency_llm_failed: %s", exc)
        return None


def validator_node(state: ReportState) -> dict[str, Any]:
    """企业级校验：引用告警 + Groundedness 审查 + 跨章节一致性校验（Moonshot/LiteLLM）。"""
    metrics = state.get("citation_metrics") or {}
    warnings = metrics.get("warnings") if isinstance(metrics, dict) else None
    n_warn = len(warnings) if isinstance(warnings, list) else 0
    strict = os.getenv("AGENT_CITATION_WARN_THRESHOLD", "8").strip()
    try:
        threshold = int(strict)
    except ValueError:
        threshold = 8
    
    md = str(state.get("markdown") or state.get("final_report") or "")
    sections = state.get("sections", {})
    docs = state.get("deduplicated_docs") or state.get("cleaned_docs") or state.get("collected_docs") or []
    
    # 收集证据片段
    evidence_lines: list[str] = []
    for idx, d in enumerate(docs[:8], start=1):
        snippet = str(d.get("cleaned_text") or d.get("raw_text") or "").strip()[:260]
        src = str(d.get("source_url") or d.get("url") or d.get("source_name") or "")
        if snippet:
            evidence_lines.append(f"[{idx}] {snippet} (source={src})")
    
    # Groundedness 检查
    grounded_score = 0.72
    grounded_reason = ""
    llm_judge = _call_groundedness_llm_json(
        "请评估以下回答与证据的一致性。\n"
        f"回答:\n{md[:2800]}\n\n"
        f"证据:\n{chr(10).join(evidence_lines) if evidence_lines else '无可用证据'}"
    )
    if isinstance(llm_judge, dict):
        try:
            grounded_score = float(llm_judge.get("grounded_score", grounded_score))
        except Exception:
            pass
        grounded_score = max(0.0, min(1.0, grounded_score))
        grounded_reason = str(llm_judge.get("reason") or "")
    else:
        if md and evidence_lines:
            cite_markers = len(re.findall(r"\[\d+\]|\(source[:：]", md, flags=re.IGNORECASE))
            grounded_score = min(0.9, 0.45 + 0.05 * cite_markers)
        grounded_reason = "groundedness_fallback_heuristic"

    # 跨章节一致性校验
    consistency_score = 0.85
    has_contradiction = False
    contradictions: list[dict[str, str]] = []
    repeated_content: list[dict[str, str]] = []
    consistency_suggestions: list[str] = []
    
    if sections and len(sections) >= 2:
        # 构建章节内容摘要用于一致性检查
        section_summaries = []
        for sec_name, sec_content in sections.items():
            if sec_content:
                summary = f"【{sec_name}】\n{sec_content[:500]}..."
                section_summaries.append(summary)
        
        if section_summaries:
            consistency_prompt = (
                "请检查以下报告章节之间的一致性：\n\n"
                + "\n\n".join(section_summaries[:6])  # 最多检查6个章节
                + "\n\n请检查：\n1. 各章节观点是否存在矛盾\n2. 是否存在内容重复\n3. 逻辑是否连贯"
            )
            
            consistency_result = _call_consistency_llm_json(consistency_prompt)
            if isinstance(consistency_result, dict):
                try:
                    consistency_score = float(consistency_result.get("consistency_score", 0.85))
                    consistency_score = max(0.0, min(1.0, consistency_score))
                except Exception:
                    pass
                has_contradiction = bool(consistency_result.get("has_contradiction", False))
                contradictions = consistency_result.get("contradictions", []) or []
                repeated_content = consistency_result.get("repeated_content", []) or []
                consistency_suggestions = consistency_result.get("suggestions", []) or []
            else:
                # Fallback: 简单检查重复段落
                consistency_score = _heuristic_consistency_check(sections)

    grounded_threshold = float(os.getenv("AGENT_GROUNDED_SCORE_THRESHOLD", "0.62"))
    consistency_threshold = float(os.getenv("AGENT_CONSISTENCY_THRESHOLD", "0.70"))
    
    needs_human_by_ground = grounded_score < grounded_threshold
    needs_human_by_consistency = consistency_score < consistency_threshold or has_contradiction

    if state.get("status") == "failed":
        return {
            "needs_human": True,
            "human_reason": "流水线失败：" + "; ".join((state.get("errors") or [])[:3]),
            "status": "failed",
            "status_message": "validator_failed_pipeline",
            "grounded_score": grounded_score,
            "consistency_score": consistency_score,
            "has_contradiction": has_contradiction,
        }
    
    if n_warn >= threshold or needs_human_by_ground or needs_human_by_consistency:
        reason_parts: list[str] = []
        if n_warn >= threshold:
            reason_parts.append(f"引用校验告警过多（{n_warn}）")
        if needs_human_by_ground:
            reason_parts.append(f"Groundedness 较低（{grounded_score:.2f}）")
        if needs_human_by_consistency:
            if has_contradiction:
                reason_parts.append(f"检测到章节间矛盾（一致性得分: {consistency_score:.2f}）")
            else:
                reason_parts.append(f"章节一致性较低（{consistency_score:.2f}）")
        if contradictions:
            reason_parts.append(f"发现 {len(contradictions)} 处矛盾")
        if repeated_content:
            reason_parts.append(f"发现 {len(repeated_content)} 处重复内容")
        if grounded_reason:
            reason_parts.append(grounded_reason[:100])
        if consistency_suggestions:
            reason_parts.append("建议：" + consistency_suggestions[0][:80])
            
        return {
            "needs_human": True,
            "human_reason": "；".join(reason_parts) + "，建议人工复核。",
            "status": "needs_human",
            "status_message": "validator_needs_human",
            "grounded_score": grounded_score,
            "consistency_score": consistency_score,
            "has_contradiction": has_contradiction,
            "contradictions": contradictions[:5],  # 最多返回5个
            "repeated_content": repeated_content[:3],  # 最多返回3个
            "consistency_suggestions": consistency_suggestions[:3],
        }
    
    return {
        "needs_human": False,
        "human_reason": "",
        "status": state.get("status") or "completed",
        "status_message": state.get("status_message") or "validator_ok",
        "grounded_score": grounded_score,
        "consistency_score": consistency_score,
        "has_contradiction": False,
        "contradictions": [],
        "repeated_content": [],
        "consistency_suggestions": [],
    }


def _heuristic_consistency_check(sections: dict[str, str]) -> float:
    """启发式一致性检查（无 LLM 时的回退方案）。"""
    if not sections or len(sections) < 2:
        return 0.85
    
    section_names = list(sections.keys())
    section_texts = [sections[name] or "" for name in section_names]
    
    # 检查重复段落
    total_duplicates = 0
    for i, text1 in enumerate(section_texts):
        for j, text2 in enumerate(section_texts[i+1:], i+1):
            # 简单检查：如果两个章节有超过100字的相同内容
            if len(text1) > 100 and len(text2) > 100:
                # 提取前200字比较
                snippet1 = text1[:200]
                snippet2 = text2[:200]
                # 计算相似度（简单版本）
                words1 = set(snippet1.split())
                words2 = set(snippet2.split())
                if words1 and words2:
                    overlap = len(words1.intersection(words2))
                    similarity = overlap / max(len(words1), len(words2))
                    if similarity > 0.6:  # 60%相似度阈值
                        total_duplicates += 1
    
    # 根据重复数量扣分
    score = 0.85 - (total_duplicates * 0.1)
    return max(0.5, min(0.95, score))


def report_state_to_workflow(state: ReportState) -> WorkflowState:
    """将 LangGraph 的 ReportState 转成 legacy WorkflowState（给步骤函数/持久化使用）。"""
    return _to_workflow(state)


def build_workflow_state_for_persist(state: ReportState) -> WorkflowState:
    """
    Phase 2：节点只负责生成/渲染，不做落库；
    这里把 Graph 最终状态重建成 WorkflowState，然后由 agent_service 统一 persist。
    """
    ws = _to_workflow(state)

    ws.documents = state.get("collected_docs") or []
    ws.cleaned_documents = state.get("cleaned_docs") or []
    ws.deduplicated_documents = state.get("deduplicated_docs") or []
    ws.dedupe_meta = state.get("dedupe_meta") or {}
    ws.section_map = state.get("section_map") or {}
    ws.section_markdown = state.get("sections") or {}
    ws.section_paragraphs = state.get("section_paragraphs") or {}
    ws.citations = state.get("citations") or []
    ws.citation_metrics = state.get("citation_metrics") or {}
    ws.charts = state.get("charts") or []
    ws.structured_signals = state.get("structured_signals") or []

    ws.markdown = state.get("markdown") or state.get("final_report") or ""
    ws.stats = state.get("stats") or {}
    ws.errors = state.get("errors") or []
    ws.status_message = state.get("status_message") or "agent completed"

    if state.get("status") == "failed":
        ws.status = "failed"
    else:
        ws.status = "success"

    return ws


def _count_non_empty_text_items(docs: list[dict[str, Any]]) -> int:
    cnt = 0
    for d in docs:
        t = d.get("cleaned_text") or d.get("raw_text") or ""
        if len(str(t).strip()) >= 120:
            cnt += 1
    return cnt


def retriever_node(state: ReportState) -> dict[str, Any]:
    """
    Phase 3 retriever：混合 RAG
    - 若 need_internal_kb=True：先查内部 KB（chromadb 向量检索），再补充外部 crawl_by_whitelist
    - 若 chromadb 未初始化/不可用：回退到现有 token-overlap retrieve_evidence（基于 kb_chunks）
    - rerank 后合并到 collected_docs，继续 cleaner/deduplicator/classifier
    """
    query = state.get("query") or ""
    need_internal_kb = bool(state.get("need_internal_kb", False))

    # 清掉 classifier 产生的“路由错误”，避免多轮循环时错误残留导致死循环
    errors = [e for e in (state.get("errors") or []) if e not in {"classifier_low_conf", "classifier_failed"}]

    def _hit_to_internal_doc(hit: dict[str, Any], idx: int) -> dict[str, Any]:
        text = hit.get("chunk_text") or ""
        src = hit.get("source_url") or "knowledge-base"
        return {
            "id": hit.get("id") or f"internal-doc-{idx}",
            "title": hit.get("title") or "知识库文档",
            "source_name": hit.get("source_name") or "internal-kb",
            "source_url": src,
            "url": src,
            "raw_text": text,
            "cleaned_text": text,
            "published_at": None,
            "media_name": hit.get("source_name") or "internal-kb",
            "fetch_status": "success",
            "error": None,
            "_internal_score": float(hit.get("score") or 0.0),
        }

    internal_docs: list[dict[str, Any]] = []
    internal_mode = "disabled"

    if need_internal_kb:
        try:
            from packages.retrieval.service import chroma_is_ready, retrieve_chroma_evidence, retrieve_evidence

            kb_chunks = state.get("kb_chunks") or []
            internal_top_k = int(os.getenv("AGENT_INTERNAL_TOP_K", "6"))

            if chroma_is_ready():
                hits = retrieve_chroma_evidence(query=query, top_k=internal_top_k)
                internal_docs = [_hit_to_internal_doc(h, idx) for idx, h in enumerate(hits)]
                internal_mode = "chroma"
            else:
                hits = retrieve_evidence(query=query, kb_chunks=kb_chunks, top_k=internal_top_k)
                internal_docs = [_hit_to_internal_doc(h, idx) for idx, h in enumerate(hits)]
                internal_mode = "kb_token_overlap"
        except Exception as exc:
            logger.warning("internal_kb_retrieve_failed: %s", exc)
            internal_docs = []
            internal_mode = "internal_failed"

    # 外部 crawl（补充外部证据）
    ws = _to_workflow(state)
    ws = plan_sources(ws)
    ws = crawl_sources(ws)
    external_docs = ws.documents or []

    # 简单 rerank + merge：优先高相关内部证据，再融合外部证据
    combined: list[tuple[float, dict[str, Any]]] = []
    for d in internal_docs:
        base_score = float(d.get("_internal_score") or 0.0)
        text = f"{d.get('title','')} {d.get('cleaned_text','')}"
        score = max(base_score, _token_overlap_score(query, text))
        combined.append((score + 0.12, d))
    for d in external_docs:
        text = f"{d.get('title','')} {d.get('cleaned_text','')}"
        score = _token_overlap_score(query, text)
        d["_external_score"] = score
        combined.append((score, d))

    combined.sort(key=lambda x: x[0], reverse=True)
    max_total = int(os.getenv("AGENT_MAX_TOTAL_DOCS", "30"))
    collected = [doc for _, doc in combined[:max_total]]

    # 清理临时字段
    for d in collected:
        d.pop("_internal_score", None)
        d.pop("_external_score", None)

    non_empty = _count_non_empty_text_items(collected)

    prev_attempt = int(state.get("retriever_attempt") or 0)
    attempt = prev_attempt + 1
    min_docs = int(os.getenv("AGENT_MIN_DOCS", "8"))
    max_retries = int(os.getenv("AGENT_RETRIEVER_MAX_RETRIES", "3"))

    if non_empty < min_docs and attempt <= max_retries:
        errors.append("insufficient_docs")

    stats = {
        **(state.get("stats") or {}),
        **(ws.stats or {}),
        "retriever_attempt": attempt,
        "retriever_non_empty": non_empty,
        "internal_mode": internal_mode,
        "internal_docs_count": len(internal_docs),
        "external_docs_count": len(external_docs),
        "collected_docs_count": len(collected),
    }

    return {
        "collected_docs": collected,
        "stats": stats,
        "errors": errors,
        "retriever_attempt": attempt,
        "status": "running",
        "status_message": f"retriever_done (attempt {attempt}, internal={internal_mode})",
    }


def cleaner_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.documents = state.get("collected_docs") or []
    ws = clean_documents(ws)
    return {
        "cleaned_docs": ws.cleaned_documents,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "status": "running",
        "status_message": "cleaner_done",
    }


def deduplicator_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.cleaned_documents = state.get("cleaned_docs") or []
    ws = deduplicate_documents(ws)
    return {
        "deduplicated_docs": ws.deduplicated_documents,
        "dedupe_meta": ws.dedupe_meta,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "status": "running",
        "status_message": "deduplicator_done",
    }


def classifier_node(state: ReportState) -> dict[str, Any]:
    """
    Phase 2.5 classifier：rule 安全兜底 + llm mapping（low_conf 触发回 retriever）
    """
    mode = os.getenv("AGENT_CLASSIFIER_MODE", "llm").lower().strip() or "llm"
    attempt = int(state.get("retriever_attempt") or 0)

    # 保留非 classifier 错误（例如 insufficient_docs），但清掉旧的 classifier 路由标记
    errors = [e for e in (state.get("errors") or []) if e not in {"classifier_low_conf", "classifier_failed"}]

    ws = _to_workflow(state)
    ws.deduplicated_documents = state.get("deduplicated_docs") or []

    # rule 兜底：无论 llm 成功与否都先有可用 section_map
    ws_rule = classify_documents(ws)
    rule_section_map = ws_rule.section_map
    rule_stats = ws_rule.stats or {}
    section_titles = list(rule_section_map.keys())
    default_section = "附录" if "附录" in section_titles else section_titles[-1]

    if mode == "rule":
        return {
            "section_map": rule_section_map,
            "stats": {**(state.get("stats") or {}), **rule_stats, "classifier_mode": "rule"},
            "errors": errors,
            "status": "running",
            "status_message": "classifier_done(rule)",
        }

    # llm 模式：只有在 LITELLM 配置就绪时才触发（否则回退 rule，避免打爆任务）
    llm_model = os.getenv("LITELLM_MODEL", "").strip()
    llm_api_key = os.getenv("LITELLM_API_KEY", "").strip()
    llm_enabled = bool(llm_model and llm_api_key and llm_api_key != "replace_me")
    if not llm_enabled:
        return {
            "section_map": rule_section_map,
            "stats": {**(state.get("stats") or {}), **rule_stats, "classifier_mode": "llm", "classifier_llm": "disabled"},
            "errors": errors,
            "status": "running",
            "status_message": "classifier_done(llm->disabled->rule)",
        }

    try:
        max_docs = int(os.getenv("AGENT_CLASSIFIER_MAX_DOCS", "14"))
        docs_input: list[dict[str, Any]] = []
        for i, item in enumerate(ws_rule.deduplicated_documents[:max_docs]):  # type: ignore[attr-defined]
            docs_input.append(
                {
                    "id": str(item.get("id") or f"doc-{i}"),
                    "title": str(item.get("title") or "")[:200],
                    "cleaned_text": str(item.get("cleaned_text") or "")[:900],
                    "source_url": str(item.get("source_url") or item.get("url") or "")[:300],
                }
            )

        classifier_prompt = (
            "你将把每个文档片段分配到七个固定中文章节之一。\n"
            "要求：只输出合法 JSON，并且 section_key 使用中文章节标题。\n\n"
            f"FEW_SHOT_EXAMPLES_JSON:\n{json.dumps(CLASSIFIER_FEW_SHOT_EXAMPLES, ensure_ascii=False)}\n\n"
            f"待分类输入 JSON 数组:\n{json.dumps(docs_input, ensure_ascii=False)}\n"
        )

        llm_resp = _call_llm_json(classifier_prompt, system_prompt=CLASSIFIER_LLM_SYSTEM_PROMPT)
        if not llm_resp or not isinstance(llm_resp, dict) or not isinstance(llm_resp.get("items"), list):
            if attempt <= 1:
                errors.append("classifier_failed")
            return {
                "section_map": rule_section_map,
                "stats": {**(state.get("stats") or {}), **rule_stats, "classifier_mode": "llm", "classifier_llm": "parse_failed"},
                "errors": errors,
                "status": "running",
                "status_message": "classifier_done(llm->parse_failed->rule)",
            }

        sec_by_id: dict[str, str] = {}
        conf_by_id: dict[str, float] = {}
        for it in llm_resp.get("items") or []:
            if not isinstance(it, dict):
                continue
            did = str(it.get("id") or "")
            sec = str(it.get("section_key") or "")
            conf_raw = it.get("confidence")
            try:
                conf = float(conf_raw)
            except Exception:
                conf = 0.0
            if sec not in section_titles:
                # 尽量兜底到附录，避免 generate_sections 结构缺失
                sec = default_section
            if did:
                sec_by_id[did] = sec
                if conf < 0.0:
                    conf = 0.0
                if conf > 1.0:
                    conf = conf / 100.0 if conf > 1.0 else 1.0
                conf_by_id[did] = conf

        # confidence < 0.4 -> low_conf
        conf_values: list[float] = []
        section_map: dict[str, list[dict[str, Any]]] = {t: [] for t in section_titles}
        for item in ws_rule.deduplicated_documents:  # type: ignore[attr-defined]
            did = str(item.get("id") or "")
            sec = sec_by_id.get(did, default_section)
            section_map.setdefault(sec, []).append(item)
            conf = conf_by_id.get(did, 0.0)
            conf_values.append(conf)

        low_conf = any(c < 0.4 for c in conf_values) if conf_values else False

        if low_conf and attempt <= 1:
            errors.append("classifier_low_conf")

        conf_min = min(conf_values) if conf_values else None
        conf_avg = sum(conf_values) / len(conf_values) if conf_values else None

        return {
            "section_map": section_map,
            "stats": {
                **(state.get("stats") or {}),
                **rule_stats,
                "classifier_mode": "llm",
                "classifier_llm_low_conf": low_conf,
                "classifier_llm_conf_min": conf_min,
                "classifier_llm_conf_avg": conf_avg,
            },
            "errors": errors,
            "status": "running",
            "status_message": f"classifier_done(llm, low_conf={low_conf})",
        }

    except Exception:
        # llm classifier 崩溃：回退 rule（尽可能触发一次重抓，但不保证）
        if attempt <= 1:
            errors.append("classifier_failed")
        return {
            "section_map": rule_section_map,
            "stats": {**(state.get("stats") or {}), **rule_stats, "classifier_mode": "llm", "classifier_llm": "exception"},
            "errors": errors,
            "status": "running",
            "status_message": "classifier_done(llm->exception->rule)",
        }


def section_generator_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.section_map = state.get("section_map") or {}
    ws.deduplicated_documents = state.get("deduplicated_docs") or []
    ws.kb_chunks = state.get("kb_chunks") or []
    ws = generate_sections(ws)
    return {
        "sections": ws.section_markdown,
        "section_paragraphs": ws.section_paragraphs,
        "structured_signals": ws.structured_signals,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "errors": state.get("errors") or [],
        "status": "running",
        "status_message": "section_generator_done",
    }


def citation_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.section_map = state.get("section_map") or {}
    ws.section_paragraphs = state.get("section_paragraphs") or {}
    ws = generate_citations(ws)
    return {
        "citations": ws.citations,
        "citation_metrics": ws.citation_metrics,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "status": "running",
        "status_message": "citation_done",
    }


def chart_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.deduplicated_documents = state.get("deduplicated_docs") or []
    ws.section_map = state.get("section_map") or {}
    ws.structured_signals = state.get("structured_signals") or []
    ws = generate_charts(ws)
    return {
        "charts": ws.charts,
        "stats": {**(state.get("stats") or {}), **(ws.stats or {})},
        "status": "running",
        "status_message": "chart_done",
    }


def assembler_node(state: ReportState) -> dict[str, Any]:
    ws = _to_workflow(state)
    ws.section_markdown = state.get("sections") or {}
    ws.citations = state.get("citations") or []
    ws = assemble_report(ws)
    return {
        "markdown": ws.markdown,
        "final_report": ws.markdown,
        "status": "completed",
        "status_message": "assembler_done",
    }


def route_after_retriever(state: ReportState) -> str:
    errors = state.get("errors") or []
    attempt = int(state.get("retriever_attempt") or 0)
    max_retries = int(os.getenv("AGENT_RETRIEVER_MAX_RETRIES", "3"))
    if "insufficient_docs" in errors and attempt <= max_retries:
        return "planner"
    return "cleaner"


def route_after_classifier(state: ReportState) -> str:
    errors = state.get("errors") or []
    if "classifier_failed" in errors or "classifier_low_conf" in errors:
        return "retriever"
    return "section_generator"
