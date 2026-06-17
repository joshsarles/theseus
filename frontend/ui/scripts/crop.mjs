import { chromium } from "playwright";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const ud = mkdtempSync(join(tmpdir(), "theseus-pw-"));
const ctx = await chromium.launchPersistentContext(ud, {
  headless: true, viewport: { width: 1728, height: 1080 }, deviceScaleFactor: 2,
  args: ["--use-gl=angle","--use-angle=swiftshader","--enable-webgl","--ignore-gpu-blocklist","--enable-unsafe-swiftshader"],
});
const page = ctx.pages()[0];
await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
await page.waitForTimeout(5500);
// seal one decision so a human leaf is visible in the crop
const acc = page.getByRole("button", { name: "ACCEPT" });
if (await acc.count()) { await acc.first().click(); await page.waitForTimeout(900); }
// crop the right spine (last 340px) + header
await page.screenshot({ path: "/tmp/theseus-spine.png", clip: { x: 1388, y: 0, width: 340, height: 1080 } });
// crop the header strip
await page.screenshot({ path: "/tmp/theseus-header.png", clip: { x: 0, y: 0, width: 1728, height: 66 } });
// crop the tactical plot center-top
await page.screenshot({ path: "/tmp/theseus-tac.png", clip: { x: 320, y: 66, width: 1068, height: 480 } });
await ctx.close();
console.log("crops written");
