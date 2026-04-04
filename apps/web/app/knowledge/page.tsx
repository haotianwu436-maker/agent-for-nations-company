"use client";

import { useEffect, useState, useCallback } from "react";
import { getApiBase } from "../../lib/api-base";

interface Chunk {
  id: string;
  title: string;
  source_name: string;
  chunk_text: string;
  created_at?: string;
}

interface SearchResult {
  id: string;
  title: string;
  source_name: string;
  chunk_text: string;
  score: number;
}

interface UploadResult {
  document_id: string;
  parsed_file_type: string;
  docling_used: boolean;
  docling_fallback_count: number;
  chunk_count: number;
}

interface KbStats {
  doc_count: number;
  chunk_count: number;
  last_updated_at?: string;
}

export default function KnowledgePage() {
  const [query, setQuery] = useState("");
  const [sourceName, setSourceName] = useState("manual-upload");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [stats, setStats] = useState<KbStats>({ doc_count: 0, chunk_count: 0 });
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());

  const fetchStats = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${getApiBase()}/agent/kb/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch {}
  }, []);

  const fetchChunks = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${getApiBase()}/knowledge/chunks`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setChunks(data.items || []);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchStats();
    fetchChunks();
  }, [fetchStats, fetchChunks]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = e.dataTransfer.files;
    if (files?.[0]) {
      handleFileUpload(files[0]);
    }
  }, []);

  async function handleFileUpload(file: File) {
    const token = localStorage.getItem("token");
    if (!token) {
      setMessage({ type: "error", text: "请先登录" });
      return;
    }

    const validTypes = [".txt", ".md", ".docx", ".pdf"];
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!validTypes.includes(ext)) {
      setMessage({ type: "error", text: `不支持的文件类型: ${ext}` });
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setMessage(null);

    const form = new FormData();
    form.append("file", file);
    form.append("source_name", sourceName);

    const progressInterval = setInterval(() => {
      setUploadProgress(prev => Math.min(prev + 10, 90));
    }, 200);

    try {
      const res = await fetch(`${getApiBase()}/knowledge/files`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        setMessage({ type: "error", text: `上传失败: ${data.detail || "未知错误"}` });
        return;
      }

      const result = data as UploadResult;
      setMessage({
        type: "success",
        text: `✓ ${file.name} 上传成功！生成 ${result.chunk_count} 个片段`
      });

      await fetchStats();
      await fetchChunks();
    } catch {
      setMessage({ type: "error", text: "上传失败，请检查网络连接" });
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress(0), 500);
    }
  }

  async function handleSearch() {
    const token = localStorage.getItem("token");
    if (!token || !query.trim()) return;

    setLoading(true);
    setSearchResults([]);

    try {
      const res = await fetch(
        `${getApiBase()}/knowledge/search?q=${encodeURIComponent(query)}&top_k=10`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.items || []);
      }
    } catch {
      setMessage({ type: "error", text: "搜索失败" });
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    const token = localStorage.getItem("token");
    if (!token) return;

    setLoading(true);
    try {
      const res = await fetch(`${getApiBase()}/agent/kb/refresh`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });

      if (res.ok) {
        setMessage({ type: "success", text: "知识库刷新成功" });
        await fetchStats();
        await fetchChunks();
      }
    } catch {
      setMessage({ type: "error", text: "刷新失败" });
    } finally {
      setLoading(false);
    }
  }

  function toggleChunk(id: string) {
    setExpandedChunks(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div className="h-full overflow-y-auto p-6 bg-white">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">知识库管理</h1>
        <p className="text-gray-500">上传文档、管理知识片段、测试检索效果</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="p-4 rounded-lg bg-blue-50 border border-blue-100">
          <div className="text-2xl font-bold text-blue-700 mb-1">{stats.doc_count}</div>
          <div className="text-sm text-gray-600">文档总数</div>
        </div>
        <div className="p-4 rounded-lg bg-green-50 border border-green-100">
          <div className="text-2xl font-bold text-green-700 mb-1">{stats.chunk_count}</div>
          <div className="text-sm text-gray-600">知识片段</div>
        </div>
        <div className="p-4 rounded-lg bg-amber-50 border border-amber-100">
          <div className="text-2xl font-bold text-amber-700 mb-1">
            {stats.last_updated_at ? new Date(stats.last_updated_at).toLocaleDateString() : "-"}
          </div>
          <div className="text-sm text-gray-600">最后更新</div>
        </div>
      </div>

      {/* Upload Section */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span>📤</span> 文档上传
        </h2>

        <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 mb-3">
          <label className="block text-sm text-gray-600 mb-1">来源标识</label>
          <input
            type="text"
            value={sourceName}
            onChange={e => setSourceName(e.target.value)}
            className="w-full px-3 py-2 rounded-md bg-white border border-gray-300 text-gray-800 focus:outline-none focus:border-blue-500"
            placeholder="例如：manual-upload、内部文档"
          />
        </div>

        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-lg p-6 text-center transition-all ${
            dragActive
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 bg-gray-50 hover:border-gray-400"
          }`}
        >
          <input
            type="file"
            accept=".txt,.md,.docx,.pdf"
            onChange={e => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          <div className="text-3xl mb-2">📄</div>
          <p className="text-gray-700 font-medium mb-1">
            {uploading ? "正在上传..." : "点击或拖拽文件到此处上传"}
          </p>
          <p className="text-sm text-gray-500">支持 TXT、MD、DOCX、PDF 格式</p>

          {uploading && (
            <div className="mt-3">
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-sm text-gray-500 mt-1">{uploadProgress}%</p>
            </div>
          )}
        </div>

        {message && (
          <div
            className={`mt-3 p-3 rounded-md ${
              message.type === "success"
                ? "bg-green-50 border border-green-200 text-green-700"
                : "bg-red-50 border border-red-200 text-red-700"
            }`}
          >
            {message.text}
          </div>
        )}
      </div>

      {/* Search Section */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span>🔍</span> 知识检索
        </h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSearch()}
            placeholder="输入关键词搜索知识库..."
            className="flex-1 px-3 py-2 rounded-md bg-white border border-gray-300 text-gray-800 placeholder-gray-400 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 text-white rounded-md font-medium transition-all"
          >
            {loading ? "搜索中..." : "搜索"}
          </button>
        </div>

        {searchResults.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-sm text-gray-500">找到 {searchResults.length} 个相关结果</p>
            {searchResults.map((result, i) => (
              <div
                key={i}
                className="p-3 rounded-md bg-white border border-gray-200 hover:border-blue-300 transition-colors"
              >
                <div className="flex items-start justify-between gap-3 mb-1">
                  <h3 className="font-medium text-gray-800">{result.title || "无标题"}</h3>
                  <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700">
                    匹配度: {(result.score * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-xs text-gray-500 mb-1">{result.source_name}</p>
                <p className="text-sm text-gray-600 line-clamp-2">{result.chunk_text}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="px-3 py-2 rounded-md bg-gray-100 border border-gray-300 text-gray-700 hover:bg-gray-200 transition-all flex items-center gap-2"
        >
          <span>🔄</span> 刷新知识库
        </button>
        <button
          onClick={fetchChunks}
          className="px-3 py-2 rounded-md bg-gray-100 border border-gray-300 text-gray-700 hover:bg-gray-200 transition-all"
        >
          重新加载列表
        </button>
      </div>

      {/* Chunks List */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <span>📚</span> 知识片段列表
          <span className="text-sm font-normal text-gray-500">({chunks.length})</span>
        </h2>

        {chunks.length === 0 ? (
          <div className="text-center py-8 rounded-lg bg-gray-50 border border-gray-200 border-dashed">
            <div className="text-3xl mb-2">📭</div>
            <p className="text-gray-500 mb-1">知识库为空</p>
            <p className="text-sm text-gray-400">上传文档后将自动解析为知识片段</p>
          </div>
        ) : (
          <div className="space-y-2">
            {chunks.slice(0, 50).map(chunk => (
              <div
                key={chunk.id}
                className="rounded-md bg-white border border-gray-200 overflow-hidden"
              >
                <button
                  onClick={() => toggleChunk(chunk.id)}
                  className="w-full px-3 py-2 flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-gray-400 text-sm">
                      {expandedChunks.has(chunk.id) ? "▼" : "▶"}
                    </span>
                    <span className="font-medium text-gray-700 truncate">
                      {chunk.title || "无标题"}
                    </span>
                    <span className="text-xs text-gray-400 shrink-0">{chunk.source_name}</span>
                  </div>
                  <span className="text-xs text-gray-400">
                    {chunk.chunk_text.length} 字符
                  </span>
                </button>
                {expandedChunks.has(chunk.id) && (
                  <div className="px-3 pb-3 pt-1 border-t border-gray-100">
                    <p className="text-sm text-gray-600 whitespace-pre-wrap">{chunk.chunk_text}</p>
                  </div>
                )}
              </div>
            ))}
            {chunks.length > 50 && (
              <p className="text-center text-sm text-gray-400 py-3">
                还有 {chunks.length - 50} 个片段未显示
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
