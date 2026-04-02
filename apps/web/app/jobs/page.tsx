"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "../../lib/api-base";
import { DEFAULT_BRAND } from "../../lib/default-brand";

type Job = {
  id: string;
  status: string;
  report_type: string;
  created_at?: string;
  time_range_start?: string;
  time_range_end?: string;
  stats?: Record<string, any>;
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [brand, setBrand] = useState({ name: DEFAULT_BRAND.name, logo_url: DEFAULT_BRAND.logo_url });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    Promise.all([
      fetch(`${getApiBase()}/report-jobs`, { headers: { Authorization: `Bearer ${token || ""}` } }),
      fetch(`${getApiBase()}/organization/branding`, { headers: { Authorization: `Bearer ${token || ""}` } })
    ])
      .then(async ([jobsRes, brandRes]) => {
        const jobsData = jobsRes.ok ? await jobsRes.json() : { items: [] };
        const brandData = brandRes.ok ? await brandRes.json() : brand;
        setJobs(jobsData.items || []);
        setBrand(brandData || brand);
      })
      .catch(() => setJobs([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="card">
        <h2>任务列表</h2>
        <p>用于演示和验收：可直接查看状态、写作模式、时间范围并进入验收页。</p>
        <div className="row">
          <a className="btn btn-primary" href="/jobs/new">+ 新建任务</a>
          <a className="btn" href="/brand">品牌配置</a>
          <a className="btn" href="/knowledge">知识库</a>
        </div>
      </div>

      <div className="card">
        <strong>品牌归属：</strong> {brand.name}
      </div>

      <div className="jobs-list">
        {loading ? <div className="card">加载中...</div> : null}
        {!loading && jobs.length === 0 ? <div className="card empty">暂无任务，请先创建任务。</div> : null}
        {jobs.map((j) => {
          const stats = j.stats || {};
          const mode = stats.writing_mode_used || "-";
          return (
            <a className="job-item" key={j.id} href={`/jobs/${j.id}`}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>{j.report_type.toUpperCase()} 报告任务</strong>
                <span className={`status-pill status-${j.status}`}>{j.status}</span>
              </div>
              <div style={{ marginTop: 8, fontSize: 13, color: "#4b5563" }}>
                <div>任务ID：{j.id}</div>
                <div>Writing Mode：{mode}</div>
                <div>
                  时间范围：{j.time_range_start || "-"} ~ {j.time_range_end || "-"}
                </div>
                <div>创建时间：{j.created_at || "-"}</div>
              </div>
              <div style={{ marginTop: 10 }}>
                <span className="btn">进入验收页</span>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}
