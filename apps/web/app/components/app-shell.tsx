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
  const [isCollapsed, setIsCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('sidebar-collapsed') === 'true';
    }
    return false;
  });

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

  // Persist sidebar state
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('sidebar-collapsed', isCollapsed.toString());
    }
  }, [isCollapsed]);

  const navItems = useMemo(
    () => [
      { href: "/agent", label: "智能体对话", icon: "💬" },
      { href: "/knowledge", label: "知识库管理", icon: "📚" },
      { href: "/jobs/new", label: "新建任务", icon: "➕" },
      { href: "/jobs", label: "任务列表", icon: "📋" },
      { href: "/brand", label: "品牌配置", icon: "⚙️" }
    ],
    []
  );

  const minimalLayout = pathname === "/login";

  if (minimalLayout) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        {children}
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-white text-gray-800 overflow-hidden">
      {/* Left Sidebar - Collapsible */}
      <aside className={`flex-shrink-0 bg-white border-r border-gray-200 flex flex-col transition-all duration-300 ${isCollapsed ? 'w-16' : 'w-64'}`}>
        {/* Brand Header - Logo Area */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          {!isCollapsed && (
            <a href="/agent" className="block group flex-1">
              <img 
                src="/logo.png.jpg" 
                alt="中央广播电视总台研究院 CHINA MEDIA GROUP INSTITUTE" 
                className="w-full h-auto max-h-16 object-contain"
              />
            </a>
          )}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 rounded hover:bg-gray-100 transition-colors"
            title={isCollapsed ? "展开" : "折叠"}
          >
            <span className="text-gray-500">{isCollapsed ? '→' : '←'}</span>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {!isCollapsed && (
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-3">
              主要功能
            </div>
          )}
          {navItems.map((item) => {
            const active = isNavActive(pathname, item.href);
            return (
              <a
                key={item.href}
                href={item.href}
                className={`flex items-center ${isCollapsed ? 'justify-center px-2' : 'gap-3 px-3'} py-2.5 rounded-md text-sm transition-all duration-200 ${
                  active
                    ? "bg-blue-50 text-blue-700 border-l-4 border-blue-600"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
                title={isCollapsed ? item.label : undefined}
              >
                <span className="text-base">{item.icon}</span>
                {!isCollapsed && <span className="font-medium">{item.label}</span>}
              </a>
            );
          })}
        </nav>

        {/* Recent Jobs */}
        <div className="p-3 border-t border-gray-200">
          {!isCollapsed && (
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-3">
              最近任务
            </div>
          )}
          {jobs.length === 0 ? (
            !isCollapsed && (
              <div className="px-3 py-3 text-sm text-gray-400 text-center bg-gray-50 rounded-md">
                暂无任务
              </div>
            )
          ) : (
            <div className="space-y-1">
              {jobs.map((j) => (
                <a
                  key={j.id}
                  href={`/jobs/${j.id}`}
                  className={`flex items-center ${isCollapsed ? 'justify-center px-2' : 'justify-between px-3'} py-2 rounded-md text-sm hover:bg-gray-50 transition-colors group`}
                  title={isCollapsed ? `${j.report_type} - ${j.status}` : undefined}
                >
                  {!isCollapsed && (
                    <span className="text-gray-600 group-hover:text-gray-900 truncate flex-1">
                      {j.report_type}
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    j.status === "completed" 
                      ? "bg-green-100 text-green-700" 
                      : j.status === "running"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-gray-100 text-gray-600"
                  }`}>
                    {isCollapsed ? (j.status === 'completed' ? '✓' : j.status === 'running' ? '⏳' : '○') : j.status}
                  </span>
                </a>
              ))}
            </div>
          )}
        </div>

        {/* User Status */}
        <div className="p-3 border-t border-gray-200 bg-gray-50">
          <div className={`flex items-center ${isCollapsed ? 'justify-center px-2' : 'gap-3 px-3'} py-2 rounded-md bg-white border border-gray-200`}>
            <div className={`w-2 h-2 rounded-full ${authed ? "bg-green-500" : "bg-red-500"}`} />
            {!isCollapsed && (
              <>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-700">
                    {authed ? "已登录" : "未登录"}
                  </p>
                  <p className="text-xs text-gray-400 capitalize">{role}</p>
                </div>
                <a
                  href="/login"
                  className="text-xs text-blue-600 hover:text-blue-700 transition-colors"
                >
                  {authed ? "切换" : "登录"}
                </a>
              </>
            )}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-gray-50">
        {/* Top Header - AI Agent Title */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-900">
              总台研究院 · 智媒报告助手
            </h2>
            <span className="text-gray-300">|</span>
            <span className="text-sm text-gray-500">
              {navItems.find(n => isNavActive(pathname, n.href))?.label || "智能对话"}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-50 border border-green-200">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-xs text-green-700 font-medium">系统正常</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-hidden">
          {children}
        </div>
      </main>
    </div>
  );
}
