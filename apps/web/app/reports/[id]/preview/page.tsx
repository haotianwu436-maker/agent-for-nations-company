"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "../../../../lib/api-base";
import { DEFAULT_BRAND } from "../../../../lib/default-brand";

export default function ReportPreviewPage({ params }: { params: { id: string } }) {
  const [markdown, setMarkdown] = useState("加载中...");
  const [brand, setBrand] = useState({ name: DEFAULT_BRAND.name, logo_url: DEFAULT_BRAND.logo_url });
  const [citationsCount, setCitationsCount] = useState(0);
  const [chartsCount, setChartsCount] = useState(0);

  useEffect(() => {
    const token = localStorage.getItem("token");
    Promise.all([
      fetch(`${getApiBase()}/reports/${params.id}/markdown`, { headers: { Authorization: `Bearer ${token || ""}` } }),
      fetch(`${getApiBase()}/reports/${params.id}/citations`, { headers: { Authorization: `Bearer ${token || ""}` } }),
      fetch(`${getApiBase()}/reports/${params.id}/charts`, { headers: { Authorization: `Bearer ${token || ""}` } }),
      fetch(`${getApiBase()}/organization/branding`, { headers: { Authorization: `Bearer ${token || ""}` } })
    ])
      .then(async ([mdRes, cRes, chartRes, bRes]) => {
        setMarkdown(mdRes.ok ? (await mdRes.json()).markdown || "无内容" : "加载失败");
        setCitationsCount(cRes.ok ? ((await cRes.json()).citations || []).length : 0);
        setChartsCount(chartRes.ok ? ((await chartRes.json()).charts || []).length : 0);
        setBrand(bRes.ok ? await bRes.json() : brand);
      })
      .catch(() => setMarkdown("加载失败"));
  }, [params.id]);

  return (
    <div>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div className="row" style={{ alignItems: "center" }}>
            {brand.logo_url ? <img src={brand.logo_url} alt="logo" className="brand-chip-logo" /> : null}
            <div>
              <h2 style={{ margin: 0 }}>{brand.name}</h2>
              <div style={{ color: "#6b7280", fontSize: 12 }}>客户演示预览页</div>
            </div>
          </div>
          <a className="btn" href={`/jobs/${params.id}`}>返回验收驾驶舱</a>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <span className="status-pill">citations: {citationsCount}</span>
          <span className="status-pill">charts: {chartsCount}</span>
        </div>
      </div>

      <div className="card">
        <h2>报告正文</h2>
        <div className="report-section-content">{markdown}</div>
      </div>
    </div>
  );
}
