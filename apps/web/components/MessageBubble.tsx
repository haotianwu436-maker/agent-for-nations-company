"use client";

import { useState } from "react";
import MemoizedMarkdown from "./MemoizedMarkdown";

 type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  markdown?: string;
  citations?: Array<Record<string, unknown>>;
  sources?: Array<{
    id: string;
    title: string;
    source: string;
    url?: string;
    preview: string;
    score?: number;
  }>;
  status?: string;
  needs_human?: boolean;
  grounded_score?: number;
  loading?: boolean;
  error?: boolean;
  trajectory?: Array<{
    node: string;
    type: "start" | "end";
    timestamp: string;
    inputs?: Record<string, unknown>;
    outputs?: Record<string, unknown>;
  }>;
};

type Props = {
  message: Message;
  onCopyReport?: (content: string) => void;
  onRetry?: () => void;
};

function GroundednessBadge({ score }: { score: number }) {
  let colorClass = "bg-rose-500/20 text-rose-300 border-rose-400/50";
  let label = "需复核";
  
  if (score >= 0.8) {
    colorClass = "bg-emerald-500/20 text-emerald-300 border-emerald-400/50";
    label = "高可信度";
  } else if (score >= 0.6) {
    colorClass = "bg-amber-500/20 text-amber-300 border-amber-400/50";
    label = "中等可信度";
  }
  
  return (
    <span className={`rounded-full border px-2 py-1 text-xs ${colorClass}`}>
      Grounded: {(score * 100).toFixed(0)}% ({label})
    </span>
  );
}

function CitationCard({ citation, index }: { citation: Record<string, unknown>; index: number }) {
  const [expanded, setExpanded] = useState(false);
  
  const text = String(citation.text || citation.snippet || "");
  const source = String(citation.source || citation.source_name || "未知来源");
  const url = String(citation.url || citation.source_url || "");
  
  return (
    <div className="rounded border border-slate-600/50 bg-slate-700/30 p-2">
      <div className="flex items-start gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500/30 text-xs font-medium text-indigo-300">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <p className={`text-xs text-slate-300 ${expanded ? "" : "line-clamp-2"}`}>
            {text}
          </p>
          {text.length > 100 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-xs text-indigo-400 hover:text-indigo-300"
            >
              {expanded ? "收起" : "展开"}
            </button>
          )}
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xs text-slate-500">{source}</span>
            {url && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-indigo-400 hover:text-indigo-300"
              >
                查看来源
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TrajectoryTimeline({ trajectory }: { trajectory: Message["trajectory"] }) {
  if (!trajectory || trajectory.length === 0) return null;
  
  return (
    <div className="mt-4 rounded-lg border border-slate-600/50 bg-slate-800/50 p-3">
      <h4 className="mb-2 text-xs font-semibold text-slate-300">Agent 执行轨迹</h4>
      <div className="space-y-1">
        {trajectory.map((entry, idx) => (
          <div key={idx} className="flex items-center gap-2 text-xs">
            <span className={`h-2 w-2 rounded-full ${entry.type === "start" ? "bg-amber-400" : "bg-emerald-400"}`} />
            <span className="text-slate-400">{entry.node}</span>
            <span className="text-slate-600">{entry.type === "start" ? "开始" : "完成"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MessageBubble({ message, onCopyReport, onRetry }: Props) {
  const isUser = message.role === "user";
  const markdown = message.markdown || message.content;
  const [showCitations, setShowCitations] = useState(false);
  const [showTrajectory, setShowTrajectory] = useState(false);

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
      <div
        className={`max-w-[92%] rounded-2xl border px-4 py-3 shadow-lg md:max-w-[85%] ${
          isUser
            ? "border-blue-400/30 bg-gradient-to-r from-blue-600 to-indigo-600 text-blue-50"
            : "border-slate-600/60 bg-slate-800/85 text-slate-100"
        } ${message.error ? "border-rose-400/70 bg-rose-950/30" : ""}`}
      >
        {!isUser ? (
          <div>
            {message.loading ? (
              <div className="inline-flex items-center gap-2 text-sm text-slate-200">
                <span>{message.content}</span>
                <span className="inline-flex gap-1" aria-hidden="true">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:-0.2s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:-0.1s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300" />
                </span>
              </div>
            ) : (
              <>
                <MemoizedMarkdown content={markdown} citations={message.citations} />
                
                {/* Human Review Warning */}
                {message.needs_human ? (
                  <div className="mt-3 rounded-lg border border-amber-300/50 bg-amber-400/15 px-3 py-2 text-xs text-amber-100">
                    ⚠️ 此部分内容建议人工复核
                  </div>
                ) : null}
                
                {/* Status Bar */}
                {!message.error && (message.citations?.length || message.sources?.length || message.status || typeof message.grounded_score === "number") ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-600/60 pt-3 text-xs">
                    {message.status ? (
                      <span className={`rounded-full px-2 py-1 ${
                        message.status === "completed" 
                          ? "bg-emerald-500/20 text-emerald-300" 
                          : message.status === "needs_human"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-slate-700 text-slate-300"
                      }`}>
                        状态: {message.status}
                      </span>
                    ) : null}
                    
                    {typeof message.grounded_score === "number" ? (
                      <GroundednessBadge score={message.grounded_score} />
                    ) : null}
                    
                    {message.citations?.length ? (
                      <button
                        onClick={() => setShowCitations(!showCitations)}
                        className={`rounded-full px-2 py-1 transition ${
                          showCitations 
                            ? "bg-indigo-500/30 text-indigo-300" 
                            : "bg-slate-700 text-slate-300 hover:bg-slate-600"
                        }`}
                      >
                        引用: {message.citations.length}
                      </button>
                    ) : null}
                    
                    {message.sources?.length ? (
                      <span className="rounded-full bg-slate-700 px-2 py-1 text-slate-300">
                        来源: {message.sources.length}
                      </span>
                    ) : null}
                    
                    {message.trajectory && message.trajectory.length > 0 && (
                      <button
                        onClick={() => setShowTrajectory(!showTrajectory)}
                        className={`rounded-full px-2 py-1 transition ${
                          showTrajectory 
                            ? "bg-indigo-500/30 text-indigo-300" 
                            : "bg-slate-700 text-slate-300 hover:bg-slate-600"
                        }`}
                      >
                        轨迹
                      </button>
                    )}
                  </div>
                ) : null}
                
                {/* Citations Panel */}
                {showCitations && message.citations && message.citations.length > 0 && (
                  <div className="mt-3 space-y-2">
                    <h4 className="text-xs font-semibold text-slate-400">引用详情</h4>
                    {message.citations.map((citation, idx) => (
                      <CitationCard key={idx} citation={citation} index={idx} />
                    ))}
                  </div>
                )}
                
                {/* Trajectory Panel */}
                {showTrajectory && message.trajectory && (
                  <TrajectoryTimeline trajectory={message.trajectory} />
                )}
                
                {/* Action Buttons */}
                {!message.error && markdown.trim() ? (
                  <div className="mt-3 flex justify-end gap-2">
                    <button
                      type="button"
                      className="rounded-lg border border-slate-500 bg-slate-700/80 px-3 py-1.5 text-xs text-slate-100 transition hover:border-indigo-400 hover:bg-slate-700"
                      onClick={() => onCopyReport?.(markdown)}
                    >
                      复制报告
                    </button>
                  </div>
                ) : null}
                
                {/* Error Retry */}
                {message.error ? (
                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      className="rounded-lg border border-rose-400/70 bg-rose-500/20 px-3 py-1.5 text-xs text-rose-100 transition hover:bg-rose-500/30"
                      onClick={onRetry}
                    >
                      重试
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </div>
        ) : (
          <div className="whitespace-pre-wrap break-words text-sm leading-7">{message.content}</div>
        )}
      </div>
    </div>
  );
}
