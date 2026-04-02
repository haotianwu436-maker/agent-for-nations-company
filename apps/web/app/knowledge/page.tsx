"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "../../lib/api-base";

export default function KnowledgePage() {
  const [query, setQuery] = useState("AI governance");
  const [sourceName, setSourceName] = useState("manual-upload");
  const [uploadMsg, setUploadMsg] = useState("");
  const [searchItems, setSearchItems] = useState<any[]>([]);
  const [chunkItems, setChunkItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  async function refreshChunks() {
    const token = localStorage.getItem("token");
    if (!token) return;
    const res = await fetch(`${getApiBase()}/knowledge/chunks`, { headers: { Authorization: `Bearer ${token}` } });
    const data = res.ok ? await res.json() : { items: [] };
    setChunkItems(data.items || []);
  }

  useEffect(() => {
    refreshChunks();
  }, []);

  async function handleFileUpload(file: File) {
    const token = localStorage.getItem("token");
    if (!token) {
      setUploadMsg("请先登录");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    form.append("source_name", sourceName);
    setLoading(true);
    const res = await fetch(`${getApiBase()}/knowledge/files`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form
    });
    const data = await res.json().catch(() => ({}));
    setLoading(false);
    if (!res.ok) {
      setUploadMsg(`上传失败: ${data.detail || "unknown"}`);
      return;
    }
    setUploadMsg(
      `上传成功 document_id=${data.document_id} | parsed_file_type=${data.parsed_file_type} | docling_used=${data.docling_used} | docling_fallback_count=${data.docling_fallback_count} | chunk_count=${data.chunk_count}`
    );
    await refreshChunks();
  }

  async function handleSearch() {
    const token = localStorage.getItem("token");
    if (!token) return;
    const res = await fetch(`${getApiBase()}/knowledge/search?q=${encodeURIComponent(query)}&top_k=8`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = res.ok ? await res.json() : { items: [] };
    setSearchItems(data.items || []);
  }

  return (
    <div>
      <div className="card">
        <h2>知识库管理</h2>
        <p>支持 txt / md / docx 上传，展示解析方式、分块数量与检索命中结果。</p>
      </div>

      <div className="card">
        <h3>上传文档</h3>
        <label>source_name</label>
        <input className="input" value={sourceName} onChange={(e) => setSourceName(e.target.value)} />
        <input
          className="input"
          type="file"
          accept=".txt,.md,.docx"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileUpload(file);
          }}
        />
        <div>{loading ? "上传中..." : uploadMsg || "请选择文档后自动上传"}</div>
      </div>

      <div className="card">
        <h3>知识库检索</h3>
        <div className="row">
          <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} />
          <button className="btn btn-primary" onClick={handleSearch}>搜索</button>
        </div>
        {searchItems.length === 0 ? <div className="empty">暂无命中结果</div> : null}
        {searchItems.map((item, idx) => (
          <div className="card" key={idx}>
            <div><strong>{item.title || "-"}</strong> / {item.source_name || "-"}</div>
            <div style={{ color: "#6b7280", fontSize: 12 }}>score: {item.score}</div>
            <div className="report-section-content">{item.chunk_text}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Chunk 列表</h3>
        <div style={{ color: "#6b7280", marginBottom: 8 }}>当前 chunk 总数: {chunkItems.length}</div>
        {chunkItems.length === 0 ? <div className="empty">暂无 chunk</div> : null}
        {chunkItems.slice(0, 20).map((item, idx) => (
          <details key={idx} style={{ marginBottom: 8 }}>
            <summary>{item.title || "untitled"} / {item.source_name || "-"}</summary>
            <div className="report-section-content">{item.chunk_text || "-"}</div>
          </details>
        ))}
      </div>
    </div>
  );
}
