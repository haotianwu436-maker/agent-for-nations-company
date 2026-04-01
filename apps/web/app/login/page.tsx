"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export default function LoginPage() {
  const [email, setEmail] = useState("owner@demo.local");
  const [password, setPassword] = useState("demo1234");
  const [message, setMessage] = useState("");

  async function handleLogin() {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) {
      setMessage("登录失败");
      return;
    }
    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    setMessage("登录成功");
  }

  return (
    <div className="card">
      <h2>登录</h2>
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="邮箱" />
      <br />
      <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码" type="password" />
      <br />
      <button onClick={handleLogin}>登录</button>
      <p>{message}</p>
      <a href="/jobs/new">去创建任务</a>
    </div>
  );
}
