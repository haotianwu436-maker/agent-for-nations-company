"use client";

import { getApiBase } from "./api-base";

export type AgentChatRequest = {
  query: string;
  user_id: string;
  organization_id: string;
  use_llm_writing: boolean;
  need_internal_kb?: boolean;
  messages?: Array<{ role: "user" | "assistant"; content: string }>;
};

export type AgentChatResponse = {
  message: string;
  markdown?: string;
  citations: Array<Record<string, unknown>>;
  sources: Array<Record<string, unknown>>;
  status: string;
  needs_human: boolean;
  grounded_score: number;
  consistency_score?: number;
  has_contradiction?: boolean;
  contradictions?: Array<{ sections: string; issue: string }>;
  repeated_content?: Array<{ sections: string; description: string }>;
  consistency_suggestions?: string[];
  // AIGC Detection
  aigc_score?: number;
  is_aigc?: boolean;
  aigc_suggestion?: string;
  kb_info?: {
    doc_count: number;
    chunk_count: number;
    last_updated_at: string;
  };
  trajectory?: Array<{
    node: string;
    type: "start" | "end";
    timestamp: string;
    inputs?: Record<string, unknown>;
    outputs?: Record<string, unknown>;
  }>;
};

export type KbStatusResponse = {
  doc_count: number;
  chunk_count: number;
  last_updated_at: string;
};

export type SourceDocument = {
  id: string;
  title: string;
  source: string;
  url?: string;
  preview: string;
  score?: number;
};

export type StreamEvent =
  | { type: "step"; data: { step: string; label: string; emoji: string; progress: number; description?: string; node?: string } }
  | { type: "progress"; data: { value: number; step: string } }
  | { type: "token"; data: { text: string; section?: string; is_final: boolean } }
  | { type: "section"; data: { section_name: string; content: string } }
  | { type: "citations"; data: { citations: Array<Record<string, unknown>>; count?: number } }
  | { type: "sources"; data: { sources: SourceDocument[] } }
  | { type: "stats"; data: Record<string, unknown> }
  | { type: "kb_info"; data: { doc_count: number; chunk_count: number; last_updated_at?: string } }
  | { type: "thinking"; data: { node: string; thought: string } }
  | { type: "trajectory"; data: { trajectory: AgentChatResponse["trajectory"]; complete?: boolean; current_node?: string } }
  | { type: "done"; data: AgentChatResponse }
  | { type: "error"; data: { code: string; message: string } };

export function parseSSEEvent(eventLine: string, dataLine: string): StreamEvent | null {
  if (eventLine === "event: step") {
    return { type: "step", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: progress") {
    return { type: "progress", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: token") {
    return { type: "token", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: section") {
    return { type: "section", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: citations") {
    return { type: "citations", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: sources") {
    return { type: "sources", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: stats") {
    return { type: "stats", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: kb_info") {
    return { type: "kb_info", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: thinking") {
    return { type: "thinking", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: trajectory") {
    return { type: "trajectory", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: done") {
    return { type: "done", data: JSON.parse(dataLine) };
  }
  if (eventLine === "event: error") {
    return { type: "error", data: JSON.parse(dataLine) };
  }
  return null;
}

export type StreamCallbacks = {
  onStep?: (step: { step: string; label: string; emoji: string; progress: number; description?: string; node?: string }) => void;
  onProgress?: (value: number) => void;
  onToken?: (text: string, section?: string) => void;
  onSection?: (sectionName: string, content: string) => void;
  onCitations?: (citations: Array<Record<string, unknown>>) => void;
  onSources?: (sources: SourceDocument[]) => void;
  onStats?: (stats: Record<string, unknown>) => void;
  onKbInfo?: (info: { doc_count: number; chunk_count: number }) => void;
  onThinking?: (node: string, thought: string) => void;
  onTrajectory?: (trajectory: AgentChatResponse["trajectory"], complete?: boolean) => void;
  onDone?: (data: AgentChatResponse) => void;
  onError?: (error: { code: string; message: string }) => void;
};

export async function chatWithAgentStream(
  payload: AgentChatRequest,
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`${getApiBase()}/agent/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    callbacks.onError?.({ code: "http_error", message: errorData?.detail || "请求失败" });
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError?.({ code: "no_reader", message: "无法读取响应流" });
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();
        
        if (!trimmed) {
          // Empty line means end of event
          if (eventType && buffer.trim()) {
            const dataLine = buffer.trim();
            if (dataLine.startsWith("data: ")) {
              const actualData = dataLine.slice(6);
              const event = parseSSEEvent(eventType, actualData);
              if (event) {
                switch (event.type) {
                  case "step":
                    callbacks.onStep?.(event.data);
                    break;
                  case "progress":
                    callbacks.onProgress?.(event.data.value);
                    break;
                  case "token":
                    callbacks.onToken?.(event.data.text, event.data.section);
                    break;
                  case "section":
                    callbacks.onSection?.(event.data.section_name, event.data.content);
                    break;
                  case "citations":
                    callbacks.onCitations?.(event.data.citations);
                    break;
                  case "sources":
                    callbacks.onSources?.(event.data.sources);
                    break;
                  case "stats":
                    callbacks.onStats?.(event.data);
                    break;
                  case "kb_info":
                    callbacks.onKbInfo?.(event.data);
                    break;
                  case "thinking":
                    callbacks.onThinking?.(event.data.node, event.data.thought);
                    break;
                  case "trajectory":
                    callbacks.onTrajectory?.(event.data.trajectory, event.data.complete);
                    break;
                  case "done":
                    callbacks.onDone?.(event.data);
                    break;
                  case "error":
                    callbacks.onError?.(event.data);
                    break;
                }
              }
            }
            eventType = "";
            buffer = "";
          }
          continue;
        }

        if (trimmed.startsWith("event: ")) {
          eventType = trimmed;
        } else if (trimmed.startsWith("data: ")) {
          buffer = trimmed;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function chatWithAgent(payload: AgentChatRequest): Promise<AgentChatResponse> {
  const res = await fetch(`${getApiBase()}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = (await res.json().catch(() => ({}))) as Partial<AgentChatResponse> & { detail?: string };
  if (!res.ok) {
    throw new Error(data?.detail || "请求失败，请稍后重试");
  }

  return {
    message:
      typeof data.message === "string"
        ? data.message
        : typeof (data as { markdown?: string }).markdown === "string"
          ? ((data as { markdown?: string }).markdown as string)
          : "",
    markdown: typeof (data as { markdown?: string }).markdown === "string" ? (data as { markdown?: string }).markdown : "",
    citations: Array.isArray(data.citations) ? data.citations : [],
    sources: Array.isArray(data.sources) ? data.sources : [],
    status: typeof data.status === "string" ? data.status : "completed",
    needs_human: Boolean((data as { needs_human?: boolean }).needs_human),
    grounded_score: Number((data as { grounded_score?: number }).grounded_score || 0),
    trajectory: Array.isArray((data as { trajectory?: unknown }).trajectory) 
      ? (data as { trajectory?: AgentChatResponse["trajectory"] }).trajectory 
      : undefined,
    kb_info:
      typeof (data as { kb_info?: unknown }).kb_info === "object" && (data as { kb_info?: unknown }).kb_info
        ? {
            doc_count: Number((data as { kb_info?: { doc_count?: number } }).kb_info?.doc_count || 0),
            chunk_count: Number((data as { kb_info?: { chunk_count?: number } }).kb_info?.chunk_count || 0),
            last_updated_at: String((data as { kb_info?: { last_updated_at?: string } }).kb_info?.last_updated_at || "")
          }
        : undefined
  };
}

export async function fetchKbStatus(): Promise<KbStatusResponse> {
  const res = await fetch(`${getApiBase()}/agent/kb/status`, { method: "GET" });
  const data = (await res.json().catch(() => ({}))) as Partial<KbStatusResponse> & { detail?: string };
  if (!res.ok) throw new Error(data?.detail || "获取知识库状态失败");
  return {
    doc_count: Number(data.doc_count || 0),
    chunk_count: Number(data.chunk_count || 0),
    last_updated_at: String(data.last_updated_at || "")
  };
}

export async function refreshKb(): Promise<{ updated_files: number; inserted_chunks: number; status: string }> {
  const res = await fetch(`${getApiBase()}/agent/kb/refresh`, { method: "POST" });
  const data = (await res.json().catch(() => ({}))) as {
    updated_files?: number;
    inserted_chunks?: number;
    status?: string;
    detail?: string;
  };
  if (!res.ok) throw new Error(data?.detail || "刷新知识库失败");
  return {
    updated_files: Number(data.updated_files || 0),
    inserted_chunks: Number(data.inserted_chunks || 0),
    status: String(data.status || "ok")
  };
}
