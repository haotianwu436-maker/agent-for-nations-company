# 本地开发指南

本指南用于研发同学接手与日常迭代。**当前阶段禁止改动主链路架构**，以交付版稳定为优先。

## 1. 开发模式建议

- 推荐：`Postgres Docker + API/Web 本机`
- 优点：启动快、日志可读、便于调试断点

## 2. 初次启动

1. 复制 `.env.example` 为 `.env`
2. 启动数据库：
   - `docker compose up -d postgres`
3. 导入数据库：
   - `Get-Content "apps/api/db/schema.sql" | docker exec -i ai48-postgres-1 psql -U media_ai -d media_ai`
4. 启动 API 与 Web（见 `docs/deployment.md`）

## 3. 开发验证流程

1. 登录接口验证
2. 创建报告任务
3. 执行任务
4. 查看 markdown/charts/citations
5. 前端页面联调验证

## 4. 模式切换验证

- `llm` 模式：`REPORT_WRITING_MODE=llm`
- `rule` 模式：`REPORT_WRITING_MODE=rule`

建议每次改动后至少跑一次 `rule`，确保回退稳定。

## 5. 测试

```powershell
python -m pytest apps/api/tests -q
```

## 6. 开发注意事项

- 不要提交真实 API Key
- 不要提交 `.next`、`node_modules`、本地日志
- 仅在交付阻塞级问题时修复主链路代码
- 新需求请先记录在 `docs/progress.md`，再评估迭代批次
