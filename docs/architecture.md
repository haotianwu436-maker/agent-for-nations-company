# 媒体行业 AI 资讯报告撰写智能体：实施计划（MVP）

## 1. 总体架构

系统采用 Monorepo，分为 `apps`（可运行应用）与 `packages`（领域能力包）：

- `apps/api`：FastAPI，提供任务 API、鉴权、报告读写、工作流触发。
- `apps/web`：Next.js，提供登录、任务创建、任务列表、报告预览。
- `packages/orchestrator`：LangGraph 工作流节点编排。
- `packages/crawler`：Crawl4AI 抓取与正文抽取封装。
- `packages/retrieval`：Chroma 向量入库与检索（预留后续切 Qdrant/Weaviate）。
- `packages/citation`：来源绑定、引用校验、覆盖率检查。
- `packages/reporting`：固定模板章节渲染与 Markdown 导出。
- `packages/visualization`：图表数据聚合（柱状图/折线图/饼图）。
- `packages/auth`：母子账号与 RBAC 规则。
- `packages/shared`：公共模型、配置、日志、异常。

主链路（SOP）：

1. 创建任务（周报/月报 + 关键词 + 时间范围 + 白名单 + 模板）
2. `plan_sources`
3. `crawl_sources`
4. `clean_documents`
5. `deduplicate_documents`
6. `classify_documents`
7. `retrieve_evidence`
8. `generate_sections`
9. `validate_citations`
10. `generate_charts`
11. `assemble_report`
12. `export_markdown`

## 2. 技术栈

- Backend：Python `3.11` + FastAPI `0.115.0`
- Orchestration：LangGraph `0.2.35`
- Crawling：Crawl4AI `0.4.247`
- LLM Gateway：LiteLLM `1.51.0`
- Retrieval：LangChain + ChromaDB `0.5.5`
- Database：PostgreSQL `16`
- Frontend：Next.js `14.2.15` + React `18.3.1` + Tailwind `3.4.13`
- Auth：JWT（MVP）+ PostgreSQL RBAC
- Observability：预留 Langfuse 接口（MVP 先做埋点抽象）

## 3. 模块拆分与职责

- `apps/api/app/api`：REST API 路由层
- `apps/api/app/services`：任务编排与业务服务
- `apps/api/app/repositories`：DB 操作
- `apps/api/app/schemas`：请求/响应 DTO
- `apps/api/app/core`：配置、日志、异常、依赖注入
- `apps/api/db`：SQL schema 与 seed
- `apps/web/app`：页面路由
- `apps/web/components`：可复用 UI

## 4. 数据库设计（MVP）

关键表：

- `organizations`：母账号组织
- `users`：账号（母/子账号）
- `roles`：角色定义（owner / member）
- `user_roles`：用户角色映射
- `report_jobs`：报告任务主表
- `source_items`：抓取后的原始与清洗内容
- `report_sections`：固定章节内容
- `citations`：引用与证据绑定

状态机：

- `report_jobs.status`: `pending | running | success | failed`

时间范围控制：

- 在创建任务时写入 `time_range_start/time_range_end`
- 所有抓取查询必须追加该过滤条件

## 5. API 设计（MVP）

认证：

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/create-child`（母账号可调用）

任务：

- `POST /api/v1/report-jobs`：创建报告任务
- `GET /api/v1/report-jobs`：分页查询任务
- `GET /api/v1/report-jobs/{job_id}`：任务详情
- `POST /api/v1/report-jobs/{job_id}/run`：执行任务

报告：

- `GET /api/v1/reports/{job_id}/markdown`
- `GET /api/v1/reports/{job_id}/sections`
- `GET /api/v1/reports/{job_id}/charts`

## 6. MVP 范围（本阶段）

已锁定的第一阶段能力：

- 报告任务创建 + 状态跟踪
- 按时间范围抓取（先用白名单 URL + 关键词过滤）
- 清洗去重（URL 去重 + 文本相似去重）
- 固定 7 章输出（无内容时优雅降级）
- 引用绑定与基础校验
- Markdown 报告导出
- 至少 2 种图表数据输出（柱状图/饼图）
- 母子账号基本 RBAC
- 前端 5 个页面骨架

## 7. 开发顺序

1. 基础工程与数据库
2. 认证/RBAC 与任务 API
3. Orchestrator 节点与服务实现
4. Markdown/图表输出
5. 前端页面串联 API
6. 单测 + Happy Path E2E

## 8. 风险点与默认策略

- 抓取不稳定：统一超时、重试、失败落库（不阻塞主流程）
- LLM 不可用：提供 deterministic fallback（规则分类 + 模板占位）
- 引用不足：标记 `citation_status=insufficient`，仍生成降级报告
- 数据重复：双重去重（URL + 文本指纹）
- 待确认项：统一记录到 `docs/progress.md`，不阻塞开发

## 9. 验收方式

最小验收命令（本地）：

1. 启动 `docker compose up --build`
2. 调用创建任务 API 成功返回 `pending`
3. 调用 run API 后任务状态变更至 `success/failed`
4. 能获取 `markdown` 报告，且包含固定 7 章标题
5. 引用表中存在与章节内容绑定的记录
6. 前端可完成登录 -> 创建任务 -> 查看列表 -> 预览报告
