/**
 * 将 app/styles.css 同步到 public/app-theme.css。
 * 根 layout 会 <link> 引用该文件，避免部分环境下 Next 打包的 CSS chunk 未加载导致「纯 HTML」观感。
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const src = path.join(root, "app", "styles.css");
const destDir = path.join(root, "public");
const dest = path.join(destDir, "app-theme.css");

if (!fs.existsSync(src)) {
  console.error("sync-css: missing", src);
  process.exit(1);
}
fs.mkdirSync(destDir, { recursive: true });
fs.copyFileSync(src, dest);
console.log("sync-css:", dest);
