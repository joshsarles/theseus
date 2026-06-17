import { chromium } from "playwright";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const ud = mkdtempSync(join(tmpdir(), "theseus-pw-"));
const ctx = await chromium.launchPersistentContext(ud, {
  headless: true,
  viewport: { width: 1728, height: 1080 },
  deviceScaleFactor: 2,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"],
});
const page = ctx.pages()[0];
await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
await page.waitForTimeout(6000);
const r = await page.evaluate(() => {
  const cv = document.querySelector("canvas");
  const parent = cv?.parentElement;
  const sect = cv?.closest("section");
  const main = document.querySelector("main");
  return {
    canvasCss: cv ? { cw: cv.clientWidth, ch: cv.clientHeight, aw: cv.width, ah: cv.height } : null,
    parentRect: parent ? { w: Math.round(parent.getBoundingClientRect().width), h: Math.round(parent.getBoundingClientRect().height) } : null,
    sectRect: sect ? { w: Math.round(sect.getBoundingClientRect().width), h: Math.round(sect.getBoundingClientRect().height) } : null,
    mainCols: main ? getComputedStyle(main).gridTemplateColumns : null,
  };
});
console.log(JSON.stringify(r, null, 2));
await ctx.close();
