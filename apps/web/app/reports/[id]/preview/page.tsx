"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export default function ReportPreviewPage({ params }: { params: { id: string } }) {
  const [markdown, setMarkdown] = useState("加载中...");
  const [brand, setBrand] = useState({ name: "媒体行业 AI 资讯报告撰写智能体", logo_url: "" });

  useEffect(() => {
    const token = localStorage.getItem("token");
    fetch(`${API_BASE}/reports/${params.id}/markdown`, {
      headers: { Authorization: `Bearer ${token || ""}` }
    })
      .then((r) => r.json())
      .then((d) => setMarkdown(d.markdown || "无内容"))
      .catch(() => setMarkdown("加载失败"));
    fetch(`${API_BASE}/organization/branding`, {
      headers: { Authorization: `Bearer ${token || ""}` }
    })
      .then((r) => r.json())
      .then((d) => setBrand(d || brand))
      .catch(() => setBrand(brand));
  }, [params.id]);

  return (
    <div className="card">
      <div className="brand-header">
        {brand.logo_url ? <img src={brand.logo_url} alt="logo" className="brand-logo" /> : null}
        <h2>{brand.name}</h2>
      </div>
      <h2>报告预览</h2>
      <pre style={{ whiteSpace: "pre-wrap" }}>{markdown}</pre>
      <a href="/jobs">返回任务列表</a>
    </div>
  );
}
