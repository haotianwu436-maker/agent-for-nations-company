"use client";

export default function NewJobError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="card" style={{ maxWidth: 520 }}>
      <h2>新建任务页加载失败</h2>
      <p style={{ color: "#6b7280", fontSize: 14 }}>{error.message || "未知错误"}</p>
      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn btn-primary" type="button" onClick={() => reset()}>
          重试
        </button>
        <a className="btn" href="/jobs">
          返回任务列表
        </a>
      </div>
    </div>
  );
}
