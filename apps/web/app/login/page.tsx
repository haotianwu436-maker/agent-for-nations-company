"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getApiBase } from "../../lib/api-base";
import Image from "next/image";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("owner@demo.com");
  const [password, setPassword] = useState("demo1234");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiHint, setApiHint] = useState("");

  useEffect(() => setApiHint(getApiBase()), []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 20000);
    
    const apiBase = getApiBase();
    console.log("[Login] API Base:", apiBase);
    
    try {
      const url = `${apiBase}/auth/login`;
      console.log("[Login] Request URL:", url);
      
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
        signal: ctrl.signal
      });
      console.log("[Login] Response status:", res.status);
      const data = await res.json().catch((e) => {
        console.error("[Login] Parse error:", e);
        return {};
      });
      console.log("[Login] Response data:", data);
      
      if (!res.ok) {
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((x: { msg?: string }) => x.msg || JSON.stringify(x)).join("; ")
              : data.detail
                ? JSON.stringify(data.detail)
                : "";
        setMessage(`登录失败（HTTP ${res.status}）${detail ? `：${detail}` : ""}`);
        return;
      }
      if (!data.access_token) {
        setMessage("登录失败：接口未返回 access_token，请检查后端版本。");
        return;
      }
      localStorage.setItem("token", data.access_token);
      setMessage("登录成功，正在跳转…");
      router.push("/jobs/new");
    } catch (e: unknown) {
      console.error("[Login] Error:", e);
      if (e instanceof Error && e.name === "AbortError") {
        setMessage(
          "登录超时（20s）。请先确认：1）API 已启动；2）启动 API 的终端里已设置 DATABASE_URL=postgresql+psycopg://...@127.0.0.1:5432/media_ai（不要用 localhost，否则登录可能一直卡住）。"
        );
      } else {
        setMessage(
          `登录失败：无法连接 ${getApiBase()}。请确认：1）本机已启动 API；2）新标签页打开 http://127.0.0.1:8000/healthz 应显示 {"status":"ok"}；3）若 .env 里写了 NEXT_PUBLIC_API_BASE_URL 指向错误地址也会失败。`
        );
      }
    } finally {
      window.clearTimeout(timer);
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f8fafc] flex">
      {/* 左侧品牌区域 */}
      <div className="hidden lg:flex lg:w-[45%] xl:w-[40%] bg-white flex-col justify-between p-12 xl:p-16 border-r border-slate-100">
        <div>
          {/* Logo */}
          <div className="w-64 h-20 relative mb-4">
            <Image
              src="/logo.png.jpg"
              alt="中央广播电视总台研究院"
              fill
              className="object-contain"
              priority
            />
          </div>
          <p className="text-base text-slate-500 font-medium ml-1">新媒体研究部</p>
        </div>

        <div className="space-y-6">
          <div>
            <h1 className="text-3xl xl:text-4xl font-bold text-slate-900 leading-tight mb-3">
              企业级 RAG<br />智能报告系统
            </h1>
            <p className="text-lg text-slate-500">Enterprise RAG Intelligence Platform</p>
          </div>
          <p className="text-slate-400 text-sm leading-relaxed max-w-sm">
            基于大语言模型的智能报告生成平台，助力媒体研究高效产出专业分析报告。
          </p>
        </div>

        <div className="flex items-center gap-6 text-sm text-slate-400">
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
            安全可靠
          </span>
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            高效智能
          </span>
        </div>
      </div>

      {/* 右侧登录区域 */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-[420px]">
          {/* 移动端 Logo */}
          <div className="lg:hidden flex flex-col items-center mb-10">
            <div className="w-48 h-16 relative mb-3">
              <Image
                src="/logo.png.jpg"
                alt="中央广播电视总台研究院"
                fill
                className="object-contain"
                priority
              />
            </div>
            <p className="text-sm text-slate-500">新媒体研究部</p>
          </div>

          {/* 登录卡片 */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-8 lg:p-10">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-slate-900 mb-2">欢迎登录</h2>
              <p className="text-sm text-slate-500">请使用您的账号密码登录系统</p>
            </div>

            {/* 默认账号提示 */}
            <div className="bg-slate-50 rounded-lg p-4 mb-6">
              <p className="text-xs text-slate-400 mb-3 uppercase tracking-wider font-medium">默认体验账号</p>
              <div className="space-y-2">
                <div className="flex items-center gap-3 text-sm text-slate-700">
                  <svg className="w-4 h-4 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" /></svg>
                  <span className="font-medium">owner@demo.com</span>
                </div>
                <div className="flex items-center gap-3 text-sm text-slate-700">
                  <svg className="w-4 h-4 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                  <span className="font-medium">demo1234</span>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3 pt-3 border-t border-slate-200">
                接口：{apiHint || "加载中…"}
              </p>
            </div>

            {/* 错误提示 */}
            {message && (
              <div className={`mb-6 p-4 rounded-lg text-sm ${message.includes("成功") ? "bg-green-50 text-green-700 border border-green-100" : "bg-red-50 text-red-700 border border-red-100"}`}>
                {message}
              </div>
            )}

            {/* 登录表单 */}
            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">邮箱地址</label>
                <div className="relative">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="请输入邮箱"
                    className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">登录密码</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="请输入密码"
                    className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                  >
                    {showPassword ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                    )}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 bg-[#2563eb] hover:bg-blue-700 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/25 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-2"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    登录系统
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 pt-6 border-t border-slate-100 text-center">
              <button
                onClick={() => router.push("/jobs/new")}
                className="text-sm text-slate-500 hover:text-[#2563eb] font-medium transition-colors"
              >
                跳过登录去创建任务 →
              </button>
            </div>
          </div>

          {/* 版权信息 */}
          <p className="text-center text-xs text-slate-400 mt-8">
            © 2026 中央广播电视总台研究院新媒体研究部 · 版权所有
          </p>
        </div>
      </div>
    </div>
  );
}
