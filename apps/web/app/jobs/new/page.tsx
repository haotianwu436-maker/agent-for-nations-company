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
  const [messageType, setMessageType] = useState<"success" | "error" | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCreate(runNow: boolean) {
    const token = localStorage.getItem("token");
    if (!token) {
      setMessage("请先登录");
      setMessageType("error");
      router.push("/login");
      return;
    }
    setLoading(true);
    setMessage("");
    setMessageType(null);

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
        setMessage(`创建失败: ${data.detail || "未知错误"}`);
        setMessageType("error");
        return;
      }

      if (runNow) {
        const runRes = await fetch(`${getApiBase()}/report-jobs/${data.id}/run`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` }
        });
        const runData = await runRes.json().catch(() => ({}));
        if (!runRes.ok) {
          setMessage(`任务已创建(${data.id})，但执行失败: ${runData.detail || "未知错误"}`);
          setMessageType("error");
          return;
        }
        setMessage(`✓ 任务已创建并触发执行: ${data.id}`);
        setMessageType("success");
      } else {
        setMessage(`✓ 任务已创建: ${data.id}`);
        setMessageType("success");
      }

      // Delay navigation so user can see the message
      setTimeout(() => router.push(`/jobs/${data.id}`), 1000);
    } catch {
      setMessage("请求失败，请检查 API 是否在线");
      setMessageType("error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-100 mb-2">新建任务</h1>
        <p className="text-slate-400">配置报告参数并创建新的 AI 报告生成任务</p>
      </div>

      {/* Form Card */}
      <div className="max-w-3xl">
        <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          {/* Keywords */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-2">
              关键词 <span className="text-slate-500">（逗号分隔）</span>
            </label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
              placeholder="AI, AIGC, media, policy..."
            />
            <p className="mt-1.5 text-xs text-slate-500">
              这些关键词将用于检索相关资讯和文档
            </p>
          </div>

          {/* Sources */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-2">
              信源白名单 <span className="text-slate-500">（每行一个 URL）</span>
            </label>
            <textarea
              value={sources}
              onChange={(e) => setSources(e.target.value)}
              rows={5}
              className="w-full px-4 py-3 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all resize-none font-mono text-sm"
              placeholder="https://example.com/..."
            />
            <p className="mt-1.5 text-xs text-slate-500">
              系统将优先从这些来源抓取资讯
            </p>
          </div>

          {/* Default Settings Info */}
          <div className="p-4 rounded-lg bg-indigo-500/10 border border-indigo-500/20 mb-6">
            <h4 className="text-sm font-medium text-indigo-300 mb-2">默认配置</h4>
            <div className="grid grid-cols-2 gap-2 text-xs text-slate-400">
              <div>报告类型：<span className="text-slate-300">weekly（周报）</span></div>
              <div>写作模式：<span className="text-slate-300">LLM + Rule 双模式</span></div>
              <div>时间范围：<span className="text-slate-300">最近 7 天</span></div>
              <div>语言：<span className="text-slate-300">中文</span></div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => handleCreate(false)}
              disabled={loading}
              className="px-5 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 font-medium transition-all disabled:opacity-50"
            >
              {loading ? "创建中..." : "仅创建任务"}
            </button>
            <button
              onClick={() => handleCreate(true)}
              disabled={loading}
              className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-all disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>创建中...</span>
                </>
              ) : (
                <>
                  <span>⚡</span>
                  <span>创建并立即执行</span>
                </>
              )}
            </button>
          </div>

          {/* Message */}
          {message && (
            <div
              className={`mt-4 p-4 rounded-lg ${
                messageType === "success"
                  ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                  : "bg-rose-500/10 border border-rose-500/20 text-rose-400"
              }`}
            >
              {message}
            </div>
          )}
        </div>

        {/* Back Link */}
        <div className="mt-4">
          <a
            href="/jobs"
            className="inline-flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            <span>←</span>
            <span>返回任务列表</span>
          </a>
        </div>
      </div>
    </div>
  );
}
