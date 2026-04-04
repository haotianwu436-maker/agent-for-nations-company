"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { chatWithAgentStream, fetchKbStatus, refreshKb, AgentChatResponse, SourceDocument } from "../lib/api";
import ReportCharts from "./ReportCharts";

type Role = "user" | "assistant";

interface ChartData {
  type: "bar" | "line" | "pie";
  title: string;
  data: Array<Record<string, any>>;
  x_key?: string;
  y_key?: string;
  name_key?: string;
  value_key?: string;
  colors?: string[];
}

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  markdown?: string;
  citations?: Array<Record<string, unknown>>;
  sources?: SourceDocument[];
  charts?: ChartData[];
  status?: string;
  needs_human?: boolean;
  grounded_score?: number;
  consistency_score?: number;
  has_contradiction?: boolean;
  contradictions?: Array<{ sections: string; issue: string }>;
  loading?: boolean;
  error?: boolean;
  queryForRetry?: string;
  trajectory?: AgentChatResponse["trajectory"];
}

interface ChatConversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

const EXAMPLE_PROMPTS = [
  "帮我写一篇人工智能在传媒行业的周报",
  "结合我们内部宣传要点，写一份详细的月报",
  "分析最近AI政策对媒体行业的影响",
  "生成包含数据可视化和趋势解读的报告"
];

const ALL_STEPS = [
  { id: "planning", label: "理解需求", emoji: "🎯" },
  { id: "retrieving_internal", label: "检索内部知识库", emoji: "📚" },
  { id: "retrieving_external", label: "抓取外部信息", emoji: "🌐" },
  { id: "cleaning", label: "清洗数据", emoji: "🧹" },
  { id: "deduplicating", label: "去重合并", emoji: "🔄" },
  { id: "classifying", label: "智能分类", emoji: "📋" },
  { id: "generating", label: "生成章节", emoji: "✍️" },
  { id: "citing", label: "生成引用", emoji: "📎" },
  { id: "visualizing", label: "生成图表", emoji: "📊" },
  { id: "assembling", label: "组装报告", emoji: "📑" },
  { id: "validating", label: "质量校验", emoji: "✅" },
];

function uid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function shouldUseInternalHint(query: string) {
  return query.includes("内部宣传要点");
}

function renderMarkdown(content: string) {
  return content
    .replace(/## (.*)/g, '<h2 class="text-lg font-bold text-gray-900 mt-5 mb-2 pb-1 border-b border-gray-200">$1</h2>')
    .replace(/### (.*)/g, '<h3 class="text-base font-semibold text-gray-800 mt-4 mb-2">$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong class="text-gray-900 font-semibold">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="text-gray-700">$1</em>')
    .replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-100 rounded-md p-3 my-2 overflow-x-auto border border-gray-200"><code class="text-sm text-gray-800">$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1.5 py-0.5 rounded text-sm text-blue-700 border border-gray-200">$1</code>')
    .replace(/\n/g, '<br />');
}

interface ChatInterfaceProps {
  conversation: ChatConversation;
  onConversationChange: (conversation: ChatConversation) => void;
  onDeleteCurrentConversation?: () => void;
  onClearAllConversations?: () => void;
}

export default function ChatInterface({
  conversation,
  onConversationChange,
  onDeleteCurrentConversation,
  onClearAllConversations
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [currentStep, setCurrentStep] = useState<string>("");
  const [progress, setProgress] = useState<number>(0);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());
  const [kbInfo, setKbInfo] = useState({ doc_count: 0, chunk_count: 0, last_updated_at: "" });
  const [showTrajectory, setShowTrajectory] = useState(false);
  const [currentTrajectory, setCurrentTrajectory] = useState<AgentChatResponse["trajectory"]>([]);
  const [thinkingLog, setThinkingLog] = useState<Array<{node: string; thought: string}>>([]);
  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [showSources, setShowSources] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('chat-sidebar-collapsed') === 'true';
    }
    return false;
  });

  // Persist sidebar state
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('chat-sidebar-collapsed', isSidebarCollapsed.toString());
    }
  }, [isSidebarCollapsed]);
  
  const listRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  const messages = conversation.messages;

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, thinkingLog]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  useEffect(() => {
    fetchKbStatus()
      .then(setKbInfo)
      .catch(() => setKbInfo({ doc_count: 0, chunk_count: 0, last_updated_at: "" }));
  }, []);

  function updateMessages(nextMessages: ChatMessage[]) {
    onConversationChange({
      ...conversation,
      messages: nextMessages,
      updatedAt: Date.now(),
      title: conversation.title === "新对话" && nextMessages[0]?.content ? nextMessages[0].content.slice(0, 20) : conversation.title
    });
  }

  async function send(query: string) {
    const cleaned = query.trim();
    if (!cleaned || isSending) return;

    const userMsg: ChatMessage = { id: uid(), role: "user", content: cleaned };
    const loadingMsg: ChatMessage = {
      id: uid(),
      role: "assistant",
      content: "",
      loading: true,
      queryForRetry: cleaned,
    };

    updateMessages([...messages, userMsg, loadingMsg]);
    setInput("");
    setIsSending(true);
    setCurrentStep("planning");
    setProgress(0);
    setCompletedSteps(new Set());
    setThinkingLog([]);
    setSources([]);
    setCurrentTrajectory([]);

    try {
      const historyForApi = messages
        .filter(m => !m.loading && !m.error)
        .map(m => ({ role: m.role, content: (m.markdown || m.content || "").slice(0, 2000) }));

      let accumulatedMarkdown = "";

      await chatWithAgentStream(
        {
          query: cleaned,
          user_id: "frontend-user",
          organization_id: "frontend-org",
          use_llm_writing: true,
          need_internal_kb: shouldUseInternalHint(cleaned),
          messages: historyForApi,
        },
        {
          onStep: (step) => {
            setCurrentStep(step.step);
            setProgress(step.progress);
            setCompletedSteps(prev => {
              const next = new Set(prev);
              const idx = ALL_STEPS.findIndex(s => s.id === step.step);
              if (idx > 0) next.add(ALL_STEPS[idx - 1].id);
              return next;
            });
          },
          onProgress: setProgress,
          onToken: (text) => {
            accumulatedMarkdown = text;
            updateMessages(
              messages.map(m =>
                m.id === loadingMsg.id
                  ? { ...m, content: text, markdown: text, loading: false }
                  : m
              )
            );
          },
          onCitations: (citations) => {
            updateMessages(
              messages.map(m =>
                m.id === loadingMsg.id ? { ...m, citations } : m
              )
            );
          },
          onSources: (srcs) => {
            setSources(srcs);
            updateMessages(
              messages.map(m =>
                m.id === loadingMsg.id ? { ...m, sources: srcs } : m
              )
            );
          },
          onThinking: (node, thought) => {
            setThinkingLog(prev => [...prev, { node, thought }]);
          },
          onTrajectory: (trajectory) => {
            setCurrentTrajectory(trajectory);
          },
          onDone: (data) => {
            setCompletedSteps(new Set(ALL_STEPS.map(s => s.id)));
            setProgress(100);
            setCurrentStep("done");
            setCurrentTrajectory(data.trajectory || []);
            
            const parsedCharts: ChartData[] = [];
            if (data.markdown) {
              const chartRegex = /```json\s*\n?(\{[\s\S]*?"type"\s*:\s*"(bar|line|pie)"[\s\S]*?\})\s*\n?```/g;
              let match;
              while ((match = chartRegex.exec(data.markdown)) !== null) {
                try {
                  const chartData = JSON.parse(match[1]);
                  if (chartData.type && chartData.data) {
                    parsedCharts.push(chartData);
                  }
                } catch {}
              }
            }
            
            updateMessages(
              messages.map(m =>
                m.id === loadingMsg.id
                  ? {
                      ...m,
                      loading: false,
                      content: data.markdown || data.message,
                      markdown: data.markdown || data.message,
                      citations: data.citations,
                      sources: data.sources as SourceDocument[],
                      charts: parsedCharts.length > 0 ? parsedCharts : undefined,
                      status: data.status,
                      needs_human: data.needs_human,
                      grounded_score: data.grounded_score,
                      consistency_score: (data as any).consistency_score,
                      has_contradiction: (data as any).has_contradiction,
                      contradictions: (data as any).contradictions,
                      trajectory: data.trajectory,
                    }
                  : m
              )
            );
          },
          onError: (error) => {
            updateMessages(
              messages.map(m =>
                m.id === loadingMsg.id
                  ? {
                      ...m,
                      loading: false,
                      error: true,
                      content: `生成失败：${error.message}`,
                      markdown: `> 生成失败：${error.message}\n\n请检查网络或后端服务后重试。`,
                    }
                  : m
              )
            );
          },
        }
      );
    } catch (err) {
      const errorText = err instanceof Error ? err.message : "网络异常";
      updateMessages(
        messages.map(m =>
          m.id === loadingMsg.id
            ? {
                ...m,
                loading: false,
                error: true,
                content: `生成失败：${errorText}`,
                markdown: `> 生成失败：${errorText}\n\n请检查网络或后端服务后重试。`,
              }
            : m
        )
      );
    } finally {
      setIsSending(false);
    }
  }

  async function handleRefreshKb() {
    await refreshKb();
    const s = await fetchKbStatus();
    setKbInfo(s);
  }

  function copyReport(content: string) {
    navigator.clipboard.writeText(content);
  }

  const canSend = input.trim().length > 0 && !isSending;

  return (
    <div className="flex h-full bg-white">
      {/* Main Chat Area - Full Width */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        {/* Chat Header */}
        <div className="h-14 flex items-center justify-between px-6 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-4">
            <span className="text-gray-500 text-sm">知识库:</span>
            <span className="text-green-600 text-sm font-medium">{kbInfo.doc_count} 篇文档</span>
            <button
              onClick={handleRefreshKb}
              className="text-xs text-blue-600 hover:text-blue-700 transition-colors"
            >
              刷新
            </button>
          </div>
          <div className="flex items-center gap-2">
            {sources.length > 0 && (
              <button
                onClick={() => setShowSources(!showSources)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  showSources
                    ? "bg-green-50 text-green-700 border border-green-200"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                来源 ({sources.length})
              </button>
            )}
            {currentTrajectory.length > 0 && (
              <button
                onClick={() => setShowTrajectory(!showTrajectory)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  showTrajectory
                    ? "bg-blue-50 text-blue-700 border border-blue-200"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                轨迹
              </button>
            )}
          </div>
        </div>

        {/* Sources Panel */}
        {showSources && sources.length > 0 && (
          <div className="border-b border-gray-200 bg-gray-50 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">📚 检索到的来源</h3>
            <div className="grid grid-cols-2 gap-3 max-h-48 overflow-y-auto">
              {sources.map((src, i) => (
                <div key={i} className="p-3 rounded-md bg-white border border-gray-200">
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-medium text-gray-800 line-clamp-1">{src.title}</h4>
                    {src.score !== undefined && (
                      <span className="text-xs text-green-600">{(src.score * 100).toFixed(0)}%</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{src.source}</p>
                  <p className="text-xs text-gray-600 mt-2 line-clamp-2">{src.preview}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Trajectory Panel */}
        {showTrajectory && currentTrajectory.length > 0 && (
          <div className="border-b border-gray-200 bg-gray-50 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">🔍 Agent 执行轨迹</h3>
            <div className="flex flex-wrap gap-2">
              {currentTrajectory.map((entry, i) => (
                <div
                  key={i}
                  className={`px-2 py-1 rounded text-xs border ${
                    entry.type === "start"
                      ? "bg-amber-50 text-amber-700 border-amber-200"
                      : "bg-green-50 text-green-700 border-green-200"
                  }`}
                >
                  {entry.node} {entry.type === "start" ? "▶" : "✓"}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Thinking Log */}
        {thinkingLog.length > 0 && (
          <div className="border-b border-gray-200 bg-amber-50 p-3">
            <div className="max-h-24 overflow-y-auto space-y-1">
              {thinkingLog.slice(-3).map((log, i) => (
                <div key={i} className="text-xs text-amber-700">
                  <span className="font-medium">[{log.node}]</span> {log.thought}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        <div ref={listRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center mb-6 shadow-md">
                <span className="text-3xl text-white">📺</span>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">AI 报告智能体</h2>
              <p className="text-gray-500 max-w-md mb-8">
                输入需求，智能体会自动检索内部知识库和外部资讯，生成专业的媒体行业报告
              </p>
              <div className="flex flex-wrap justify-center gap-2 max-w-lg">
                {EXAMPLE_PROMPTS.map(prompt => (
                  <button
                    key={prompt}
                    onClick={() => send(prompt)}
                    className="px-4 py-2 rounded-full bg-gray-100 text-gray-700 text-sm border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-all"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map(message => (
              <div
                key={message.id}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 ${
                    message.role === "user"
                      ? "bg-blue-100 text-gray-900"
                      : "bg-white border border-gray-200 text-gray-800 shadow-sm"
                  } ${message.error ? "bg-red-50 border-red-200" : ""}`}
                >
                  {message.loading ? (
                    <div className="flex items-center gap-3 text-gray-500">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                      <span className="text-sm">正在生成报告...</span>
                    </div>
                  ) : (
                    <>
                      <div
                        className="prose prose-sm max-w-none text-gray-800"
                        dangerouslySetInnerHTML={{
                          __html: renderMarkdown(message.markdown || message.content)
                        }}
                      />
                      
                      {/* Charts Section */}
                      {message.charts && message.charts.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-gray-200">
                          <h4 className="text-sm font-semibold text-gray-700 mb-3">📊 数据可视化</h4>
                          <ReportCharts charts={message.charts} />
                        </div>
                      )}
                      
                      {/* Consistency Check */}
                      {message.consistency_score !== undefined && (
                        <div className="mt-3">
                          <div className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${
                            message.has_contradiction
                              ? "bg-red-100 text-red-700"
                              : message.consistency_score >= 0.8
                              ? "bg-green-100 text-green-700"
                              : "bg-amber-100 text-amber-700"
                          }`}>
                            <span>一致性: {(message.consistency_score * 100).toFixed(0)}%</span>
                            {message.has_contradiction && <span>⚠️ 发现矛盾</span>}
                          </div>
                          {message.contradictions && message.contradictions.length > 0 && (
                            <div className="mt-2 space-y-1">
                              {message.contradictions.slice(0, 3).map((c, i) => (
                                <div key={i} className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
                                  {c.sections}: {c.issue}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                      
                      {/* AIGC Check */}
                      {message.aigc_score !== undefined && (
                        <div className="mt-3">
                          <div className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${
                            message.is_aigc
                              ? "bg-red-100 text-red-700"
                              : message.aigc_score < 0.3
                              ? "bg-green-100 text-green-700"
                              : "bg-amber-100 text-amber-700"
                          }`}>
                            <span>AIGC检测: {(message.aigc_score * 100).toFixed(0)}%</span>
                            {message.is_aigc && <span>⚠️ 疑似AI生成</span>}
                          </div>
                          {message.aigc_suggestion && (
                            <div className="mt-1 text-xs text-gray-600">
                              {message.aigc_suggestion}
                            </div>
                          )}
                        </div>
                      )}
                      
                      {message.needs_human && (
                        <div className="mt-3 px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-amber-700 text-xs">
                          ⚠️ 此部分内容建议人工复核
                        </div>
                      )}
                      
                      {!message.error && message.markdown && (
                        <div className="mt-3 flex items-center gap-3 pt-3 border-t border-gray-200">
                          {message.grounded_score !== undefined && (
                            <span className={`text-xs px-2 py-1 rounded ${
                              message.grounded_score >= 0.8
                                ? "bg-green-100 text-green-700"
                                : message.grounded_score >= 0.6
                                ? "bg-amber-100 text-amber-700"
                                : "bg-red-100 text-red-700"
                            }`}>
                              可信度: {(message.grounded_score * 100).toFixed(0)}%
                            </span>
                          )}
                          <button
                            onClick={() => copyReport(message.markdown || "")}
                            className="text-xs text-gray-500 hover:text-gray-700 transition-colors"
                          >
                            复制
                          </button>
                          {message.error && message.queryForRetry && (
                            <button
                              onClick={() => send(message.queryForRetry!)}
                              className="text-xs text-red-600 hover:text-red-700 transition-colors"
                            >
                              重试
                            </button>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Progress Bar */}
        {isSending && (
          <div className="px-6 py-3 border-t border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-700">
                {ALL_STEPS.find(s => s.id === currentStep)?.emoji} {ALL_STEPS.find(s => s.id === currentStep)?.label}
              </span>
              <span className="text-sm text-gray-500">{progress}%</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex gap-1 mt-2">
              {ALL_STEPS.map(step => (
                <div
                  key={step.id}
                  className={`flex-1 h-1 rounded-full ${
                    completedSteps.has(step.id)
                      ? "bg-green-400"
                      : step.id === currentStep
                      ? "bg-blue-600"
                      : "bg-gray-200"
                  }`}
                />
              ))}
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="p-4 border-t border-gray-200 bg-white">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (canSend) send(input);
            }}
            className="flex gap-3"
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (canSend) send(input);
                }
              }}
              placeholder="输入需求，例如：帮我写一篇人工智能在传媒行业的周报..."
              className="flex-1 min-h-[48px] max-h-[200px] bg-white border border-gray-300 rounded-lg px-4 py-3 text-gray-800 placeholder-gray-400 resize-none focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-200 transition-all"
              disabled={isSending}
            />
            <button
              type="submit"
              disabled={!canSend}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 text-white rounded-lg font-medium transition-all flex items-center gap-2"
            >
              <span>{isSending ? "生成中" : "发送"}</span>
              {!isSending && <span>→</span>}
            </button>
          </form>
          <p className="text-xs text-gray-400 mt-2 text-center">
            AI 生成的内容仅供参考，重要决策请人工核实
          </p>
        </div>
      </div>
    </div>
  );
}
