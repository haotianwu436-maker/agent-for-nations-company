# Demo 摘要（交付演示用）

## 1. 输入参数

- 报告类型：`weekly`
- 时间范围：`2026-03-25` ~ `2026-04-01`
- 关键词：`AI / 媒体 / AIGC / 新闻生产`
- 白名单信源：5 条（见 `demo_input.json`）

## 2. 生成模式

- LLM 版：`REPORT_WRITING_MODE=llm`
- Rule 版：`REPORT_WRITING_MODE=rule`

## 3. 输出章节概览

固定七章均完整输出：

1. 本期聚焦
2. 全球瞭望
3. 案例工场
4. 趋势雷达
5. 实战锦囊
6. 数据可视化
7. 附录

## 4. citation 情况

- LLM 版：`citation_warning_count=0`（最终验收）
- Rule 版：`citation_warning_count=0`
- 支持段落级来源 URL 与证据片段展示

## 5. 图表情况

- 输出图表类型：`bar` / `pie`（以及基础聚合图）
- 数据来源：章节分布、主题分布、机构/地区分布

## 6. 客户演示建议流程

1. 展示任务创建页并导入 `demo_input.json` 参数
2. 运行 LLM 模式并展示 `demo_output_llm.md`
3. 切换 rule 模式并展示 `demo_output_rule.md`
4. 对比建议文本差异与 citation 一致性
5. 展示 charts 接口与报告脚注追溯能力
