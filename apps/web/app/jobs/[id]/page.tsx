"use client";

import { useEffect, useState } from "react";
import { Line, LineChart, Pie, PieChart, Bar, BarChart, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend } from "recharts";
import { getApiBase } from "../../../lib/api-base";
import { DEFAULT_BRAND } from "../../../lib/default-brand";

const REQUIRED_SECTIONS = ["本期聚焦", "全球瞭望", "案例工场", "趋势雷达", "实战锦囊", "数据可视化", "附录"];
const PIE_COLORS = ["#111827", "#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

function splitMarkdownSections(md: string): Record<string, string> {
  if (!md) return {};
  const result: Record<string, string> = {};
  const parts = md.split(/^##\s+/m).filter(Boolean);
  for (const part of parts) {
    const lines = part.split("\n");
    const title = (lines.shift() || "").trim();
    if (!title) continue;
    result[title] = lines.join("\n").trim();
  }
  return result;
}

function chartDataFromRaw(chart: any) {
  const labels = chart?.labels || [];
  const values = chart?.values || [];
  return labels.map((label: string, i: number) => ({ name: label, value: Number(values[i] || 0) }));
}

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<any>(null);
  const [brand, setBrand] = useState({ name: DEFAULT_BRAND.name, logo_url: DEFAULT_BRAND.logo_url });
  const [markdown, setMarkdown] = useState("");
  const [charts, setCharts] = useState<any[]>([]);
  const [citations, setCitations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  async function loadAll() {
    const token = localStorage.getItem("token");
    try {
      const [jobRes, mdRes, chartRes, citeRes] = await Promise.all([
        fetch(`${getApiBase()}/report-jobs/${params.id}`, { headers: { Authorization: `Bearer ${token || ""}` } }),
        fetch(`${getApiBase()}/reports/${params.id}/markdown`, { headers: { Authorization: `Bearer ${token || ""}` } }),
        fetch(`${getApiBase()}/reports/${params.id}/charts`, { headers: { Authorization: `Bearer ${token || ""}` } }),
        fetch(`${getApiBase()}/reports/${params.id}/citations`, { headers: { Authorization: `Bearer ${token || ""}` } })
      ]);
      const brandRes = await fetch(`${getApiBase()}/organization/branding`, { headers: { Authorization: `Bearer ${token || ""}` } });
      setJob(jobRes.ok ? await jobRes.json() : null);
      setMarkdown(mdRes.ok ? (await mdRes.json()).markdown || "" : "");
      setCharts(chartRes.ok ? (await chartRes.json()).charts || [] : []);
      setCitations(citeRes.ok ? (await citeRes.json()).citations || [] : []);
      setBrand(brandRes.ok ? await brandRes.json() : brand);
    } catch {
      setJob(null);
      setMarkdown("");
      setCharts([]);
      setCitations([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, [params.id]);

  async function runJob() {
    const token = localStorage.getItem("token");
    const res = await fetch(`${getApiBase()}/report-jobs/${params.id}/run`, {
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

  const sections = splitMarkdownSections(markdown);
  const stats = job?.stats || {};
  const citationWarnings = (stats.citation_metrics?.warnings || []).length;

  return (
    <div className="two-col">
      <div className="job-detail-main">
        <div className="card job-overview-card">
          <div className="job-overview-top">
            <div className="job-overview-brand">
              {brand.logo_url ? <img src={brand.logo_url} alt="logo" className="brand-chip-logo" /> : null}
              <div className="job-overview-brand-text">
                <div className="job-overview-title">{brand.name}</div>
                <div className="job-overview-id">{params.id}</div>
              </div>
            </div>
            <div className="job-overview-actions">
              <a className="btn btn-sm" href={`${getApiBase()}/reports/${params.id}/export?format=docx`} target="_blank" rel="noreferrer">DOCX</a>
              <a className="btn btn-sm" href={`${getApiBase()}/reports/${params.id}/export?format=pdf`} target="_blank" rel="noreferrer">PDF</a>
            </div>
          </div>

          <div className="metric-grid-compact">
            <div className="metric-compact"><div className="metric-label">状态</div><div className="metric-value">{job?.status || "-"}</div></div>
            <div className="metric-compact"><div className="metric-label">Writing Mode</div><div className="metric-value">{stats.writing_mode_used || "-"}</div></div>
            <div className="metric-compact"><div className="metric-label">LLM Fallback</div><div className="metric-value">{stats.llm_fallback_count ?? 0}</div></div>
            <div className="metric-compact"><div className="metric-label">Citation Warn</div><div className="metric-value">{citationWarnings}</div></div>
          </div>

          <div className="job-overview-meta">
            时间范围：{job?.time_range_start || "-"} ~ {job?.time_range_end || "-"}
          </div>

          <div className="job-overview-toolbar">
            <button className="btn btn-primary btn-sm" type="button" onClick={runJob}>执行任务</button>
            <button className="btn btn-sm" type="button" onClick={loadAll}>刷新</button>
            <a className="btn btn-sm" href={`/reports/${params.id}/preview`}>演示预览</a>
          </div>
          {message ? <p className="job-overview-msg">{message}</p> : null}
        </div>

        <div className="card report-master-card">
          <h2>报告正文 · 固定七章</h2>
          {loading ? <div className="empty">加载中...</div> : null}
          <div className="report-prose">
            {REQUIRED_SECTIONS.map((title) => (
              <div className="card report-section" key={title} id={`sec-${title}`}>
                <h3>{title}</h3>
                {sections[title] ? (
                  <div className="report-section-content">{sections[title]}</div>
                ) : (
                  <div className="empty">本章暂无内容（系统已保留章节结构）</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="section-nav">
        <div className="card acceptance-rail-card">
          <h3>章节</h3>
          <div className="acceptance-nav-links">
            {REQUIRED_SECTIONS.map((title) => (
              <a key={title} href={`#sec-${title}`}>{title}</a>
            ))}
          </div>
        </div>

        <div className="card acceptance-rail-card">
          <h3>引用与证据</h3>
          {citations.length === 0 ? <div className="empty">暂无引用</div> : null}
          {citations.map((c, i) => (
            <details key={`${c.section_key}-${i}`} style={{ marginBottom: 8 }}>
              <summary style={{ fontSize: 13 }}>[{c.section_key}] {c.validation_status}</summary>
              <div style={{ fontSize: 12, color: "#374151", marginTop: 6 }}>
                <div><a href={`#sec-${c.section_key}`}>跳转章节</a></div>
                <div>source: <a href={c.source_url} target="_blank" rel="noreferrer">{c.source_url}</a></div>
                <div>evidence: {c.evidence_snippet || "-"}</div>
              </div>
            </details>
          ))}
        </div>

        <div className="card acceptance-rail-card">
          <h3>图表</h3>
          {charts.length === 0 ? <div className="empty">暂无图表</div> : null}
          {charts.map((chart, idx) => {
            const data = chartDataFromRaw(chart);
            return (
              <div className="chart-block" key={`${chart.title}-${idx}`}>
                <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 13 }}>{chart.title}</div>
                <div style={{ width: "100%", height: 200 }}>
                  <ResponsiveContainer>
                    {chart.chart_type === "line" ? (
                      <LineChart data={data}><XAxis dataKey="name" hide /><YAxis /><Tooltip /><Line dataKey="value" stroke="#2563eb" /></LineChart>
                    ) : chart.chart_type === "pie" ? (
                      <PieChart>
                        <Pie data={data} dataKey="value" nameKey="name" outerRadius={64}>
                          {data.map((_: any, i: number) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    ) : (
                      <BarChart data={data}><XAxis dataKey="name" hide /><YAxis /><Tooltip /><Bar dataKey="value" fill="#111827" /></BarChart>
                    )}
                  </ResponsiveContainer>
                </div>
                <div className="chart-caption">{chart.notes || "图表解读：该图展示了本任务的结构化统计结果。"}</div>
              </div>
            );
          })}
        </div>

        <div className="card acceptance-rail-card">
          <h3>系统状态</h3>
          <div className="stats-kv">
            <div>kb_ready: {String(stats.kb_ready ?? "-")}</div>
            <div>kb_chunks_loaded: {stats.kb_chunks_loaded ?? "-"}</div>
            <div>docling_used: {String(stats.docling_used ?? "-")}</div>
            <div>tools_called: {String(stats.tool_stats?.tools_called ?? "-")}</div>
            <div>archive_verify_count: {stats.tool_stats?.archive_verify_count ?? "-"}</div>
            <div>aigc_mock_count: {stats.tool_stats?.aigc_mock_count ?? "-"}</div>
            <div>entry_pages: {stats.crawl_meta?.entry_pages ?? "-"}</div>
            <div>first_level_links: {stats.crawl_meta?.first_level_links ?? "-"}</div>
            <div>effective_targets: {stats.crawl_meta?.effective_targets ?? "-"}</div>
            <div>effective_success: {stats.crawl_meta?.effective_success ?? "-"}</div>
            <div>source_filter: {JSON.stringify(stats.crawl_meta?.source_filter || {})}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
