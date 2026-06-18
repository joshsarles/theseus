import { chromium } from "playwright";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Isolated own-profile playwright harness that can switch the THESEUS scene tab
// before screenshotting (OPERATIONS vs FLEET LEARNING). Own temp profile — never
// the shared MCP profile.
const URL = process.env.SHOOT_URL ?? "http://localhost:5173/";
const OUT = process.env.SHOOT_OUT ?? "/tmp/theseus-scene.png";
const TAB = process.env.SHOOT_TAB ?? ""; // e.g. "FLEET LEARNING"
const HERO = process.env.SHOOT_HERO ?? ""; // e.g. "TACTICAL" centre sub-tab
const WAIT = Number(process.env.SHOOT_WAIT ?? 6500);
const W = Number(process.env.SHOOT_W ?? 1728);
const H = Number(process.env.SHOOT_H ?? 1080);

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
await page.waitForTimeout(2800);

if (HERO) {
  await page.getByRole("button", { name: HERO, exact: true }).first().click().catch((e) => pageErrors.push("hero: " + e.message));
  await page.waitForTimeout(700);
}
if (TAB) {
  await page.getByRole("tab", { name: new RegExp(TAB) }).click().catch((e) => pageErrors.push("tab: " + e.message));
  await page.waitForTimeout(700);
}

await page.waitForTimeout(WAIT);

const probe = await page.evaluate(() => {
  const canvases = Array.from(document.querySelectorAll("canvas")).map((c) => ({ w: c.width, h: c.height }));
  return {
    canvasCount: canvases.length,
    canvases,
    svgCount: document.querySelectorAll("svg").length,
    text: document.body.innerText.replace(/\s+/g, " ").slice(0, 600),
    leafRows: document.querySelectorAll("[data-leaf]").length,
  };
});

await page.screenshot({ path: OUT, fullPage: false });

console.log(
  JSON.stringify(
    {
      ok: consoleErrors.length === 0 && pageErrors.length === 0,
      out: OUT,
      tab: TAB || "operations",
      hero: HERO || null,
      canvasCount: probe.canvasCount,
      canvases: probe.canvases,
      svgCount: probe.svgCount,
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
