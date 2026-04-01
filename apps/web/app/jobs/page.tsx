"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

type Job = {
  id: string;
  status: string;
  report_type: string;
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [brand, setBrand] = useState({ name: "媒体行业 AI 资讯报告撰写智能体", logo_url: "" });
  const [brandMsg, setBrandMsg] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    Promise.all([
      fetch(`${API_BASE}/report-jobs`, { headers: { Authorization: `Bearer ${token || ""}` } }),
      fetch(`${API_BASE}/organization/branding`, { headers: { Authorization: `Bearer ${token || ""}` } })
    ])
      .then(async ([jobsRes, brandRes]) => {
        const jobsData = jobsRes.ok ? await jobsRes.json() : { items: [] };
        const brandData = brandRes.ok ? await brandRes.json() : brand;
        setJobs(jobsData.items || []);
        setBrand(brandData || brand);
      })
      .catch(() => setJobs([]));
  }, []);

  async function saveBranding() {
    const token = localStorage.getItem("token");
    const res = await fetch(`${API_BASE}/organization/branding`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token || ""}`
      },
      body: JSON.stringify(brand)
    });
    setBrandMsg(res.ok ? "品牌配置已保存" : "品牌配置保存失败");
  }

  return (
    <div className="card">
      <div className="brand-header">
        {brand.logo_url ? <img src={brand.logo_url} alt="logo" className="brand-logo" /> : null}
        <h2>{brand.name}</h2>
      </div>
      <div className="card">
        <h3>品牌配置</h3>
        <label>单位名称</label>
        <input value={brand.name} onChange={(e) => setBrand({ ...brand, name: e.target.value })} />
        <label>Logo URL</label>
        <input value={brand.logo_url} onChange={(e) => setBrand({ ...brand, logo_url: e.target.value })} />
        <button onClick={saveBranding}>保存品牌配置</button>
        <p>{brandMsg}</p>
      </div>
      <h2>任务列表</h2>
      <a href="/jobs/new">+ 新建任务</a>
      <ul>
        {jobs.map((j) => (
          <li key={j.id}>
            <span>{j.report_type}</span> | <span>{j.status}</span> | <a href={`/jobs/${j.id}`}>详情</a>
          </li>
        ))}
      </ul>
    </div>
  );
}
