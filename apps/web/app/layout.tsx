import "./styles.css";
import React from "react";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <main style={{ maxWidth: 980, margin: "0 auto", padding: 24 }}>{children}</main>
      </body>
    </html>
  );
}
