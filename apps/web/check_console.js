const { chromium } = require('@playwright/test');

async function getConsoleLogs() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  
  page.on('console', msg => console.log(`BROWSER CONSOLE: ${msg.type()} - ${msg.text()}`));
  page.on('pageerror', error => console.error(`BROWSER ERROR: ${error.message}`));

  try {
    await page.goto('http://localhost:3007/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
  } catch (e) {
    console.error(`GOTO ERROR: ${e.message}`);
  }

  await browser.close();
}

getConsoleLogs();
