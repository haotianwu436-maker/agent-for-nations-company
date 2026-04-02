"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getApiBase } from "../../../lib/api-base";

export default function NewJobPage() {
  const router = useRouter();
  const [keywords, setKeywords] = useState("AI,AIGC,media,policy,trend,case");
  const [sources, setSources] = useState(
    "https://arstechnica.com/\nhttps://www.anthropic.com/news/announcing-our-updated-responsible-scaling-policy"
  );
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleCreate(runNow: boolean) {
    const token = localStorage.getItem("token");
    if (!token) {
      setMessage("请先登录");
      router.push("/login");
      return;
    }
    setLoading(true);
    const now = new Date();
    const start = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    try {
      const res = await fetch(`${getApiBase()}/report-jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          report_type: "weekly",
          keywords: keywords.split(",").map((x) => x.trim()).filter(Boolean),
          time_range_start: start.toISOString(),
          time_range_end: now.toISOString(),
          source_whitelist: sources.split("\n").map((x) => x.trim()).filter(Boolean),
          template_name: "global-media-weekly-v1",
          language: "zh-CN"
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage(`创建失败: ${data.detail || "unknown"}`);
        return;
      }
      if (runNow) {
        const runRes = await fetch(`${getApiBase()}/report-jobs/${data.id}/run`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` }
        });
        const runData = await runRes.json().catch(() => ({}));
        if (!runRes.ok) {
          setMessage(`任务已创建(${data.id})，但执行失败: ${runData.detail || "unknown"}`);
          return;
        }
        setMessage(`任务已创建并触发执行: ${data.id}`);
      } else {
        setMessage(`任务已创建: ${data.id}`);
      }
      router.push(`/jobs/${data.id}`);
    } catch {
      setMessage("请求失败，请检查 API 是否在线");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h2>新建任务</h2>
      <p>默认参数已对齐验收样例，可直接“一键创建并执行”。</p>
      <label>关键词（逗号分隔）</label>
      <br />
      <input className="input" value={keywords} onChange={(e) => setKeywords(e.target.value)} />
      <br />
      <label>信源白名单（每行一个 URL）</label>
      <br />
      <textarea className="textarea" rows={5} value={sources} onChange={(e) => setSources(e.target.value)} />
      <br />
      <div className="row">
        <button className="btn" disabled={loading} onClick={() => handleCreate(false)}>仅创建任务</button>
        <button className="btn btn-primary" disabled={loading} onClick={() => handleCreate(true)}>创建并立即执行</button>
      </div>
      <p>{message}</p>
      <a href="/jobs">去任务列表</a>
    </div>
  );
}
