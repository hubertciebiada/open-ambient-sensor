// Render the composition frame by frame in headless Chromium.
//   node capture.js stills 0.5 2.4 ...   -> stills/t_<t>.png
//   node capture.js video out.mp4         -> H.264 via ffmpeg (no audio)
const http = require("http"), fs = require("fs"), path = require("path");
const { spawn } = require("child_process");
// Playwright from the local project, or from the global npm root.
const { chromium } = (() => {
  try { return require("playwright"); } catch (e) {
    const root = require("child_process").execSync("npm root -g").toString().trim();
    return require(path.join(root, "playwright"));
  }
})();
const ROOT = __dirname, FPS = 30, DUR = 20.0;
const MIME = { ".html": "text/html", ".js": "application/javascript", ".png": "image/png", ".jpg": "image/jpeg", ".woff2": "font/woff2", ".css": "text/css" };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split("?")[0]));
  fs.readFile(p, (e, d) => {
    if (e) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { "Content-Type": MIME[path.extname(p)] || "application/octet-stream" }); res.end(d);
  });
});
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const port = server.address().port;
  const browser = await chromium.launch({ args: ["--font-render-hinting=none", "--force-color-profile=srgb"] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on("console", (m) => console.log("[page]", m.text()));
  page.on("pageerror", (e) => console.log("[pageerror]", e.message));
  await page.goto(`http://127.0.0.1:${port}/comp.html`);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
  const mode = process.argv[2];
  if (mode === "stills") {
    fs.mkdirSync(path.join(ROOT, "stills"), { recursive: true });
    for (const a of process.argv.slice(3)) {
      const t = parseFloat(a);
      await page.evaluate((t) => window.renderAt(t), t);
      await page.screenshot({ path: path.join(ROOT, "stills", `t_${t.toFixed(3)}.png`) });
      console.log("still", t);
    }
  } else if (mode === "video") {
    const out = process.argv[3] || "video.mp4";
    const n = Math.round(DUR * FPS);
    const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "png", "-i", "-",
      "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", out], { stdio: ["pipe", "inherit", "inherit"] });
    const t0 = Date.now();
    for (let f = 0; f < n; f++) {
      await page.evaluate((t) => window.renderAt(t), f / FPS);
      const buf = await page.screenshot({ type: "png" });
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
      if (f % 60 === 0) console.log(`frame ${f}/${n}  ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    }
    ff.stdin.end();
    await new Promise((r) => ff.on("close", r));
    console.log("video done", out, ((Date.now() - t0) / 1000).toFixed(1) + "s");
  }
  await browser.close(); server.close();
})().catch((e) => { console.error(e); process.exit(1); });
