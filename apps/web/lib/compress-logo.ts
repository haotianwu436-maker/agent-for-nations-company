/** 将 data URL 压成适合入库的 JPEG，避免 PUT 请求体过大导致浏览器/网关直接断开（表现为「网络异常」） */
export function compressLogoDataUrl(dataUrl: string, maxWidth = 360, quality = 0.85): Promise<string> {
  if (!dataUrl.startsWith("data:image/")) return Promise.resolve(dataUrl);
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      try {
        const w = Math.min(maxWidth, img.naturalWidth || maxWidth);
        const h = Math.round(((img.naturalHeight || w) * w) / (img.naturalWidth || w));
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = Math.max(1, h);
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(dataUrl);
          return;
        }
        ctx.drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL("image/jpeg", quality));
      } catch {
        resolve(dataUrl);
      }
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
}
