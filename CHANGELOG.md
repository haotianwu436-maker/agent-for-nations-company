# Changelog

## v1.0.0 - Delivery Baseline

### Added

- 交付级 README 与文档体系（部署、环境变量、限制、清单）
- demo 套件（输入、LLM 输出、Rule 输出、演示摘要）
- 写作模式可观测字段说明与 API 统计文档
- GitHub Release 草稿文档
- 知识库文件上传接口（`txt/md/docx`）与 Docling 解析增强
- 正式验收清单文档：`docs/acceptance-checklist.md`
- 第三方工具最小接入层（真实工具 + mock 工具）
- PDF 导出能力（在 docx 基础上补齐）

### Changed

- 默认写作模式固定为 `REPORT_WRITING_MODE=llm`
- 保留 `REPORT_WRITING_MODE=rule` 回退模式
- 引用匹配增强（关键词反查 + 证据窗口兜底）以收敛 weak span 告警
- LLM 输出后处理清洗（编号与重复前缀清理、段落格式统一）
- 抓取增强为“首页 + 一级链接 + 直链共存”模式
- 引入信源权威规则（主流/垂直分级、黑名单排除、优先级排序）

### Fixed

- citation warning 收敛到 0（最终验收）
- 弱章节（数据可视化、附录）补充可引用模板
- Docling 不可用时自动回退到现有文本分块解析

### Notes

- `v1.0.0` 作为正式交付冻结版本，后续仅建议接收热修复与运维级改动。
