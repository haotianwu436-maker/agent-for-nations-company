# Changelog

## v1.0.0 - Delivery Baseline

### Added

- 交付级 README 与文档体系（部署、环境变量、限制、清单）
- demo 套件（输入、LLM 输出、Rule 输出、演示摘要）
- 写作模式可观测字段说明与 API 统计文档
- GitHub Release 草稿文档

### Changed

- 默认写作模式固定为 `REPORT_WRITING_MODE=llm`
- 保留 `REPORT_WRITING_MODE=rule` 回退模式
- 引用匹配增强（关键词反查 + 证据窗口兜底）以收敛 weak span 告警
- LLM 输出后处理清洗（编号与重复前缀清理、段落格式统一）

### Fixed

- citation warning 收敛到 0（最终验收）
- 弱章节（数据可视化、附录）补充可引用模板

### Notes

- 本版本不新增业务功能，仅进行交付收口与工程化整理。
