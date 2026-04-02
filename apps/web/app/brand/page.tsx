"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBase } from "../../lib/api-base";
import { DEFAULT_BRAND } from "../../lib/default-brand";
import { compressLogoDataUrl } from "../../lib/compress-logo";

const MAX_DATA_URL_CHARS = 1_800_000; // 约 1.3MB 原图量级，避免请求体过大

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result || ""));
    r.onerror = () => reject(new Error("read failed"));
    r.readAsDataURL(file);
  });
}

export default function BrandPage() {
  const [brand, setBrand] = useState({ name: DEFAULT_BRAND.name, logo_url: DEFAULT_BRAND.logo_url });
  const [msg, setMsg] = useState("");
  const pasteRef = useRef<HTMLDivElement>(null);

  async function loadBrand() {
    const token = localStorage.getItem("token");
    if (!token) return;
    const res = await fetch(`${getApiBase()}/organization/branding`, { headers: { Authorization: `Bearer ${token}` } });
    if (res.ok) setBrand(await res.json());
  }

  useEffect(() => {
    loadBrand();
  }, []);

  const applyLogoDataUrl = useCallback((dataUrl: string, hint: string) => {
    if (!dataUrl.startsWith("data:image/")) {
      setMsg("请粘贴图片或选择图片文件（不支持纯文本路径）。");
      return;
    }
    if (dataUrl.length > MAX_DATA_URL_CHARS) {
      setMsg("图片过大，请先压缩到约 1MB 以内再粘贴或选择。");
      return;
    }
    setBrand((b) => ({ ...b, logo_url: dataUrl }));
    setMsg(`${hint}（已填入 Logo，请点击下方「保存品牌配置」）`);
  }, []);

  const onPasteLogo = useCallback(
    (e: React.ClipboardEvent) => {
      const text = e.clipboardData?.getData("text/plain")?.trim() || "";
      if (/^[a-zA-Z]:\\/.test(text) || text.startsWith("\\\\")) {
        e.preventDefault();
        setMsg("不能粘贴磁盘路径（如 C:\\...）。请「选择本地图片」，或在看图软件里复制图像再 Ctrl+V。");
        return;
      }
      const items = e.clipboardData?.items;
      if (!items?.length) return;
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (it.kind === "file" && it.type.startsWith("image/")) {
          e.preventDefault();
          const f = it.getAsFile();
          if (!f) continue;
          void fileToDataUrl(f).then((url) => applyLogoDataUrl(url, "已从剪贴板粘贴图片"));
          return;
        }
      }
    },
    [applyLogoDataUrl]
  );

  async function saveBrand() {
    const token = localStorage.getItem("token");
    if (!token) {
      setMsg("请先登录");
      return;
    }
    setMsg("保存中…");
    try {
      let logoUrl = (brand.logo_url || "").trim();
      if (logoUrl.startsWith("data:image")) {
        logoUrl = await compressLogoDataUrl(logoUrl);
      }
      const payload = {
        name: brand.name.trim(),
        logo_url: logoUrl
      };
      const res = await fetch(`${getApiBase()}/organization/branding`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload)
      });
      const raw = await res.text();
      let data: Record<string, unknown> = {};
      try {
        data = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
      } catch {
        setMsg(`保存失败：HTTP ${res.status}，响应不是 JSON（多为代理或路由未命中）：${raw.slice(0, 160)}`);
        return;
      }
      if (!res.ok) {
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((x: { msg?: string }) => x.msg || JSON.stringify(x)).join("; ")
              : data.detail != null
                ? JSON.stringify(data.detail)
                : `HTTP ${res.status}`;
        setMsg(`保存失败：${detail}`);
        return;
      }
      setBrand({
        name: typeof data.name === "string" ? data.name : payload.name,
        logo_url: typeof data.logo_url === "string" ? data.logo_url : payload.logo_url
      });
      setMsg("保存成功，侧边栏与任务页刷新后即可看到新品牌。");
    } catch (e) {
      const err = e instanceof Error ? e.message : String(e);
      setMsg(
        `保存失败：${err || "网络异常"}。请确认 FastAPI 已启动；未配置 env 时请求走同页 /proxy/v1。`
      );
    }
  }

  return (
    <div>
      <div className="card">
        <h2>品牌配置</h2>
        <p>修改单位名称和 Logo，用于任务页、报告页和预览页展示。</p>
      </div>

      <div className="card">
        <label>单位名称</label>
        <input className="input" value={brand.name} onChange={(e) => setBrand({ ...brand, name: e.target.value })} />
        <label>Logo</label>
        <p style={{ fontSize: 13, color: "#6b7280", margin: "4px 0 8px" }}>
          浏览器不能使用 <code>C:\...</code> 本地路径。请任选：在下方灰框内点击后{" "}
          <strong>Ctrl+V</strong> 粘贴截图/图片；或点「选择本地图片」。也可粘贴 <strong>https:// 图片链接</strong> 到最下方输入框。
        </p>
        <div
          ref={pasteRef}
          tabIndex={0}
          role="button"
          className="input"
          style={{
            minHeight: 88,
            display: "grid",
            placeItems: "center",
            cursor: "pointer",
            background: "#f9fafb",
            color: "#6b7280",
            fontSize: 14
          }}
          onPaste={onPasteLogo}
          onClick={() => pasteRef.current?.focus()}
        >
          点击此处聚焦，然后 Ctrl+V 粘贴图片
        </div>
        <label style={{ marginTop: 12, display: "block" }}>或选择本地图片文件</label>
        <input
          className="input"
          type="file"
          accept="image/*"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            try {
              const url = await fileToDataUrl(f);
              applyLogoDataUrl(url, "已读取本地图片");
            } catch {
              setMsg("读取图片失败，请换一张图重试。");
            }
          }}
        />
        <label style={{ marginTop: 12, display: "block" }}>图片链接（https，可选）</label>
        <input
          className="input"
          value={brand.logo_url.startsWith("data:") ? "" : brand.logo_url}
          onChange={(e) => setBrand({ ...brand, logo_url: e.target.value })}
          placeholder="https://example.com/logo.png"
        />
        {brand.logo_url.startsWith("data:") ? (
          <p style={{ fontSize: 12, color: "#6b7280" }}>当前为粘贴/上传的图片（Base64），预览见下方。</p>
        ) : null}
        <div className="row" style={{ marginTop: 8 }}>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setBrand((b) => ({ ...b, logo_url: "" }));
              setMsg("已清除 Logo，保存后生效。");
            }}
          >
            清除 Logo
          </button>
        </div>
        <button type="button" className="btn btn-primary" onClick={saveBrand}>
          保存品牌配置
        </button>
        <div style={{ marginTop: 8 }}>{msg}</div>
      </div>

      <div className="card">
        <h3>品牌效果预览</h3>
        <div className="brand-chip" style={{ maxWidth: 440 }}>
          {brand.logo_url ? <img src={brand.logo_url} alt="preview-logo" className="brand-chip-logo" /> : null}
          <div>
            <div className="brand-chip-title">{brand.name}</div>
            <div className="brand-chip-sub">报告验收与客户演示界面</div>
          </div>
        </div>
      </div>
    </div>
  );
}
