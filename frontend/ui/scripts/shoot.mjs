import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const URL = process.env.SHOOT_URL ?? "http://localhost:5173/";
const OUT = process.env.SHOOT_OUT ?? "/tmp/theseus-shot.png";
const WAIT = Number(process.env.SHOOT_WAIT ?? 6500);
const W = Number(process.env.SHOOT_W ?? 1920);
const H = Number(process.env.SHOOT_H ?? 1080);

mkdirSync("/tmp", { recursive: true });

const browser = await chromium.launch({
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({
  viewport: { width: W, height: H },
  deviceScaleFactor: 2,
});

const consoleErrors = [];
const consoleWarnings = [];
const pageErrors = [];
const failedRequests = [];

page.on("console", (msg) => {
  const type = msg.type();
  if (type === "error") consoleErrors.push(msg.text());
  else if (type === "warning") consoleWarnings.push(msg.text());
});
page.on("pageerror", (err) => pageErrors.push(err.message));
page.on("requestfailed", (req) => {
  const f = req.failure();
  failedRequests.push(`${req.url()} :: ${f ? f.errorText : "unknown"}`);
});

await page.goto(URL, { waitUntil: "networkidle", timeout: 30000 }).catch((e) => {
  pageErrors.push("goto: " + e.message);
});

// give R3F + deck.gl + framer-motion time to mount and animate
await page.waitForTimeout(WAIT);

// probe for the 3D canvas + deck canvas presence
const probe = await page.evaluate(() => {
  const canvases = Array.from(document.querySelectorAll("canvas")).map((c) => ({
    w: c.width,
    h: c.height,
    cls: c.className,
  }));
  const text = document.body.innerText.slice(0, 400);
  return { canvasCount: canvases.length, canvases, text };
});

await page.screenshot({ path: OUT, fullPage: false });

console.log(JSON.stringify({
  ok: consoleErrors.length === 0 && pageErrors.length === 0,
  out: OUT,
  canvasCount: probe.canvasCount,
  canvases: probe.canvases,
  consoleErrors,
  pageErrors,
  failedRequests: failedRequests.filter((r) => !r.includes("favicon")),
  consoleWarnings: consoleWarnings.slice(0, 6),
  textSample: probe.text.replace(/\s+/g, " ").trim(),
}, null, 2));

await browser.close();
