"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getApiBase } from "../../lib/api-base";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("owner@demo.com");
  const [password, setPassword] = useState("demo1234");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiHint, setApiHint] = useState("");

  useEffect(() => setApiHint(getApiBase()), []);

  async function handleLogin() {
    setLoading(true);
    setMessage("");
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 20000);
    try {
      const res = await fetch(`${getApiBase()}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
        signal: ctrl.signal
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((x: { msg?: string }) => x.msg || JSON.stringify(x)).join("; ")
              : data.detail
                ? JSON.stringify(data.detail)
                : "";
        setMessage(`登录失败（HTTP ${res.status}）${detail ? `：${detail}` : ""}`);
        return;
      }
      if (!data.access_token) {
        setMessage("登录失败：接口未返回 access_token，请检查后端版本。");
        return;
      }
      localStorage.setItem("token", data.access_token);
      setMessage("登录成功，正在跳转…");
      router.push("/jobs/new");
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") {
        setMessage(
          "登录超时（20s）。请先确认：1）API 已启动；2）启动 API 的终端里已设置 DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5432/media_ai（不要用 localhost，否则登录可能一直卡住）。"
        );
      } else {
        setMessage(
          `登录失败：无法连接 ${getApiBase()}。请确认：1）本机已启动 API；2）新标签页打开 http://127.0.0.1:8000/healthz 应显示 {"status":"ok"}；3）若 .env 里写了 NEXT_PUBLIC_API_BASE_URL 指向错误地址也会失败。`
        );
      }
    } finally {
      window.clearTimeout(timer);
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <h2>登录</h2>
      <p className="auth-subtitle">进入 AI 报告验收驾驶舱</p>
      <div className="auth-hint">
        默认账号：owner@demo.com / demo1234
        <div style={{ marginTop: 6, fontSize: 12, color: "#6b7280" }}>
          接口地址：{apiHint || "加载中…"}（未配置 env 时为同页 /proxy/v1，由 Next 服务端转发到本机 :8000）
        </div>
      </div>
      <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="邮箱" />
      <input className="input" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码" type="password" />
      <button type="button" className="btn btn-primary auth-btn" onClick={handleLogin} disabled={loading}>
        {loading ? "登录中…" : "登录"}
      </button>
      <p>{message}</p>
      <a href="/jobs/new">跳过登录去创建任务</a>
    </div>
  );
}
