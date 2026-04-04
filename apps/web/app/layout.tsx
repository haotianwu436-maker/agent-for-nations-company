import "./globals.css";
import "./styles.css";
import React, { Suspense } from "react";
import AppShell from "./components/app-shell";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        {/* 静态样式兜底：不依赖 /_next/static/css 分包，避免部分环境出现「只有 HTML、无全局样式」 */}
        <link rel="stylesheet" href="/app-theme.css" />
      </head>
      <body>
        {/*
          AppShell 内使用 usePathname()：在根 Layout 中必须由 Suspense 包裹，
          否则部分环境下会出现子路由（如 /jobs/new）白屏、不挂载。
        */}
        <Suspense
          fallback={
            <div className="shell-suspense-fallback" role="status" aria-live="polite">
              页面加载中…
            </div>
          }
        >
          <AppShell>{children}</AppShell>
        </Suspense>
      </body>
    </html>
  );
}
