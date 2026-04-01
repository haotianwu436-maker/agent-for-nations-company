from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlparse

from packages.citation.service import build_citations_for_sections, validate_citations
from packages.crawler.service import crawl_by_whitelist
from packages.reporting.renderer import SECTION_KEYS, render_markdown
from packages.tools.service import run_tools_on_items
from packages.visualization.service import generate_chart_data

logger = logging.getLogger(__name__)


@dataclass
class WorkflowState:
    job_id: str
    organization_id: str
    report_type: str
    keywords: list[str]
    time_range_start: str
    time_range_end: str
    source_whitelist: list[str]
    use_llm_writing: bool = False
    language: str = "zh-CN"
    status: str = "pending"
    status_message: str = ""
    errors: list[str] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)
    cleaned_documents: list[dict] = field(default_factory=list)
    deduplicated_documents: list[dict] = field(default_factory=list)
    dedupe_meta: dict = field(default_factory=dict)
    section_map: dict[str, list[dict]] = field(default_factory=dict)
    citations: list[dict] = field(default_factory=list)
    citation_metrics: dict = field(default_factory=dict)
    section_markdown: dict[str, str] = field(default_factory=dict)
    section_paragraphs: dict[str, list[dict]] = field(default_factory=dict)
    markdown: str = ""
    charts: list[dict] = field(default_factory=list)
    structured_signals: list[dict] = field(default_factory=list)
    kb_chunks: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _token_set(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]{2,}", (text or "").lower())
    return set(tokens)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return inter / union if union else 0.0


def _safe_step(state: WorkflowState, step_name: str, fn: Callable[[WorkflowState], WorkflowState]) -> WorkflowState:
    try:
        logger.info("step_start job_id=%s step=%s", state.job_id, step_name)
        out = fn(state)
        out.status_message = f"{step_name} completed"
        logger.info("step_done job_id=%s step=%s", state.job_id, step_name)
        return out
    except Exception as exc:
        logger.exception("step_failed job_id=%s step=%s", state.job_id, step_name)
        state.errors.append(f"{step_name}: {exc}")
        state.status = "failed"
        state.status_message = f"{step_name} failed"
        return state


def _call_llm(prompt: str) -> str | None:
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
                {"role": "system", "content": "你是媒体行业AI资讯分析助手，输出简洁、可引用、无臆测。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=400,
            timeout=30,
        )
        return resp.choices[0].message.content  # type: ignore
    except Exception as exc:
        logger.warning("llm_call_failed: %s", exc)
        return None


def _call_llm_with_status(prompt: str) -> tuple[str | None, str]:
    model_name = os.getenv("LITELLM_MODEL", "").strip()
    api_key = os.getenv("LITELLM_API_KEY", "").strip()
    if not model_name or not api_key or api_key == "replace_me":
        return None, "disabled"
    try:
        result = _call_llm(prompt)
        if result:
            return result, "ok"
        return None, "error"
    except Exception:
        return None, "error"


def plan_sources(state: WorkflowState) -> WorkflowState:
    if not state.source_whitelist:
        state.source_whitelist = ["https://example.com"]
    state.stats["planned_sources"] = len(state.source_whitelist)
    return state


def crawl_sources(state: WorkflowState) -> WorkflowState:
    crawled, crawl_meta = crawl_by_whitelist(
        whitelist=state.source_whitelist,
        keywords=state.keywords,
        start_at=state.time_range_start,
        end_at=state.time_range_end,
        return_meta=True,
    )
    state.documents = crawled
    state.stats["crawl_total"] = len(crawled)
    state.stats["crawl_success"] = len([x for x in crawled if x.get("fetch_status") == "success"])
    state.stats["crawl_failed"] = len([x for x in crawled if x.get("fetch_status") == "failed"])
    non_empty = len([x for x in crawled if len((x.get("cleaned_text") or "").strip()) >= 120])
    state.stats["content_non_empty_rate"] = round(non_empty / max(len(crawled), 1), 4)
    state.stats["crawl_meta"] = crawl_meta
    return state


def clean_documents(state: WorkflowState) -> WorkflowState:
    cleaned: list[dict] = []
    for idx, item in enumerate(state.documents):
        text = item.get("cleaned_text") or item.get("raw_text") or ""
        text = re.sub(r"\s+", " ", text).strip()
        cleaned.append(
            {
                **item,
                "id": item.get("id") or f"doc-{idx}",
                "source_url": item.get("source_url") or item.get("url"),
                "title": (item.get("title") or "未命名标题").strip(),
                "cleaned_text": text[:12000],
                "hash": _text_hash(text[:4000]),
            }
        )
    state.cleaned_documents = cleaned
    state.stats["clean_total"] = len(cleaned)
    baseline_non_empty = 0
    improved_non_empty = 0
    for item in cleaned:
        meta = item.get("error", "")
        m = re.search(r"baseline_len=(\d+);extracted_len=(\d+)", meta)
        if m:
            if int(m.group(1)) >= 120:
                baseline_non_empty += 1
            if int(m.group(2)) >= 120:
                improved_non_empty += 1
    if cleaned:
        state.stats["extract_quality_before"] = round(baseline_non_empty / len(cleaned), 4)
        state.stats["extract_quality_after"] = round(improved_non_empty / len(cleaned), 4)
    return state


def deduplicate_documents(state: WorkflowState) -> WorkflowState:
    url_seen: dict[str, dict] = {}
    title_seen: dict[str, dict] = {}
    deduped: list[dict] = []
    mapping: list[dict] = []

    for item in state.cleaned_documents:
        norm_url = _normalize_url(item.get("source_url", ""))
        norm_title = _normalize_title(item.get("title", ""))
        if norm_url and norm_url in url_seen:
            mapping.append({"merged_id": item["id"], "target_id": url_seen[norm_url]["id"], "reason": "url"})
            continue
        if norm_title and norm_title in title_seen:
            mapping.append({"merged_id": item["id"], "target_id": title_seen[norm_title]["id"], "reason": "title"})
            continue

        duplicate_target = None
        current_set = _token_set(item.get("cleaned_text", ""))
        for kept in deduped:
            score = _jaccard(current_set, _token_set(kept.get("cleaned_text", "")))
            if score >= 0.82:
                duplicate_target = kept
                break
        if duplicate_target:
            mapping.append({"merged_id": item["id"], "target_id": duplicate_target["id"], "reason": "similarity"})
            continue

        deduped.append(item)
        if norm_url:
            url_seen[norm_url] = item
        if norm_title:
            title_seen[norm_title] = item

    state.deduplicated_documents = deduped
    state.dedupe_meta = {
        "before_count": len(state.cleaned_documents),
        "after_count": len(deduped),
        "merged_map": mapping,
    }
    return state


def classify_documents(state: WorkflowState) -> WorkflowState:
    # 固定章节 + 单文档单章节分配（避免重复）
    section_map: dict[str, list[dict]] = {title: [] for title in SECTION_KEYS.values()}
    hit_count = {k: 0 for k in section_map.keys()}
    for item in state.deduplicated_documents:
        text = f"{item.get('title', '')} {item.get('cleaned_text', '')}".lower()
        if any(k in text for k in ["投融资", "爆发", "重磅", "发布"]):
            key = "本期聚焦"
        elif any(k in text for k in ["政策", "监管", "global", "欧洲", "美国", "中国", "policy", "regulation", "government"]):
            key = "全球瞭望"
        elif any(k in text for k in ["案例", "落地", "合作", "上线", "应用", "adoption", "deployment", "newsroom"]):
            key = "案例工场"
        elif any(k in text for k in ["趋势", "预测", "未来", "增长", "trend", "forecast", "capabilities", "market"]):
            key = "趋势雷达"
        elif any(k in text for k in ["方法", "工具", "指南", "实践", "专家", "how", "guide", "plugin", "tool", "workflow"]):
            key = "实战锦囊"
        elif any(k in text for k in ["launch", "release", "announcing", "debut", "introducing", "new"]):
            key = "本期聚焦"
        elif bool(re.search(r"\d+(\.\d+)?%|\d+亿|\d+万", text)):
            key = "数据可视化"
        else:
            key = "附录"
        section_map[key].append(item)
        hit_count[key] += 1

    # 二次平衡：避免单章节堆积，优先分流到趋势雷达/实战锦囊/案例工场
    overflow = section_map["全球瞭望"][3:]
    section_map["全球瞭望"] = section_map["全球瞭望"][:3]
    for idx, item in enumerate(overflow):
        target = ["趋势雷达", "实战锦囊", "案例工场"][idx % 3]
        section_map[target].append(item)
        hit_count[target] += 1

    state.section_map = section_map
    state.stats["classification_hits"] = hit_count
    state.stats["section_distribution"] = {k: len(v) for k, v in section_map.items()}
    return state


def run_tools(state: WorkflowState) -> WorkflowState:
    payload = run_tools_on_items(state.deduplicated_documents, limit=5)
    state.tool_results = payload["tool_results"]
    state.stats["tool_stats"] = payload["tool_stats"]
    return state


def generate_citations(state: WorkflowState) -> WorkflowState:
    citations = build_citations_for_sections(state.section_map, state.section_paragraphs)
    metrics = validate_citations(citations)
    state.citations = citations
    state.citation_metrics = metrics
    return state


def generate_sections(state: WorkflowState) -> WorkflowState:
    section_markdown: dict[str, str] = {}
    section_paragraphs: dict[str, list[dict]] = {}
    section_mode: dict[str, str] = {}
    llm_summary_count = 0
    llm_fallback_count = 0
    llm_error_count = 0
    llm_called = False
    key_order = ["事件描述：", "行业影响：", "关键信号：", "风险点/机会点："]

    def _clean_llm_line(text: str) -> str:
        out = (text or "").strip()
        out = re.sub(r"^\s*\d+\)\s*", "", out)
        out = re.sub(r"^\s*[一二三四五六七八九十]+\)\s*", "", out)
        out = re.sub(r"^\s*[-*]\s*", "", out)
        out = re.sub(r"\s+", " ", out).strip()
        return out

    def _normalize_paragraph_text(paragraph: str) -> str:
        rows = [_clean_llm_line(x) for x in paragraph.splitlines() if x.strip()]
        kv: dict[str, str] = {}
        def _normalize_labeled(row: str, label: str) -> str:
            body = row[len(label) :].strip()
            body = re.sub(r"^\d+\)\s*", "", body)
            body = re.sub(r"^(事件描述|行业影响|关键信号|风险点/机会点)：\s*", "", body)
            return f"{label}{body}"
        for row in rows:
            if row.startswith("事件描述："):
                kv["事件描述："] = _normalize_labeled(row, "事件描述：")
            elif row.startswith("行业影响："):
                kv["行业影响："] = _normalize_labeled(row, "行业影响：")
            elif row.startswith("关键信号："):
                kv["关键信号："] = _normalize_labeled(row, "关键信号：")
            elif row.startswith("风险点/机会点："):
                kv["风险点/机会点："] = _normalize_labeled(row, "风险点/机会点：")
        return "\n".join([kv[k] for k in key_order if k in kv])

    def legacy_signal(item: dict) -> dict:
        text = f"{item.get('title','')} {item.get('cleaned_text','')}".lower()
        if any(k in text for k in ["policy", "regulation", "government", "responsible scaling"]):
            theme = "政策治理"
        elif any(k in text for k in ["plugin", "tool", "code", "cli"]):
            theme = "工具链与生产力"
        elif any(k in text for k in ["gemini", "openai", "anthropic", "model"]):
            theme = "模型能力升级"
        else:
            theme = "产业动态"

        if "anthropic" in text:
            org = "Anthropic"
            region = "美国"
        elif "openai" in text:
            org = "OpenAI"
            region = "美国"
        elif "google" in text or "gemini" in text:
            org = "Google"
            region = "美国"
        else:
            org = (item.get("source_name") or "未知机构")[:40]
            region = "全球"
        return {"theme": theme, "org": org, "region": region}

    def build_signal(item: dict) -> dict:
        text = f"{item.get('title','')} {item.get('cleaned_text','')}".lower()
        title_low = (item.get("title", "") or "").lower()
        # 机构识别优先级：Gemini/Google > OpenAI/Codex/GPT > Anthropic/Claude > 其他
        # 主题识别优先级：政策治理 > 工具链与生产力 > 模型能力升级 > 产业影响 > 产业动态
        if any(k in text for k in ["copyright", "licensing", "safety policy", "responsible scaling", "regulation", "governance"]):
            theme = "政策治理"
        elif any(k in text for k in ["plugin", "tool", "code", "cli", "workflow", "agent"]):
            theme = "工具链与生产力"
        elif any(k in text for k in ["gemini", "gpt", "claude", "model", "compression", "flash live"]):
            theme = "模型能力升级"
        elif any(k in text for k in ["job market", "labor", "adoption", "enterprise"]):
            theme = "产业影响"
        else:
            theme = "产业动态"

        source_url = (item.get("source_url") or "").lower()
        source_name = (item.get("source_name") or "").lower()
        # 机构识别优先级：显式品牌词 > URL域名 > 正文关键词
        if any(k in title_low for k in ["gemini", "google", "deepmind"]):
            org = "Google"
            region = "美国"
        elif any(k in title_low for k in ["openai", "codex", "gpt"]):
            org = "OpenAI"
            region = "美国"
        elif any(k in title_low for k in ["anthropic", "claude"]):
            org = "Anthropic"
            region = "美国"
        elif any(k in text for k in ["openai", "codex", "gpt"]):
            org = "OpenAI"
            region = "美国"
        elif any(k in text for k in ["anthropic", "claude"]):
            org = "Anthropic"
            region = "美国"
        elif any(k in text for k in ["google", "gemini", "deepmind"]):
            org = "Google"
            region = "美国"
        elif "openai.com" in source_url or "openai" in source_name:
            org = "OpenAI"
            region = "美国"
        elif "anthropic.com" in source_url or "anthropic" in source_name:
            org = "Anthropic"
            region = "美国"
        elif "google." in source_url or "deepmind" in source_url:
            org = "Google"
            region = "美国"
        elif "eu" in text or "europe" in text:
            org = (item.get("source_name") or "未知机构")[:40]
            region = "欧洲"
        elif "china" in text or "beijing" in text:
            org = (item.get("source_name") or "未知机构")[:40]
            region = "中国"
        else:
            org = (item.get("source_name") or "未知机构")[:40]
            region = "全球"
        return {"theme": theme, "org": org, "region": region}

    def build_analysis_lines(item: dict, signal: dict) -> tuple[str, str, str]:
        title = item.get("title", "未命名事件")
        text = f"{title} {(item.get('cleaned_text','')[:1200])}".lower()
        event = f"{title}。"
        if signal["theme"] == "工具链与生产力":
            impact = "该事件表明AI生产工具正从实验走向编采流程核心，内容策划与技术协同效率会显著提升。"
            risk_opp = "机会点：建设统一的采编Agent工具台；风险点：代码与插件供应链暴露带来安全与审计压力。"
        elif signal["theme"] == "模型能力升级":
            impact = "该动态显示多模态/实时交互能力正在提升，新闻采集、快编快审和智能分发链路将被重构。"
            risk_opp = "机会点：打造直播和快讯场景的实时辅助生产；风险点：模型可靠性不足会放大错引和误判。"
        elif signal["theme"] == "政策治理":
            impact = "该政策类进展会直接影响媒体机构在内容安全、来源合规和AI应用边界上的制度设计。"
            risk_opp = "机会点：以治理框架反哺总台AI规范体系；风险点：若规则落地滞后，跨平台发布风险上升。"
        elif signal["theme"] == "产业影响":
            impact = "事件反映AI对就业结构与业务分工的持续影响，媒体组织能力模型需提前调整。"
            risk_opp = "机会点：重塑“人机协同”岗位与能力地图；风险点：组织转型节奏不一致会拉大产能差距。"
        else:
            impact = "该事件说明AI能力正在持续外溢到媒体产业链多个环节，竞争焦点从模型转向场景与执行力。"
            risk_opp = "机会点：形成垂类报道与工具联动优势；风险点：同质化追踪导致内容价值被稀释。"

        # 关键信号增加差异化信息
        if "leak" in text or "exposed" in text:
            signal_line = f"关键信号：{signal['org']}相关工具链暴露安全脆弱点，主题={signal['theme']}，地区={signal['region']}。"
        elif "job market" in text:
            signal_line = f"关键信号：AI能力评估开始外溢至就业与组织层面，主题={signal['theme']}，地区={signal['region']}。"
        elif "plugin" in text or "codex" in text:
            signal_line = f"关键信号：开发者生态竞争进入“插件+平台”阶段，主题={signal['theme']}，机构={signal['org']}。"
        elif "flash live" in text:
            signal_line = f"关键信号：实时交互模型落地提速，真假信息识别门槛提高，主题={signal['theme']}。"
        else:
            signal_line = f"关键信号：主题={signal['theme']}，机构={signal['org']}，地区={signal['region']}。"
        return event, impact, f"{signal_line}\n风险点/机会点：{risk_opp}"

    def ensure_full_paragraph(paragraph: str, item: dict, signal: dict) -> str:
        event, impact, sig_risk = build_analysis_lines(item, signal)
        required = {
            "事件描述：": f"事件描述：{event}",
            "行业影响：": f"行业影响：{impact}",
            "关键信号：": sig_risk.split("\n")[0],
            "风险点/机会点：": sig_risk.split("\n")[1] if "\n" in sig_risk else "风险点/机会点：机会在于流程提效，风险在于治理与审校压力。",
        }
        out = paragraph.strip()
        for key, default_line in required.items():
            if key not in out:
                out += ("\n" if out else "") + default_line
        return out

    # 空章节补强：本期聚焦/案例工场优先补齐
    all_items = []
    for items in state.section_map.values():
        all_items.extend(items)
    if not state.section_map["本期聚焦"] and all_items:
        top_item = max(all_items, key=lambda x: len(x.get("cleaned_text", "")))
        for sec in ["全球瞭望", "趋势雷达", "实战锦囊", "附录"]:
            if top_item in state.section_map[sec]:
                state.section_map[sec].remove(top_item)
                break
        state.section_map["本期聚焦"].append(top_item)
    if not state.section_map["案例工场"]:
        candidate = None
        for sec in ["实战锦囊", "全球瞭望", "趋势雷达"]:
            for item in state.section_map[sec]:
                txt = f"{item.get('title','')} {item.get('cleaned_text','')}".lower()
                if any(k in txt for k in ["plugin", "workflow", "deployment", "tool", "practice", "codex"]):
                    candidate = item
                    state.section_map[sec].remove(item)
                    break
            if candidate:
                break
        if candidate:
            state.section_map["案例工场"].append(candidate)
    if not state.section_map["实战锦囊"]:
        candidate = None
        for sec in ["案例工场", "全球瞭望", "趋势雷达"]:
            for item in state.section_map[sec]:
                txt = f"{item.get('title','')} {item.get('cleaned_text','')}".lower()
                if any(k in txt for k in ["tool", "plugin", "workflow", "practice", "how", "guide", "codex"]):
                    candidate = item
                    if sec != "案例工场":
                        state.section_map[sec].remove(item)
                    break
            if candidate:
                break
        if candidate:
            state.section_map["实战锦囊"].append(candidate)

    label_before_after = []
    for section_title, items in state.section_map.items():
        if not items:
            section_markdown[section_title] = "暂无可用内容。"
            section_paragraphs[section_title] = []
            continue
        lines: list[str] = []
        paragraph_rows: list[dict] = []
        for item in items[:6]:
            source = item.get("source_name") or item.get("media_name") or "未知来源"
            old_signal = legacy_signal(item)
            signal = build_signal(item)
            label_before_after.append({"title": item.get("title", "")[:80], "before": old_signal, "after": signal})
            state.structured_signals.append(signal)
            excerpt = (item.get("cleaned_text", "")[:300]).strip()
            if not excerpt:
                excerpt = (item.get("title", "")[:120]).strip()
            prompt = (
                "请用中文写三行，每行一段：1)事件描述 2)行业影响 3)关键信号。不要编造。\n"
                f"标题：{item.get('title','')}\n"
                f"正文：{(item.get('cleaned_text','')[:1500])}"
            )
            kb_evidence = []
            if state.kb_chunks:
                try:
                    from packages.retrieval.service import retrieve_evidence

                    kb_evidence = retrieve_evidence(
                        query=f"{item.get('title','')} {signal.get('theme','')}",
                        kb_chunks=state.kb_chunks,
                        top_k=1,
                    )
                except Exception:
                    kb_evidence = []
            llm_status = "disabled"
            model_text = None
            if state.use_llm_writing:
                model_text, llm_status = _call_llm_with_status(prompt)
                llm_called = llm_called or llm_status != "disabled"
            if model_text:
                llm_summary_count += 1
                lines_out = [x.strip() for x in model_text.strip().splitlines() if x.strip()]
                event = lines_out[0] if lines_out else f"{item.get('title','未命名事件')}。"
                impact = lines_out[1] if len(lines_out) > 1 else "该动态显示媒体与AI协同生产正在加速，关键流程会进一步重构。"
                sig = lines_out[2] if len(lines_out) > 2 else f"主题={signal['theme']}，机构={signal['org']}，地区={signal['region']}。"
                risk = lines_out[3] if len(lines_out) > 3 else "风险点/机会点：机会在于流程提效，风险在于治理与审校压力同步上升。"
                paragraph = f"事件描述：{event}\n行业影响：{impact}\n关键信号：{sig}\n{risk}"
                source_mode = "llm_summary"
            else:
                if state.use_llm_writing:
                    llm_fallback_count += 1
                    if llm_status == "error":
                        llm_error_count += 1
                event, impact, sig_risk = build_analysis_lines(item, signal)
                paragraph = f"事件描述：{event}\n行业影响：{impact}\n{sig_risk}"
                source_mode = "extractive"
            paragraph = _normalize_paragraph_text(ensure_full_paragraph(paragraph, item, signal))
            if kb_evidence:
                paragraph += f"\n知识库参考：{kb_evidence[0].get('title','知识库文档')}（{kb_evidence[0].get('source_name','knowledge-base')}）"
            lines.append(f"- {paragraph}\n  来源：{source}")
            paragraph_rows.append(
                {
                    "paragraph_text": paragraph,
                    "source_item_id": item.get("id"),
                    "source_url": item.get("source_url"),
                    "source_mode": source_mode,
                    "source_text": item.get("cleaned_text") or "",
                }
            )
        # 章节级“对总台的启示与建议”
        if section_title in {"本期聚焦", "全球瞭望", "趋势雷达", "实战锦囊"}:
            chapter_themes = sorted({build_signal(x)["theme"] for x in items[:6]})
            chapter_orgs = sorted({build_signal(x)["org"] for x in items[:6]})
            tips_lines: list[str] = []
            # 事件级建议：至少1条与首个事件强关联
            head_title = (items[0].get("title") or "本章重点事件")[:80]
            llm_tip = None
            if state.use_llm_writing:
                llm_tip, tip_status = _call_llm_with_status(
                    "请基于以下事件，给出1条对总台可执行的建议，20-50字，中文。\n"
                    f"章节：{section_title}\n事件：{head_title}\n主题：{','.join(chapter_themes)}"
                )
                llm_called = llm_called or tip_status != "disabled"
                if not llm_tip:
                    llm_fallback_count += 1
                    if tip_status == "error":
                        llm_error_count += 1
            tips_lines.append(llm_tip.strip() if llm_tip else f"围绕“{head_title}”，建议总台建立事件-风险-核验三联表，提升重大AI事件的编辑决策速度。")
            if "政策治理" in chapter_themes:
                tips_lines.append("针对治理议题，建议将外部政策更新映射到内部采编规范清单，形成周度更新机制。")
            if "工具链与生产力" in chapter_themes:
                tips_lines.append("针对工具链议题，建议在快讯和编校环节先行部署可复用流程模板，并记录产能改进指标。")
            if "模型能力升级" in chapter_themes:
                tips_lines.append("针对模型升级议题，建议按“准确性/时效性/可解释性”建立对比评估表，避免单指标选型。")
            if chapter_orgs:
                tips_lines.append(f"本章涉及机构{ '、'.join(chapter_orgs[:3]) }，建议设置机构级长期追踪档案。")
            tips = "对总台的启示与建议：\n" + "\n".join([f"{i+1}) {line}" for i, line in enumerate(tips_lines)])
            lines.append(tips)

        if section_title == "数据可视化":
            lines.append("图表解读：本期样本在“政策治理”主题集中度较高，说明行业讨论焦点正从模型能力转向治理与落地规范。")

        section_markdown[section_title] = "\n".join(lines)
        section_paragraphs[section_title] = paragraph_rows
        llm_rows = sum(1 for p in paragraph_rows if p["source_mode"] == "llm_summary")
        if llm_rows == 0:
            section_mode[section_title] = "rule"
        elif llm_rows == len(paragraph_rows):
            section_mode[section_title] = "llm"
        else:
            section_mode[section_title] = "mixed"
    state.section_markdown = section_markdown
    state.section_paragraphs = section_paragraphs
    writing_mode_used = "llm" if (state.use_llm_writing and llm_summary_count > 0) else "rule"
    state.stats["section_generation_mode"] = {
        "writing_mode_used": writing_mode_used,
        "llm_summary_count": llm_summary_count,
        "llm_fallback_count": llm_fallback_count,
        "llm_error_count": llm_error_count,
        "extractive_fallback_count": sum(1 for sec in section_paragraphs.values() for p in sec if p["source_mode"] == "extractive"),
        "llm_called": llm_called,
        "section_writing_mode": section_mode,
    }
    state.stats["writing_mode_used"] = writing_mode_used
    state.stats["llm_summary_count"] = llm_summary_count
    state.stats["llm_fallback_count"] = llm_fallback_count
    state.stats["llm_error_count"] = llm_error_count
    state.stats["label_compare"] = label_before_after

    # 附录补强：即便正文全分配，也回填延伸阅读
    if "附录" in state.section_markdown and "暂无可用内容" in state.section_markdown["附录"]:
        refs = []
        for sec in ["本期聚焦", "全球瞭望", "案例工场", "趋势雷达", "实战锦囊"]:
            for p in section_paragraphs.get(sec, [])[:2]:
                if p.get("source_url"):
                    refs.append(p["source_url"])
        refs = list(dict.fromkeys(refs))[:5]
        if refs:
            state.section_markdown["附录"] = (
                "补充来源与延伸阅读：\n"
                + "\n".join([f"- {u}" for u in refs])
            )
            ref_source = refs[0]
            state.section_map.setdefault("附录", []).append(
                {
                    "id": "appendix-ref-0",
                    "source_url": ref_source,
                    "title": "延伸阅读来源汇总",
                    "cleaned_text": "附录延伸阅读来源清单，用于补充正文未覆盖信号。",
                }
            )
            state.section_paragraphs.setdefault("附录", []).append(
                {
                    "paragraph_text": "事件描述：附录汇总了本期延伸阅读来源。\n行业影响：可作为编辑部二次选题与复盘素材库。\n关键信号：本期附录聚合跨机构来源，便于横向对比。\n风险点/机会点：机会在于拓展报道深度，风险在于来源质量参差需复核。",
                    "source_item_id": "appendix-ref-0",
                    "source_url": ref_source,
                    "source_mode": "extractive",
                    "source_text": "附录延伸阅读来源清单，用于补充正文未覆盖信号。",
                }
            )

    # 数据可视化章节补强：写入图表解读文字
    if "数据可视化" in state.section_markdown and "暂无可用内容" in state.section_markdown["数据可视化"]:
        dist = state.stats.get("section_distribution", {})
        state.section_markdown["数据可视化"] = (
            "图表解读：\n"
            f"- 章节分布显示：全球瞭望={dist.get('全球瞭望',0)}，趋势雷达={dist.get('趋势雷达',0)}，案例工场={dist.get('案例工场',0)}。\n"
            "- 主题分布反映本期讨论集中在“工具链与生产力/政策治理”，建议下周增加商业化与用户体验维度样本。"
        )
        fallback_source = ""
        for sec in ["本期聚焦", "全球瞭望", "案例工场", "趋势雷达", "实战锦囊"]:
            for p in state.section_paragraphs.get(sec, []):
                if p.get("source_url"):
                    fallback_source = p["source_url"]
                    break
            if fallback_source:
                break
        if fallback_source:
            state.section_map.setdefault("数据可视化", []).append(
                {
                    "id": "viz-ref-0",
                    "source_url": fallback_source,
                    "title": "图表解读依据",
                    "cleaned_text": "图表解读基于章节分布和主题分布统计。",
                }
            )
            state.section_paragraphs.setdefault("数据可视化", []).append(
                {
                    "paragraph_text": "事件描述：数据可视化章节基于本期结构化统计生成。\n行业影响：可帮助编辑团队快速识别信息密集区与弱覆盖区。\n关键信号：全球瞭望占比更高，提示国际动态追踪压力上升。\n风险点/机会点：机会在于数据化选题，风险在于样本偏差导致误读。",
                    "source_item_id": "viz-ref-0",
                    "source_url": fallback_source,
                    "source_mode": "extractive",
                    "source_text": "图表解读基于章节分布和主题分布统计。",
                }
            )
    return state


def generate_charts(state: WorkflowState) -> WorkflowState:
    state.charts = generate_chart_data(state.deduplicated_documents, state.section_map)
    # 业务图：主题分布 + 机构/地区分布
    theme_count: dict[str, int] = {}
    org_region_count: dict[str, int] = {}
    for s in state.structured_signals:
        theme = s.get("theme", "未分类")
        key = f"{s.get('org','未知')}|{s.get('region','全球')}"
        theme_count[theme] = theme_count.get(theme, 0) + 1
        org_region_count[key] = org_region_count.get(key, 0) + 1
    state.charts.append(
        {
            "type": "bar",
            "chart_type": "bar",
            "title": "主题分布图",
            "labels": list(theme_count.keys()),
            "values": list(theme_count.values()),
            "notes": "由内容理解后的主题标签聚合",
        }
    )
    state.charts.append(
        {
            "type": "pie",
            "chart_type": "pie",
            "title": "机构/地区分布图",
            "labels": list(org_region_count.keys()),
            "values": list(org_region_count.values()),
            "notes": "由内容理解后的机构与地区标签聚合",
        }
    )
    return state


def assemble_report(state: WorkflowState) -> WorkflowState:
    title_to_citations: dict[str, list[dict]] = {}
    for c in state.citations:
        title = SECTION_KEYS.get(c["section_key"], c["section_key"])
        title_to_citations.setdefault(title, []).append(c)
    state.markdown = render_markdown(state.section_markdown, title_to_citations)
    return state


def persist_report(state: WorkflowState, persist_fn: Callable[[WorkflowState], None] | None = None) -> WorkflowState:
    if persist_fn:
        persist_fn(state)
    return state


def execute_workflow(initial_state: WorkflowState, persist_fn: Callable[[WorkflowState], None] | None = None) -> WorkflowState:
    state = initial_state
    state.status = "running"
    steps = [
        ("plan_sources", plan_sources),
        ("crawl_sources", crawl_sources),
        ("clean_documents", clean_documents),
        ("deduplicate_documents", deduplicate_documents),
        ("run_tools", run_tools),
        ("classify_documents", classify_documents),
        ("generate_sections", generate_sections),
        ("generate_citations", generate_citations),
        ("generate_charts", generate_charts),
        ("assemble_report", assemble_report),
    ]
    for step_name, fn in steps:
        state = _safe_step(state, step_name, fn)
        if state.status == "failed":
            return state
    state = _safe_step(state, "persist_report", lambda s: persist_report(s, persist_fn))
    state.status = "failed" if state.errors else "success"
    state.stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    return state
