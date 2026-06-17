import { chromium } from "playwright";
import { mkdtempSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const URL = process.env.SHOOT_URL ?? "http://localhost:5173/";
const OUT = process.env.SHOOT_OUT ?? "/tmp/theseus-shot.png";
const WAIT = Number(process.env.SHOOT_WAIT ?? 5500);
const W = Number(process.env.SHOOT_W ?? 1728);
const H = Number(process.env.SHOOT_H ?? 1080);
// optional: comma list of actions like "ACCEPT:0,OVERRIDE:0"
const ACT = process.env.SHOOT_ACT ?? "";

mkdirSync("/tmp", { recursive: true });
const userDataDir = mkdtempSync(join(tmpdir(), "theseus-pw-"));

const ctx = await chromium.launchPersistentContext(userDataDir, {
  headless: true,
  viewport: { width: W, height: H },
  deviceScaleFactor: 2,
  args: [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--enable-unsafe-swiftshader",
  ],
});

const page = ctx.pages()[0] ?? (await ctx.newPage());

const consoleErrors = [];
const pageErrors = [];
const failedRequests = [];
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("pageerror", (e) => pageErrors.push(e.message));
page.on("requestfailed", (r) => {
  const f = r.failure();
  failedRequests.push(`${r.url()} :: ${f ? f.errorText : "?"}`);
});

await page.goto(URL, { waitUntil: "networkidle", timeout: 30000 }).catch((e) => {
  pageErrors.push("goto: " + e.message);
});
await page.waitForTimeout(WAIT);

// optionally exercise the human-in-command climax
if (ACT) {
  for (const step of ACT.split(",")) {
    const [kind, idxRaw] = step.split(":");
    const idx = Number(idxRaw ?? 0);
    const label = kind.trim().toUpperCase();
    const btns = page.getByRole("button", { name: label });
    const count = await btns.count();
    if (count > idx) {
      await btns.nth(idx).click().catch(() => {});
      await page.waitForTimeout(900);
    }
  }
  await page.waitForTimeout(700);
}

const probe = await page.evaluate(() => {
  const canvases = Array.from(document.querySelectorAll("canvas")).map((c) => ({
    w: c.width,
    h: c.height,
  }));
  const bodyFont = getComputedStyle(document.body).fontFamily;
  return {
    canvasCount: canvases.length,
    canvases,
    bodyFont,
    text: document.body.innerText.replace(/\s+/g, " ").slice(0, 500),
    leafRows: document.querySelectorAll("[data-leaf]").length,
  };
});

await page.screenshot({ path: OUT, fullPage: false });

console.log(
  JSON.stringify(
    {
      ok: consoleErrors.length === 0 && pageErrors.length === 0,
      out: OUT,
      bodyFont: probe.bodyFont,
      canvasCount: probe.canvasCount,
      canvases: probe.canvases,
      leafRows: probe.leafRows,
      consoleErrors: consoleErrors.slice(0, 8),
      pageErrors,
      failedRequests: failedRequests.filter((r) => !r.includes("favicon")).slice(0, 8),
      textSample: probe.text,
    },
    null,
    2,
  ),
);

await ctx.close();
