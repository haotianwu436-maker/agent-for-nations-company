# 媒体行业 AI 资讯报告撰写智能体

面向媒体行业的报告生产系统。系统以“任务化流水线”方式执行 `搜集 -> 清洗 -> 去重 -> 分类 -> 引用 -> 可视化 -> 成稿`，输出固定七章节周报/月报，支持 LLM 写作与规则回退双模式。

## 项目简介

本项目用于将“资讯收集”升级为“结构化报告交付”。当前版本已具备可演示、可部署、可评审的工程化交付能力，适合作为内测版与后续迭代基线。

## 核心能力

- 固定七章报告生成：`本期聚焦/全球瞭望/案例工场/趋势雷达/实战锦囊/数据可视化/附录`
- 报告任务全流程执行：创建任务、执行任务、状态追踪、报告与图表查询
- 引用链路可追溯：段落级 citation 绑定、覆盖率统计、告警收敛
- 双写作模式：
  - `llm`（默认）：章节摘要与建议由 LLM 生成
  - `rule`（回退）：规则写作，不依赖 LLM
- LLM 自动降级：LLM 不可用/超时/报错时自动回退，不中断主链路
- 母子账号基础 RBAC：支持 owner 创建子账号并执行任务

## 技术架构概览

- 后端：`FastAPI + PostgreSQL`
- 前端：`Next.js + React`
- 编排：`packages/orchestrator`（可平滑迁移到正式 LangGraph 图）
- 抓取：`Crawl4AI + requests/bs4 fallback`
- 写作网关：`LiteLLM`（OpenAI 兼容接口）
- 引用：`packages/citation`
- 报告渲染：`packages/reporting`
- 图表数据：`packages/visualization`

详细架构：`docs/architecture.md`

## 项目目录结构说明

```text
apps/
  api/        FastAPI 服务、数据库 schema、测试
  web/        Next.js 前端
packages/
  orchestrator/  工作流主链路
  crawler/       抓取与正文抽取
  citation/      引用绑定与校验
  reporting/     Markdown 渲染
  visualization/ 图表数据生成
  auth/          RBAC 规则
  retrieval/     检索预留模块
  shared/        公共类型
docs/           交付文档
demo/           演示输入输出样例
scripts/        内部脚本（研发辅助）
```

## 快速启动方式

1. 复制环境变量：`.env.example` -> `.env`
2. 启动依赖（推荐先起 Postgres）：
   - `docker compose up -d postgres`
3. 启动 API：
   - `cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. 启动 Web：
   - `cd apps/web && npm install && npm run dev`
5. 访问：
   - API 文档：`http://localhost:8000/docs`
   - Web：`http://localhost:3000`

完整步骤：`docs/deployment.md`、`docs/local-development.md`

## 快速启动 & 测试

### 1) 初始化知识库（可选但推荐）

```bash
python demo/ingest_demo.py --demo_dir demo/kb_examples
```

### 2) 启动后端与前端

```bash
# API
cd apps/api
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Web
cd apps/web
npm install
npm run dev
```

### 3) 测试纯聊天接口

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/agent/chat" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query":"结合我们内部宣传要点，生成一份本周媒体AI趋势报告",
    "use_llm_writing":true,
    "need_internal_kb":true
  }'
```

### 4) 测试知识库状态与刷新

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/agent/kb/status" -H "Authorization: Bearer <token>"
curl -X POST "http://127.0.0.1:8000/api/v1/agent/kb/refresh" -H "Authorization: Bearer <token>"
```

## 环境依赖要求

- Python `3.11.x`（推荐）
- Node.js `20.x`
- PostgreSQL `16`
- Docker Desktop（推荐，用于数据库与演示环境）

## 环境变量说明

请参考：

- `.env.example`
- `docs/env.md`

重点变量：

- `REPORT_WRITING_MODE=llm`（默认）或 `rule`
- `LITELLM_BASE_URL` / `LITELLM_MODEL` / `LITELLM_API_KEY`
- `DATABASE_URL` / `POSTGRES_*`

## 运行模式说明（llm / rule）

- `llm`：仅“章节摘要写作 + 对总台建议生成”使用 LLM
- `rule`：全规则写作，作为回退和稳定基线
- 不受模式影响的链路：抓取、去重、基础标签识别、citation 主绑定

任务 `stats` 可观测字段：

- `writing_mode_used`
- `llm_summary_count`
- `llm_fallback_count`
- `llm_error_count`
- `section_generation_mode.llm_called`
- `section_generation_mode.section_writing_mode`

## 默认配置说明

- 默认模式：`REPORT_WRITING_MODE=llm`
- 默认回退：LLM 异常自动切换至规则写作
- 默认 demo 账号（仅开发演示）：`owner@demo.com / demo1234`

## Demo 演示流程

1. 读取 demo 输入：`demo/demo_input.json`
2. 创建并运行任务（API 或页面）
3. 查看报告输出：
   - LLM 版：`demo/demo_output_llm.md`
   - Rule 版：`demo/demo_output_rule.md`
4. 查看摘要：`demo/demo_summary.md`

## API 概览

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/create-child`
- `POST /api/v1/report-jobs`
- `GET /api/v1/report-jobs`
- `GET /api/v1/report-jobs/{job_id}`
- `POST /api/v1/report-jobs/{job_id}/run`
- `GET /api/v1/reports/{job_id}/markdown`
- `GET /api/v1/reports/{job_id}/charts`
- `GET /api/v1/reports/{job_id}/citations`

详细请求响应：`docs/api-spec.md`

## 报告生成链路说明

`plan_sources -> crawl_sources -> clean_documents -> deduplicate_documents -> classify_documents -> generate_sections -> generate_citations -> generate_charts -> assemble_report -> persist_report`

## 已知限制

请见：`docs/known-limitations.md`

## 后续可扩展方向

- 异步任务队列（Celery/RQ）
- 检索模块（Chroma/Qdrant）正式接入
- 站点级抓取适配器与发布时效增强
- 更细粒度 citation 语义对齐

## License / 使用说明

当前仓库 License：**待定（TBD）**。  
在明确开源/商用授权前，请仅用于内部评审与演示。
