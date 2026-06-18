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
await page.waitForTimeout(2800);
await page.getByRole("tab", { name: /FLEET LEARNING/ }).click();
await page.waitForTimeout(4500);
// crop the gate panels row (bottom third) for a close legibility read
await page.screenshot({ path: "/tmp/theseus-fleet-gates.png", clip: { x: 0, y: 690, width: 1728, height: 390 } });
console.log("cropped fleet gates → /tmp/theseus-fleet-gates.png");
await ctx.close();
