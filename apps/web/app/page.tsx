import { DEFAULT_BRAND } from "../lib/default-brand";

export default function HomePage() {
  return (
    <div className="card">
      <h1>{DEFAULT_BRAND.name}</h1>
      <p>媒体行业 AI 资讯报告撰写智能体 · 验收驾驶舱。可从左侧导航进入智能体对话、任务、知识库、品牌配置。</p>
      <div className="row">
        <a className="btn btn-primary" href="/login">登录</a>
        <a className="btn" href="/agent">智能体对话</a>
        <a className="btn" href="/jobs">任务列表</a>
        <a className="btn" href="/knowledge">知识库</a>
      </div>
    </div>
  );
}
