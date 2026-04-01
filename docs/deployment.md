# 部署说明（交付版）

本文档用于演示环境与评审环境部署。当前推荐方案：**PostgreSQL 使用 Docker，API/Web 本机运行**。

## 1. 推荐部署方式

### 必选项

- PostgreSQL 16（推荐 Docker）
- Python 3.11（API）
- Node.js 20（Web）
- 完整配置 `.env`

### 可选项

- API/Web 使用 Docker Compose 全容器运行
- LiteLLM 接入不同供应商（OpenAI 兼容接口）

## 2. 启动前准备

1. 复制环境变量：`.env.example -> .env`
2. 配置关键项：
   - `DATABASE_URL`
   - `REPORT_WRITING_MODE`（默认 `llm`）
   - `LITELLM_BASE_URL` / `LITELLM_MODEL` / `LITELLM_API_KEY`

## 3. 数据库初始化（必须）

1. 启动 PostgreSQL 容器：
   - `docker compose up -d postgres`
2. 导入 schema：
   - `Get-Content "apps/api/db/schema.sql" | docker exec -i ai48-postgres-1 psql -U media_ai -d media_ai`

## 4. 启动顺序（推荐）

1. 启动 PostgreSQL
2. 启动 API
3. 启动 Web
4. 执行健康检查与登录验证

## 5. 服务启动命令

### API（本机）

```powershell
cd apps/api
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Web（本机）

```powershell
cd apps/web
npm install
npm run dev
```

## 6. 健康检查

- API：`GET http://127.0.0.1:8000/healthz`
- API 文档：`http://127.0.0.1:8000/docs`
- Web：`http://127.0.0.1:3000`

## 7. LLM 模式与回退模式

- `REPORT_WRITING_MODE=llm`：
  - 章节摘要与建议优先走 LLM
  - LLM 不可用/超时/报错自动回退 rule
- `REPORT_WRITING_MODE=rule`：
  - 全规则写作，不依赖 LLM

## 8. 全 Docker 运行（可选）

```powershell
docker compose up --build
```

说明：全 Docker 更利于演示一键启动，但本地排障与开发迭代建议采用“DB Docker + API/Web 本机”模式。

## 9. 常见故障排查

- **Docker 未启动**：先打开 Docker Desktop，再执行 compose。
- **API 无法连库**：检查 `DATABASE_URL` 与容器端口映射。
- **LLM 不生效**：检查 `REPORT_WRITING_MODE=llm` 与 `LITELLM_*` 是否正确。
- **登录失败**：确认 schema 已导入，并使用 demo 账号。

## 10. 演示环境建议配置

- CPU 4 核 / 内存 8GB / SSD 20GB+
- 网络可访问配置的 LLM 网关地址
- Python 3.11 + Node 20 + Docker Desktop 最新稳定版
