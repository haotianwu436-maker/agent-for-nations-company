"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { getApiBase } from "../../lib/api-base";
import { DEFAULT_BRAND } from "../../lib/default-brand";

type JobItem = {
  id: string;
  status: string;
  report_type: string;
};

function decodeRoleFromToken(token: string | null): string {
  if (!token) return "guest";
  try {
    const part = token.split(".")[1];
    if (!part) return "member";
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    if (!json) return "member";
    const payload = JSON.parse(json);
    return payload.role || "member";
  } catch {
    return "member";
  }
}

/** 避免 /jobs 同时匹配 /jobs/new；详情页归入「任务列表」高亮 */
function isNavActive(pathname: string, href: string): boolean {
  if (!pathname) return false;
  if (href === "/jobs/new") {
    return pathname === "/jobs/new";
  }
  if (href === "/jobs") {
    if (pathname === "/jobs") return true;
    if (pathname.startsWith("/jobs/new")) return false;
    return /^\/jobs\/[^/]+/.test(pathname);
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "";
  const [brand, setBrand] = useState({ name: DEFAULT_BRAND.name, logo_url: DEFAULT_BRAND.logo_url });
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [authed, setAuthed] = useState(false);
  const [role, setRole] = useState("guest");

  useEffect(() => {
    const token = localStorage.getItem("token");
    setAuthed(Boolean(token));
    setRole(decodeRoleFromToken(token));
    if (!token) return;
    Promise.all([
      fetch(`${getApiBase()}/organization/branding`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${getApiBase()}/report-jobs`, { headers: { Authorization: `Bearer ${token}` } })
    ])
      .then(async ([brandRes, jobsRes]) => {
        if (brandRes.ok) setBrand(await brandRes.json());
        if (jobsRes.ok) {
          const data = await jobsRes.json();
          setJobs((data.items || []).slice(0, 8));
        }
      })
      .catch(() => null);
  }, []);

  const navItems = useMemo(
    () => [
      { href: "/jobs/new", label: "新建任务" },
      { href: "/jobs", label: "任务列表" },
      { href: "/knowledge", label: "知识库" },
      { href: "/brand", label: "品牌配置" }
    ],
    []
  );

  const minimalLayout = pathname === "/login";

  if (minimalLayout) {
    return <section className="auth-layout">{children}</section>;
  }

  return (
    <div className="app-shell">
      <aside className="left-nav">
        <a className="brand-chip" href="/jobs">
          {brand.logo_url ? <img src={brand.logo_url} alt="logo" className="brand-chip-logo" /> : null}
          <div>
            <div className="brand-chip-title">{brand.name}</div>
            <div className="brand-chip-sub">AI 报告验收驾驶舱</div>
          </div>
        </a>

        <nav className="nav-stack">
          {navItems.map((item) => (
            <a
              key={item.href}
              className={`nav-item ${isNavActive(pathname, item.href) ? "nav-item-active" : ""}`}
              href={item.href}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="side-section">
          <div className="side-title">最近任务</div>
          {jobs.length === 0 ? (
            <div className="side-muted">暂无任务</div>
          ) : (
            jobs.map((j) => (
              <a key={j.id} className="side-job" href={`/jobs/${j.id}`}>
                <span>{j.report_type}</span>
                <span className={`status-pill status-${j.status}`}>{j.status}</span>
              </a>
            ))
          )}
        </div>

        <div className="side-footer">
          <div>登录状态：{authed ? "已登录" : "未登录"}</div>
          <div>账号角色：{role}</div>
          <a href="/login">登录页</a>
        </div>
      </aside>
      <section className="main-pane">{children}</section>
    </div>
  );
}
