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

  useEffect(() => {
    const token = localStorage.getItem("token");
    fetch(`${API_BASE}/report-jobs`, {
      headers: { Authorization: `Bearer ${token || ""}` }
    })
      .then((r) => r.json())
      .then((d) => setJobs(d.items || []))
      .catch(() => setJobs([]));
  }, []);

  return (
    <div className="card">
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
