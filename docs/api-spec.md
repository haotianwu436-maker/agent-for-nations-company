# API 规格（MVP）

基础前缀：`/api/v1`

## 1) 认证

### `POST /auth/login`

请求：

```json
{
  "email": "owner@example.com",
  "password": "Passw0rd!"
}
```

响应：

```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "organization_id": "uuid",
    "role": "owner"
  }
}
```

### `POST /auth/create-child`

仅 `owner` 可调用。

请求：

```json
{
  "email": "member@example.com",
  "password": "Passw0rd!",
  "display_name": "子账号A"
}
```

响应：

```json
{
  "id": "uuid",
  "email": "member@example.com",
  "role": "member"
}
```

## 2) 报告任务

### `POST /report-jobs`

请求：

```json
{
  "report_type": "weekly",
  "keywords": ["AI媒体", "AIGC"],
  "time_range_start": "2026-03-25T00:00:00Z",
  "time_range_end": "2026-04-01T00:00:00Z",
  "source_whitelist": ["https://example.com/feed"],
  "template_name": "global-media-weekly-v1",
  "language": "zh-CN"
}
```

响应：

```json
{
  "id": "uuid",
  "status": "pending",
  "created_at": "2026-04-01T10:00:00Z"
}
```

### `GET /report-jobs`

查询参数：`page`、`page_size`、`status`

响应：

```json
{
  "items": [
    {
      "id": "uuid",
      "report_type": "weekly",
      "status": "running",
      "created_at": "2026-04-01T10:00:00Z"
    }
  ],
  "total": 1
}
```

### `GET /report-jobs/{job_id}`

响应：

```json
{
  "id": "uuid",
  "status": "success",
  "report_type": "weekly",
  "status_message": "assemble_report completed",
  "started_at": "2026-04-01T10:00:10Z",
  "finished_at": "2026-04-01T10:00:21Z",
  "error_message": null
}
```

### `POST /report-jobs/{job_id}/run`

响应：

```json
{
  "id": "uuid",
  "status": "running"
}
```

## 3) 报告内容

### `GET /reports/{job_id}/markdown`

响应：

```json
{
  "job_id": "uuid",
  "markdown": "# 本期聚焦\n..."
}
```

### `GET /reports/{job_id}/sections`

响应：

```json
{
  "job_id": "uuid",
  "sections": [
    {
      "name": "本期聚焦",
      "content": "..."
    }
  ]
}
```

### `GET /reports/{job_id}/charts`

响应：

```json
{
  "job_id": "uuid",
  "charts": [
    {
      "chart_type": "bar",
      "title": "来源媒体分布",
      "labels": ["Reuters"],
      "values": [3],
      "notes": "按抓取来源聚合"
    }
  ]
}

### `GET /reports/{job_id}/citations`

响应：

```json
{
  "job_id": "uuid",
  "citations": [
    {
      "section_key": "focus",
      "paragraph_index": 0,
      "claim_text": "某条关键结论",
      "source_url": "https://example.com",
      "quote_text": "证据摘录",
      "validation_status": "valid"
    }
  ]
}
```

## 4) 任务统计（report_jobs.stats）

任务完成后，`report_jobs.stats` 会写入可观测字段，重点包括：

- `writing_mode_used`：本次实际使用模式（`llm` 或 `rule`）
- `llm_summary_count`：LLM 成功生成的段落数量
- `llm_fallback_count`：LLM 调用失败后回退次数
- `llm_error_count`：LLM 调用错误次数
- `section_generation_mode.llm_called`：本次任务是否真正调用过 LLM
- `section_generation_mode.section_writing_mode`：章节维度写作模式（`llm/rule/mixed`）
