import { chromium } from "playwright";

const URL = "http://localhost:5173/";
const browser = await chromium.launch({
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push("PAGEERR: " + e.message));

await page.goto(URL, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(6000);

// 1) Click the first ACCEPT button in the alert feed
const acceptBtns = page.getByRole("button", { name: "ACCEPT" });
const acceptCount = await acceptBtns.count();
let acceptedVisible = false;
if (acceptCount > 0) {
  await acceptBtns.first().click();
  await page.waitForTimeout(700);
  acceptedVisible = (await page.getByText("ACCEPTED", { exact: false }).count()) > 0;
}

// 2) Click an OVERRIDE button
const overrideBtns = page.getByRole("button", { name: "OVERRIDE" });
let overriddenVisible = false;
if ((await overrideBtns.count()) > 0) {
  await overrideBtns.first().click();
  await page.waitForTimeout(700);
  overriddenVisible = (await page.getByText("OVERRIDDEN", { exact: false }).count()) > 0;
}

// 3) Hover the tactical canvas center to trigger a tooltip (deck.gl)
const deckCanvas = page.locator("canvas").nth(1);
const box = await deckCanvas.boundingBox();
let tooltipText = "";
if (box) {
  // sweep a few points to land on a contact
  for (const [fx, fy] of [[0.52, 0.42], [0.5, 0.5], [0.46, 0.55], [0.58, 0.4]]) {
    await page.mouse.move(box.x + box.width * fx, box.y + box.height * fy);
    await page.waitForTimeout(450);
    const tip = await page.locator("text=/▸/").first();
    if ((await tip.count()) > 0) {
      tooltipText = (await tip.innerText().catch(() => "")) || "";
      if (tooltipText) break;
    }
  }
}

// 4) screenshot the post-interaction state
await page.screenshot({ path: "/tmp/theseus-interacted.png" });

console.log(JSON.stringify({
  acceptCount,
  acceptedVisible,
  overriddenVisible,
  tooltipFound: tooltipText.length > 0,
  errors,
}, null, 2));

await browser.close();
