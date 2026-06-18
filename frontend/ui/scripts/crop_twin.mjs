import { chromium } from "playwright";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const ud = mkdtempSync(join(tmpdir(), "theseus-pw-"));
const ctx = await chromium.launchPersistentContext(ud, {
  headless: true, viewport: { width: 1728, height: 1080 }, deviceScaleFactor: 2,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"],
});
const page = ctx.pages()[0];
await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
await page.waitForTimeout(7000);
// the centre twin hero region (between left rail 320 and right spine 340)
await page.screenshot({ path: "/tmp/theseus-twin-crop.png", clip: { x: 320, y: 64, width: 1068, height: 470 } });
console.log("cropped twin → /tmp/theseus-twin-crop.png");
await ctx.close();
