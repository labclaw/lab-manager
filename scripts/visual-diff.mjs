#!/usr/bin/env node
/**
 * Visual diff pipeline: Stitch HTML designs vs real website.
 *
 * Usage:
 *   npx playwright install chromium   # one-time setup
 *   node scripts/visual-diff.mjs [--stitch http://localhost:9999] [--app http://localhost:8001]
 *
 * Output: .stitch/visual-diff/ with side-by-side screenshots and an HTML report.
 */

import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, existsSync, readdirSync } from 'fs';
import { resolve, basename } from 'path';

// --- Config ---
const STITCH_BASE = process.argv.includes('--stitch')
  ? process.argv[process.argv.indexOf('--stitch') + 1]
  : 'http://localhost:9999';

const APP_BASE = process.argv.includes('--app')
  ? process.argv[process.argv.indexOf('--app') + 1]
  : 'http://localhost:8001';

// Map: Stitch HTML filename -> app route
const PAGE_MAP = {
  'dashboard.html': '/',
  'inventory.html': '/inventory',
  'orders.html': '/orders',
  'documents.html': '/documents',
  'upload.html': '/upload',
  'review.html': '/review',
  'login.html': null,   // skip — requires logout
  'setup.html': null,   // skip — requires fresh DB
};

const OUT_DIR = resolve(process.cwd(), '.stitch/visual-diff');
const WIDTH = 1440;
const HEIGHT = 900;

async function main() {
  mkdirSync(OUT_DIR, { recursive: true });

  // Auto-detect Stitch pages from .stitch/designs/
  const designDir = resolve(process.cwd(), '.stitch/designs');
  let pages = Object.entries(PAGE_MAP);
  if (existsSync(designDir)) {
    const htmlFiles = readdirSync(designDir).filter(f => f.endsWith('.html'));
    for (const f of htmlFiles) {
      if (!PAGE_MAP.hasOwnProperty(f)) {
        console.log(`  [warn] ${f} not in PAGE_MAP, skipping`);
      }
    }
  }

  const browser = await chromium.launch();
  const results = [];

  for (const [stitchFile, appRoute] of pages) {
    if (appRoute === null) {
      console.log(`  [skip] ${stitchFile} (requires special state)`);
      continue;
    }

    const pageName = basename(stitchFile, '.html');
    console.log(`  [diff] ${pageName}: ${STITCH_BASE}/${stitchFile} vs ${APP_BASE}${appRoute}`);

    // Screenshot Stitch design
    const stitchPage = await browser.newPage();
    await stitchPage.setViewportSize({ width: WIDTH, height: HEIGHT });
    try {
      await stitchPage.goto(`${STITCH_BASE}/${stitchFile}`, { waitUntil: 'networkidle', timeout: 10000 });
    } catch {
      await stitchPage.goto(`${STITCH_BASE}/${stitchFile}`, { waitUntil: 'load', timeout: 10000 });
    }
    await stitchPage.waitForTimeout(500);
    const stitchPath = resolve(OUT_DIR, `${pageName}-stitch.png`);
    await stitchPage.screenshot({ path: stitchPath, fullPage: true });
    await stitchPage.close();

    // Screenshot app
    const appPage = await browser.newPage();
    await appPage.setViewportSize({ width: WIDTH, height: HEIGHT });
    try {
      await appPage.goto(`${APP_BASE}${appRoute}`, { waitUntil: 'networkidle', timeout: 10000 });
    } catch {
      await appPage.goto(`${APP_BASE}${appRoute}`, { waitUntil: 'load', timeout: 10000 });
    }
    await appPage.waitForTimeout(500);
    const appPath = resolve(OUT_DIR, `${pageName}-app.png`);
    await appPage.screenshot({ path: appPath, fullPage: true });
    await appPage.close();

    results.push({ pageName, stitchPath: `${pageName}-stitch.png`, appPath: `${pageName}-app.png` });
  }

  await browser.close();

  // Generate HTML report
  const reportHtml = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Stitch vs App — Visual Diff Report</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f0f23; color: #e2e2e9; font-family: system-ui, sans-serif; padding: 2rem; }
  h1 { font-size: 1.5rem; margin-bottom: 1.5rem; color: #8b5cf6; }
  .page-section { margin-bottom: 3rem; }
  .page-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 0.75rem; text-transform: capitalize; }
  .compare { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  .compare .label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: #a0a0b8; margin-bottom: 0.5rem; }
  .compare img { width: 100%; border: 1px solid #2d2d44; border-radius: 0.75rem; }
  .timestamp { font-size: 0.7rem; color: #a0a0b8; margin-top: 2rem; }
</style>
</head>
<body>
<h1>Stitch Design vs Production — Visual Diff</h1>
${results.map(r => `
<div class="page-section">
  <div class="page-title">${r.pageName}</div>
  <div class="compare">
    <div>
      <div class="label">Stitch Design</div>
      <img src="${r.stitchPath}" alt="${r.pageName} stitch" />
    </div>
    <div>
      <div class="label">Production App</div>
      <img src="${r.appPath}" alt="${r.pageName} app" />
    </div>
  </div>
</div>`).join('\n')}
<div class="timestamp">Generated: ${new Date().toISOString()}</div>
</body>
</html>`;

  const reportPath = resolve(OUT_DIR, 'report.html');
  writeFileSync(reportPath, reportHtml);
  console.log(`\n  Report: ${reportPath}`);
  console.log(`  Screenshots: ${results.length} pages compared`);
}

main().catch(err => {
  console.error('Visual diff failed:', err);
  process.exit(1);
});
