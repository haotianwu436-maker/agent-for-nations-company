"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export default function NewJobPage() {
  const [keywords, setKeywords] = useState("AI媒体,AIGC");
  const [message, setMessage] = useState("");

  async function handleCreate() {
    const token = localStorage.getItem("token");
    const now = new Date();
    const start = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    const res = await fetch(`${API_BASE}/report-jobs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token || ""}`
      },
      body: JSON.stringify({
        report_type: "weekly",
        keywords: keywords.split(",").map((x) => x.trim()),
        time_range_start: start.toISOString(),
        time_range_end: now.toISOString(),
        source_whitelist: ["https://example.com/feed"],
        template_name: "global-media-weekly-v1",
        language: "zh-CN"
      })
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(`创建失败: ${data.detail || "unknown"}`);
      return;
    }
    setMessage(`任务已创建: ${data.id}`);
  }

  return (
    <div className="card">
      <h2>新建任务</h2>
      <label>关键词（逗号分隔）</label>
      <br />
      <input value={keywords} onChange={(e) => setKeywords(e.target.value)} />
      <br />
      <button onClick={handleCreate}>创建任务</button>
      <p>{message}</p>
      <a href="/jobs">去任务列表</a>
    </div>
  );
}
