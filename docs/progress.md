# 开发进度

## 当前阶段

- [x] 第一步：实施计划（架构/数据库/API/MVP/风险/验收）
- [x] 第二步：项目骨架搭建
- [x] 第三步：后端核心链路（第一批闭环）
- [x] 第四步：前端最小页面
- [x] 第五步：测试与文档完善（第一批）
- [x] 第六步：正式交付收口（文档体系 + demo + release 准备）

## 已完成

- 建立实施计划文档：`docs/architecture.md`
- 输出 API 规格：`docs/api-spec.md`
- 创建 monorepo 目录与运行骨架：`apps` / `packages` / `docs`
- 完成 PostgreSQL 初始化 schema 与 RBAC 基础表：`apps/api/db/schema.sql`
- 完成 FastAPI 最小可运行 API：认证、任务、报告读取
- 完成 Next.js 最小页面：登录、任务创建、任务列表、任务详情、报告预览
- 补充启动文档：`docs/setup.md`
- 打通真实执行链路：`packages/orchestrator/workflow.py`
- 实现抓取 fallback + 重试 + 超时：`packages/crawler/service.py`
- 实现清洗、去重、规则分类、引用覆盖率、markdown 渲染、图表生成
- API 已打通创建任务/执行任务/查询状态/报告 markdown/图表/citations
- 新增第一批测试：orchestrator、dedupe、citation、renderer、API 集成

## 待确认项（不阻塞开发）

1. 最终主模型供应商（默认通过 LiteLLM 走 OpenAI 兼容接口）
2. 爬虫白名单初始来源列表（默认先允许任务入参传入）
3. 向量库切换策略（MVP 用 Chroma，后续可切 Qdrant/Weaviate）
4. 品牌 UI 文案与 logo 资源（MVP 用占位配置）
5. 抓取站点发布日期解析策略（当前取不到发布时间时允许为空）

## 下一步

- 进入 `v1.0.0` 版本冻结，默认仅接受热修复
- 下一迭代优先：异步任务队列、检索增强、站点级抓取适配
