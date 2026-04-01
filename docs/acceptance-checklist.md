# 正式验收清单（客户需求对齐）

| 需求项 | 当前实现说明 | 验证方式 | 验证入口（接口/页面/文件） | 预期结果 | 当前状态 |
|---|---|---|---|---|---|
| 周报/月报生成 | 任务支持 `weekly/monthly`，可执行并产出报告 | 创建并执行两类任务 | `POST /api/v1/report-jobs` + `POST /api/v1/report-jobs/{id}/run` | 任务成功并有 markdown | 通过 |
| 固定七章 | 渲染器强制输出七章 | 获取 markdown | `GET /api/v1/reports/{id}/markdown`，`packages/reporting/renderer.py` | 必含七个章节标题 | 通过 |
| RAG/知识库 | 支持文本与文件上传入库，检索参与章节生成；Docling 优先解析，失败回退 | 上传知识库文档并运行任务 | `POST /api/v1/knowledge/documents`、`POST /api/v1/knowledge/files`、`GET /api/v1/knowledge/search` | stats 有 `kb_ready`，正文有知识库参考 | 通过 |
| 来源真实可核查 | 段落 citation 绑定 source_url + 证据片段 | 查询引用 | `GET /api/v1/reports/{id}/citations` | 引用记录可追溯到 URL 与摘录 | 通过 |
| 数据可视化 | 生成 bar/line/pie 与图表说明 | 查询图表与报告章节 | `GET /api/v1/reports/{id}/charts`、markdown 的“数据可视化”章 | 至少两类图表，含说明 | 通过 |
| 第三方工具接入 | 工作流接入真实工具（archive_verify）+ mock 工具（aigc_mock） | 执行任务后看 stats | `report_jobs.stats.tool_stats`、`packages/tools/service.py` | 统计含工具调用次数与成功数 | 通过 |
| 时间范围控制 | 抓取前进行发布时间过滤 | 任务设定时间范围后执行 | `report_jobs.time_range_start/end`、`packages/crawler/service.py:_time_in_range` | 超出时间范围内容不进入结果 | 通过 |
| 母子账号 | owner 可建子账号，member 可建任务 | 登录 owner 创建子账号，子账号创建任务 | `POST /api/v1/auth/create-child`、`packages/auth/rbac.py` | RBAC 权限按角色生效 | 通过 |
| 品牌化 UI | 组织级 `name/logo_url` 配置，并在任务与报告页展示 | 保存品牌配置并刷新页面 | `PUT /api/v1/organization/branding`、`/jobs`、`/reports/{id}/preview` | 页面展示单位名与 logo | 通过 |
| 导出能力 | 支持 docx/pdf 导出下载 | 调用导出接口 | `GET /api/v1/reports/{id}/export?format=docx|pdf` | 文件可下载并可打开 | 通过 |
| 首页+一级链接抓取 | 对入口页提取一级链接并抓取，保留直链模式 | 白名单传首页 URL 执行任务 | `packages/crawler/service.py` + `report_jobs.stats.crawl_meta` | 统计含 `entry_pages/first_level_links` | 通过 |
| 信源权威机制 | 主流/垂直/其他分级，黑名单排除，优先级排序 | 执行任务查看 crawl meta | `report_jobs.stats.crawl_meta.source_filter` | 统计含分级输入与拦截数 | 通过 |
