# 本地启动说明（MVP）

## 1. 前置条件

- Docker Desktop
- Node.js 20+
- Python 3.11（如需本地直跑，3.13 暂不推荐）

## 2. 使用 Docker 一键启动

1. 根目录复制环境变量：
   - `.env.example` -> `.env`
2. 执行：
   - `docker compose up --build`
3. 验证：
> 如果出现 `dockerDesktopLinuxEngine` 连接失败，说明 Docker daemon 未启动。请先启动 Docker Desktop 再重试。
   - `http://localhost:8000/healthz`
   - `http://localhost:3000`
4. 默认登录：
   - `owner@demo.com / demo1234`

## 3. 环境变量说明

- `POSTGRES_*`：数据库配置
- `JWT_SECRET`：JWT 签名密钥
- `REPORT_WRITING_MODE`：写作模式，默认 `llm`，可切换为 `rule`
- `LITELLM_BASE_URL` / `LITELLM_MODEL` / `LITELLM_API_KEY`：LLM 网关配置
- `CHROMA_PERSIST_DIR`：向量库本地持久化目录

### 写作回退策略

- 当 `REPORT_WRITING_MODE=llm` 时，仅“章节摘要写作”和“对总台建议”走 LLM。
- 以下链路始终走规则逻辑：抓取、去重、基础标签识别、citation 主绑定。
- 若 LLM 不可用（缺配置）/超时/报错，自动降级到 `rule`，任务不中断。
- 每次任务可在 `stats` 看到：
  - `writing_mode_used`
  - `llm_summary_count`
  - `llm_fallback_count`
  - `llm_error_count`
  - `section_generation_mode.llm_called`
  - `section_generation_mode.section_writing_mode`

## 4. Demo 数据

数据库初始化会自动创建：

- 一个母账号组织
- 一个母账号用户（`owner@demo.com`）
- 一个默认角色集（owner/member）

密码默认写在 `apps/api/db/schema.sql` 的 seed 区（MVP 占位，后续改为安全注入）。

## 5. 运行测试

- `python -m pytest apps/api/tests -q`

## 6. 交付文档入口

- 部署：`docs/deployment.md`
- 本地开发：`docs/local-development.md`
- 环境变量：`docs/env.md`
- 上线检查：`docs/production-checklist.md`
