/**
 * frontend-safety lane — verification harness (Brief #1, #7).
 *
 * ISOLATED by construction:
 *   - serves the freshly-built dist/ on an ephemeral localhost port (no live API)
 *   - EACH scenario gets its OWN mkdtemp chromium profile (NOT the shared mcp
 *     profile) and its own context+page, brought to front — this mirrors the
 *     demo's single focused full-screen tab and prevents Playwright's
 *     background-tab requestAnimationFrame throttle from stalling the GSAP
 *     count-up (which masks an otherwise-correct instant tick).
 *   - drives the API entirely via Playwright route interception, so "live" vs
 *     "mock" and the POST-count are deterministic — it NEVER touches a running
 *     :8501 / :5173 / :8080.
 *
 * Asserts, against the REAL built bundle:
 *   1. MOCK   → giant "SIM FEED — NOT LIVE" banner present; header reads SIM FEED.
 *   2. LIVE   → banner ABSENT; header reads LINK LIVE.
 *   3. ACCEPT → record spine leaf count ticks UP immediately (refetch on click),
 *               well inside the 4s poll interval.
 *   4. DBLCLK → a rapid double-click on ACCEPT fires EXACTLY ONE POST /api/decision
 *               and seals exactly one leaf.
 *   5. DROP   → a live link that dies re-raises the banner (no silent masquerade).
 *
 * Run:  node scripts/verify_safety.mjs     (cwd = frontend/ui, after `npm run build`)
 * Exit: 0 all-pass, 1 any failure, 2 harness error.
 */
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, extname, normalize } from "node:path";

const DIST = new URL("../dist/", import.meta.url).pathname;
const MIME = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".woff2": "font/woff2",
  ".svg": "image/svg+xml",
  ".json": "application/json",
};
const BASE_LEAVES = 54;
const PROFILE_DIRS = [];

// --- tiny static server for dist/ (SPA fallback to index.html) -------------
async function serveDist() {
  try {
    await stat(join(DIST, "index.html"));
  } catch {
    throw new Error(`dist/ not built — run \`npm run build\` first (looked in ${DIST})`);
  }
  const server = createServer(async (req, res) => {
    try {
      let p = normalize(decodeURIComponent(req.url.split("?")[0]));
      if (p === "/" || p === "") p = "/index.html";
      let file = join(DIST, p);
      if (!file.startsWith(DIST)) file = join(DIST, "index.html"); // path-escape guard
      let body;
      try {
        body = await readFile(file);
      } catch {
        body = await readFile(join(DIST, "index.html")); // SPA fallback
        file = "index.html";
      }
      res.writeHead(200, { "Content-Type": MIME[extname(file)] ?? "application/octet-stream" });
      res.end(body);
    } catch (e) {
      res.writeHead(500);
      res.end(String(e));
    }
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  return { server, port: server.address().port };
}

// Each scenario: own temp profile, own context, page brought to front.
async function freshPage() {
  const dir = mkdtempSync(join(tmpdir(), "theseus-safety-pw-"));
  PROFILE_DIRS.push(dir);
  const ctx = await chromium.launchPersistentContext(dir, {
    headless: true,
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
  });
  const page = ctx.pages()[0] ?? (await ctx.newPage());
  await page.bringToFront();
  return { ctx, page };
}

// --- the live-contract fixture the route mock returns ----------------------
function stateFixture(leafCount) {
  return {
    ship: "THESEUS",
    posture: "decision-support · human-in-command · SWAN-side",
    systems: [
      { key: "contacts", label: "CONTACTS / TACTICAL", live: true, severity: "critical", detail: "flagged" },
      { key: "machinery", label: "MACHINERY / HM&E", live: true, severity: "nominal", detail: "cbm" },
    ],
    machinery: { model: "theseus-cbm", version: 1, rmse: 0.0038, framework: "sklearn", status: "nominal", promotions: 1 },
    contacts: [
      {
        id: "position_jump:360000000", mmsi: "360000000", type: "position_jump", vessel_class: "other",
        confidence: 0.75, why: "implausible jump", recommended_action: "verify",
        lat: 38.54, lon: -90.25, status: "pending",
      },
      {
        id: "loiter:368171390", mmsi: "368171390", type: "loiter", vessel_class: "other",
        confidence: 0.7, why: "loitered", recommended_action: "verify intent",
        lat: 33.72, lon: -118.22, status: "pending",
      },
    ],
    human_in_command: { pending: 2, note: "watch officer decides" },
    record: {
      verify_ok: true,
      first_bad_leaf: null,
      message: `PASS — ${leafCount} leaves, head 49b5aad0bc53…, merkle ead78b20eed5…`,
      leaf_count: leafCount,
      events: ["ais_anomaly", "data_staged", "model_promoted", "model_trained"],
    },
  };
}

const results = [];
const pass = (name, ok, info = "") => {
  results.push({ name, ok, info });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  — " + info : ""}`);
};

// the rendered headline LEAVES count (GSAP-animated .num inside the LEAVES Field)
async function readSpine(page) {
  return page.evaluate(() => {
    const labels = Array.from(document.querySelectorAll(".eyebrow"));
    const lf = labels.find((n) => n.textContent.trim() === "LEAVES");
    const num = lf?.parentElement?.querySelector(".num");
    const v = num ? num.textContent.trim() : null;
    return v == null || v === "" ? null : Number(v);
  });
}
// count of materialised ruling chips (✓ ACCEPTED / ⟂ OVERRIDDEN), NOT the
// spine leaf-detail text which also contains the word "sealed".
async function rulingChips(page) {
  return page.evaluate(() => {
    const txt = (s) => Array.from(document.querySelectorAll("span")).filter((n) => n.textContent.trim() === s).length;
    return { accepted: txt("✓ ACCEPTED"), overridden: txt("⟂ OVERRIDDEN") };
  });
}

async function scenarioMock(origin) {
  const { ctx, page } = await freshPage();
  try {
    await page.route("**/api/state", (route) => route.abort("failed"));
    await page.route("**/api/decision", (route) => route.abort("failed"));
    await page.goto(origin + "/", { waitUntil: "domcontentloaded" });

    const banner = page.locator("[data-sim-banner]");
    await banner.waitFor({ state: "visible", timeout: 12000 }).catch(() => {});
    const bannerVisible = await banner.isVisible().catch(() => false);
    const bannerConn = await banner.getAttribute("data-conn").catch(() => null);
    const bannerText = bannerVisible ? (await banner.innerText()).replace(/\s+/g, " ").trim() : "";

    pass("A1 mock → giant SIM-FEED banner visible", bannerVisible && /SIM FEED/i.test(bannerText),
      `conn=${bannerConn} text="${bannerText.slice(0, 40)}"`);
    pass("A2 mock → banner says NOT LIVE", /NOT LIVE/i.test(bannerText), bannerText.slice(0, 40));

    const headerLink = await page.evaluate(() => {
      const m = document.querySelector("header")?.innerText.match(/LINK LIVE|SIM FEED|LINKING|LINK STALE/);
      return m ? m[0] : "?";
    });
    pass("A3 mock → header shows SIM FEED, never LINK LIVE", headerLink === "SIM FEED", `header link="${headerLink}"`);
  } finally {
    await ctx.close();
  }
}

async function scenarioLive(origin) {
  const { ctx, page } = await freshPage();
  let leafCount = BASE_LEAVES;
  let decisionPosts = 0;
  try {
    await page.route("**/api/state", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(stateFixture(leafCount)) }));
    await page.route("**/api/decision", async (route) => {
      decisionPosts += 1;
      leafCount += 1; // the server seals exactly one leaf per POST
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    });

    await page.goto(origin + "/", { waitUntil: "domcontentloaded" });
    await page.locator("header").getByText("LINK LIVE", { exact: false }).waitFor({ timeout: 12000 });

    pass("B1 live → SIM-FEED banner ABSENT", (await page.locator("[data-sim-banner]").count()) === 0,
      `banner nodes=${await page.locator("[data-sim-banner]").count()}`);

    const headerLink = await page.evaluate(() => {
      const m = document.querySelector("header")?.innerText.match(/LINK LIVE|SIM FEED|LINKING|LINK STALE/);
      return m ? m[0] : "?";
    });
    pass("B2 live → header reads LINK LIVE", headerLink === "LINK LIVE", headerLink);

    // B3 — single ACCEPT ticks the spine immediately (refetch on click). We poll
    // the rendered count for <2s — far inside the 4s poll, so any tick can only
    // come from the click's refetch(), never a scheduled poll.
    const spineBefore = await readSpine(page);
    const accept = page.getByRole("button", { name: "ACCEPT", exact: true });
    await accept.first().waitFor({ timeout: 8000 });
    await accept.first().click();

    let firstTickMs = null;
    const samples = [];
    const t0 = Date.now();
    while (Date.now() - t0 < 2000) {
      const now = await readSpine(page);
      samples.push(`${Date.now() - t0}=${now}`);
      if (now != null && spineBefore != null && now > spineBefore) {
        firstTickMs = Date.now() - t0;
        break;
      }
      await page.waitForTimeout(50);
    }
    const spineAfter = await readSpine(page);
    const chips1 = await rulingChips(page);
    pass("B3 ACCEPT → spine ticks UP immediately (refetch, < 4s poll)",
      firstTickMs != null && spineAfter > spineBefore && firstTickMs < 1500 && chips1.accepted === 1 && decisionPosts === 1,
      `leaves ${spineBefore}→${spineAfter} in ${firstTickMs}ms · accepted chips=${chips1.accepted} · posts=${decisionPosts}`);

    // B4 — rapid DOUBLE-CLICK on the next pending ACCEPT must fire EXACTLY ONE
    // POST and seal EXACTLY ONE leaf (debounce + synchronous in-flight guard).
    const postsBefore = decisionPosts;
    const leavesBefore = leafCount;
    const next = page.getByRole("button", { name: "ACCEPT", exact: true }).first();
    await next.waitFor({ timeout: 8000 });
    await next.dblclick({ delay: 20 }).catch(async () => {
      await next.click({ force: true }).catch(() => {});
      await next.click({ force: true }).catch(() => {});
    });
    await page.waitForTimeout(1400); // past the 1s debounce window + settle

    pass("B4 double-click ACCEPT → exactly ONE POST /api/decision", decisionPosts - postsBefore === 1,
      `posts ${postsBefore}→${decisionPosts} (Δ=${decisionPosts - postsBefore})`);
    pass("B4b double-click → server sealed exactly ONE leaf", leafCount - leavesBefore === 1,
      `server leaf_count ${leavesBefore}→${leafCount} (Δ=${leafCount - leavesBefore})`);
    const chips2 = await rulingChips(page);
    pass("B4c double-click → exactly ONE new ruling chip", chips2.accepted === 2,
      `accepted chips ${chips1.accepted}→${chips2.accepted}`);
  } finally {
    await ctx.close();
  }
}

async function scenarioDrop(origin) {
  const { ctx, page } = await freshPage();
  let alive = true;
  try {
    await page.route("**/api/state", (route) => {
      if (alive) route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(stateFixture(BASE_LEAVES)) });
      else route.abort("failed");
    });
    await page.route("**/api/decision", (route) => route.abort("failed"));
    await page.goto(origin + "/", { waitUntil: "domcontentloaded" });
    await page.locator("header").getByText("LINK LIVE", { exact: false }).waitFor({ timeout: 12000 });
    const noBannerWhileLive = (await page.locator("[data-sim-banner]").count()) === 0;

    alive = false; // kill the link; the 4s poll will fail → conn flips to stale
    const banner = page.locator("[data-sim-banner]");
    await banner.waitFor({ state: "visible", timeout: 12000 }).catch(() => {});
    const bannerConn = await banner.getAttribute("data-conn").catch(() => null);
    pass("C1 link drop → SIM-FEED banner re-appears (no silent masquerade)",
      noBannerWhileLive && (await banner.isVisible().catch(() => false)) && bannerConn === "stale",
      `live→drop, conn after drop=${bannerConn}`);
  } finally {
    await ctx.close();
  }
}

async function main() {
  const { server, port } = await serveDist();
  const origin = `http://127.0.0.1:${port}`;
  try {
    await scenarioMock(origin);
    await scenarioLive(origin);
    await scenarioDrop(origin);
  } finally {
    server.close();
    for (const d of PROFILE_DIRS) {
      try {
        rmSync(d, { recursive: true, force: true });
      } catch {
        /* best-effort temp cleanup */
      }
    }
  }

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (failed.length) {
    console.log("FAILURES: " + failed.map((f) => f.name).join("; "));
    process.exit(1);
  }
}

main().catch((e) => {
  console.error("HARNESS ERROR:", e);
  process.exit(2);
});
