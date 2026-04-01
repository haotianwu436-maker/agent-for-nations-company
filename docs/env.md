# 环境变量说明（交付版）

## 1. 配置文件

- 示例：`.env.example`
- 本地实际：`.env`（禁止提交）

## 2. 变量清单

| 变量名 | 默认值 | 必填 | 作用范围 | 说明 |
|---|---|---|---|---|
| `POSTGRES_DB` | `media_ai` | 是 | Docker DB | 数据库名 |
| `POSTGRES_USER` | `media_ai` | 是 | Docker DB | 数据库用户 |
| `POSTGRES_PASSWORD` | `media_ai` | 是 | Docker DB | 数据库密码（生产必须替换） |
| `POSTGRES_PORT` | `5432` | 是 | Docker DB | 数据库端口 |
| `DATABASE_URL` | `postgresql+psycopg://...` | 是 | API | API 连接数据库 |
| `API_PORT` | `8000` | 是 | API/Web | API 暴露端口 |
| `WEB_PORT` | `3000` | 是 | Web | Web 暴露端口 |
| `APP_NAME` | `media-ai-api` | 否 | API | 服务名 |
| `APP_ENV` | `dev` | 否 | API | 运行环境标识 |
| `LOG_LEVEL` | `INFO` | 否 | API | 日志级别 |
| `JWT_SECRET` | `replace_me` | 是 | API | JWT 签名密钥 |
| `JWT_EXPIRE_MINUTES` | `120` | 否 | API | Token 有效期（分钟） |
| `REPORT_WRITING_MODE` | `llm` | 是 | Orchestrator | 写作模式：`llm`/`rule` |
| `LITELLM_BASE_URL` | `https://api.moonshot.cn/v1` | llm 模式必填 | LLM | LLM 网关地址 |
| `LITELLM_MODEL` | `openai/moonshot-v1-8k` | llm 模式必填 | LLM | 模型名 |
| `LITELLM_API_KEY` | `replace_me` | llm 模式必填 | LLM | API Key（绝不能入库） |
| `LLM_TIMEOUT_SECONDS` | `30` | 否 | LLM | 预留超时配置说明 |
| `CHROMA_PERSIST_DIR` | `/data/chroma` | 否 | Retrieval | 向量持久化目录（预留） |

## 3. llm / rule 依赖差异

### `REPORT_WRITING_MODE=llm`

- 需要：`LITELLM_BASE_URL`、`LITELLM_MODEL`、`LITELLM_API_KEY`
- 仅用于：章节摘要写作、对总台建议生成
- 自动回退：LLM 不可用/超时/报错 -> rule

### `REPORT_WRITING_MODE=rule`

- 不依赖 `LITELLM_*`
- 适合离线、无密钥、稳定回归场景

## 4. 安全提醒

- 绝不能提交：`LITELLM_API_KEY`、生产数据库密码、生产 JWT 密钥
- 建议使用密钥管理平台或 CI/CD Secret 注入
- 建议定期轮换 LLM Key 与数据库凭据

## 5. Demo 用户说明

- 演示账户（由 schema 初始化）：`owner@demo.com / demo1234`
- 仅用于本地演示，不可直接用于生产
