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

  function getStatusColor(status: string) {
    switch (status) {
      case "completed": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "running": return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      case "failed": return "bg-rose-500/20 text-rose-400 border-rose-500/30";
      default: return "bg-slate-700 text-slate-400";
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">任务列表</h1>
        <p className="text-slate-400">查看所有报告任务的状态、写作模式和执行结果</p>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 mb-6">
        <a
          href="/jobs/new"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-all"
        >
          <span>+</span>
          <span>新建任务</span>
        </a>
        <a
          href="/brand"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 transition-all"
        >
          <span>⚙️</span>
          <span>品牌配置</span>
        </a>
        <a
          href="/knowledge"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 transition-all"
        >
          <span>📚</span>
          <span>知识库</span>
        </a>
      </div>

      {/* Brand Info */}
      <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700 mb-6">
        <span className="text-slate-400">品牌归属：</span>
        <span className="text-slate-200 font-medium">{brand.name}</span>
      </div>

      {/* Jobs List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="flex gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
          <span className="ml-3 text-slate-400">加载中...</span>
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-12 rounded-xl bg-slate-800/30 border border-slate-700 border-dashed">
          <div className="text-4xl mb-3">📭</div>
          <p className="text-slate-400 mb-2">暂无任务</p>
          <p className="text-sm text-slate-500">点击上方"新建任务"创建您的第一个报告任务</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {jobs.map((j) => {
            const stats = j.stats || {};
            const mode = stats.writing_mode_used || "llm";
            return (
              <a
                key={j.id}
                href={`/jobs/${j.id}`}
                className="block p-5 rounded-xl bg-slate-800/50 border border-slate-700 hover:border-indigo-500/30 hover:bg-slate-800 transition-all group"
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-100 group-hover:text-indigo-300 transition-colors">
                      {j.report_type.toUpperCase()} 报告任务
                    </h3>
                    <p className="text-sm text-slate-500 mt-1">ID: {j.id}</p>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(j.status)}`}>
                    {j.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                  <div>
                    <span className="text-slate-500">写作模式：</span>
                    <span className="text-slate-300">{mode}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">创建时间：</span>
                    <span className="text-slate-300">
                      {j.created_at ? new Date(j.created_at).toLocaleString() : "-"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-slate-500">时间范围：</span>
                    <span className="text-slate-300">
                      {j.time_range_start ? new Date(j.time_range_start).toLocaleDateString() : "-"}
                      {" ~ "}
                      {j.time_range_end ? new Date(j.time_range_end).toLocaleDateString() : "-"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-indigo-400 text-sm font-medium">
                  <span>进入验收页</span>
                  <span>→</span>
                </div>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
