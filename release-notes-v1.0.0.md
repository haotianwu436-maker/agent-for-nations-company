# Release Notes - v1.0.0

## 1. 本版本完成内容

- 完成媒体行业 AI 报告智能体 MVP 主链路交付
- 完成默认 LLM 写作 + rule 回退双模式
- 完成 citation 可追溯链路与 warning 收敛
- 完成交付级文档、部署指南、demo 套件、已知限制说明
- 完成 P0 补齐：第三方工具接入、PDF 导出、首页+一级链接抓取、信源权威规则
- 完成 Docling 实际接入：知识库文件解析预处理 + fallback 机制
- 新增正式验收文档：`docs/acceptance-checklist.md`

## 2. 核心能力

- 固定七章节报告自动生成
- 任务化执行与状态可观测
- 章节摘要与建议可由 LLM 增强
- 抓取/去重/标签/引用绑定具备稳定规则基线
- 图表数据聚合与报告脚注追溯
- 知识库文件上传（txt/md/docx）与检索参与生成
- 品牌化 UI（组织名称与 logo 配置）
- 文档导出（docx + pdf）

## 3. 推荐运行方式

- 推荐：`Postgres Docker + API/Web 本机运行`
- 替代：全 Docker 运行
- 默认模式：`REPORT_WRITING_MODE=llm`
- 回退模式：`REPORT_WRITING_MODE=rule`

## 4. Demo 说明

- 输入：`demo/demo_input.json`
- 输出：
  - `demo/demo_output_llm.md`
  - `demo/demo_output_rule.md`
  - `demo/demo_summary.md`

## 5. 已知限制

- 分类与标签识别仍以规则为主
- 抓取对强反爬与登录站点稳定性有限
- citation 对高度改写摘要仍有精度边界（已做兜底）
- PDF 导出当前未内置中文字体嵌入策略（英文与基础内容可用）

详见：`docs/known-limitations.md`

## 6. 后续优化方向

- 异步任务队列与并发隔离
- 语义检索与 citation 对齐增强
- 站点级抓取适配器
- 更完整的监控、告警与审计
- Docling 解析能力扩展到更多文件类型与策略配置
