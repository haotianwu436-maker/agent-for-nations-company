"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<any>(null);
  const [markdown, setMarkdown] = useState("");
  const [charts, setCharts] = useState<any[]>([]);
  const [citations, setCitations] = useState<any[]>([]);
  const [message, setMessage] = useState("");

  async function loadAll() {
    const token = localStorage.getItem("token");
    try {
      const [jobRes, mdRes, chartRes, citeRes] = await Promise.all([
        fetch(`${API_BASE}/report-jobs/${params.id}`, { headers: { Authorization: `Bearer ${token || ""}` } }),
        fetch(`${API_BASE}/reports/${params.id}/markdown`, { headers: { Authorization: `Bearer ${token || ""}` } }),
        fetch(`${API_BASE}/reports/${params.id}/charts`, { headers: { Authorization: `Bearer ${token || ""}` } }),
        fetch(`${API_BASE}/reports/${params.id}/citations`, { headers: { Authorization: `Bearer ${token || ""}` } })
      ]);
      setJob(jobRes.ok ? await jobRes.json() : null);
      setMarkdown(mdRes.ok ? (await mdRes.json()).markdown || "" : "");
      setCharts(chartRes.ok ? (await chartRes.json()).charts || [] : []);
      setCitations(citeRes.ok ? (await citeRes.json()).citations || [] : []);
    } catch {
      setJob(null);
      setMarkdown("");
      setCharts([]);
      setCitations([]);
    }
  }

  useEffect(() => {
    loadAll();
  }, [params.id]);

  async function runJob() {
    const token = localStorage.getItem("token");
    const res = await fetch(`${API_BASE}/report-jobs/${params.id}/run`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token || ""}` }
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(`执行失败: ${data.detail || "unknown"}`);
      return;
    }
    setMessage(`执行完成: ${data.status}`);
    await loadAll();
  }

  return (
    <div className="card">
      <h2>任务详情</h2>
      <pre>{job ? JSON.stringify(job, null, 2) : "暂无任务信息"}</pre>
      <button onClick={runJob}>执行任务</button>
      <p>{message}</p>
      <h3>报告 Markdown</h3>
      <pre style={{ whiteSpace: "pre-wrap" }}>{markdown || "暂无报告内容"}</pre>
      <h3>Citations</h3>
      {citations.length === 0 ? (
        <p>暂无引用</p>
      ) : (
        <ul>
          {citations.map((c, i) => (
            <li key={`${c.section_key}-${i}`}>
              [{c.section_key}] {c.claim_text || "未命名"} | {c.source_url || "无来源"}
            </li>
          ))}
        </ul>
      )}
      <h3>Charts</h3>
      {charts.length === 0 ? (
        <p>暂无图表</p>
      ) : (
        <pre>{JSON.stringify(charts, null, 2)}</pre>
      )}
      <a href={`/reports/${params.id}/preview`}>查看报告预览</a>
    </div>
  );
}
