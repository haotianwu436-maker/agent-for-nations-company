const envRaw = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();

function stripTrailingSlash(s: string): string {
  return s.replace(/\/$/, "");
}

/**
 * 未设置 NEXT_PUBLIC_API_BASE_URL 时走同源 `/proxy/v1`（app/proxy/v1/[...path]/route.ts → FastAPI）。
 * 若 .env 仍写 `http://本页域名/api/v1`（旧代理路径），自动改为 `/proxy/v1`，避免继续 404。
 * 直连后端：`http://127.0.0.1:8000/api/v1` 等其它 origin 保持不变。
 * API_PROXY_ORIGIN：仅 origin，不要带 /api/v1。
 */
export function getApiBase(): string {
  const trimmed = stripTrailingSlash(envRaw);

  if (trimmed) {
    if (typeof window !== "undefined") {
      try {
        const u = new URL(trimmed);
        const p = u.pathname.replace(/\/$/, "") || "/";
        if (p === "/api/v1" && u.origin === window.location.origin) {
          return `${window.location.origin}/proxy/v1`;
        }
      } catch {
        /* 非 URL 则原样 */
      }
    }
    return trimmed;
  }

  if (typeof window !== "undefined") return `${window.location.origin}/proxy/v1`;
  return "http://127.0.0.1:8000/api/v1";
}
