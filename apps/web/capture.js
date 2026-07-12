const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const resolutions = [
  { width: 1920, height: 1080, name: '1920x1080' },
  { width: 1440, height: 900, name: '1440x900' },
  { width: 1366, height: 768, name: '1366x768' },
  { width: 1280, height: 800, name: '1280x800' }
];

const routes = [
  { path: '/', name: 'dashboard' },
  { path: '/documents', name: 'documents' },
  { path: '/obligations', name: 'obligations' },
  { path: '/changes', name: 'changes' },
  { path: '/workbench', name: 'workbench' },
  { path: '/controls', name: 'controls' },
  { path: '/agents', name: 'agents' },
];

async function captureScreenshots() {
  const browser = await chromium.launch();
  const baseDir = path.join(__dirname, '..', '..', 'artifacts', 'frontend-before');
  
  if (!fs.existsSync(baseDir)) {
    fs.mkdirSync(baseDir, { recursive: true });
  }

  for (const res of resolutions) {
    const context = await browser.newContext({ viewport: { width: res.width, height: res.height } });
    const page = await context.newPage();
    
    for (const route of routes) {
      try {
        await page.goto(`http://localhost:3007${route.path}`, { waitUntil: 'networkidle' });
        const filePath = path.join(baseDir, `${route.name}-${res.name}.png`);
        await page.screenshot({ path: filePath, fullPage: true });
        console.log(`Captured ${filePath}`);
      } catch (e) {
        console.error(`Failed to capture ${route.name} at ${res.name}: ${e.message}`);
      }
    }
    await context.close();
  }

  await browser.close();
}

captureScreenshots();
