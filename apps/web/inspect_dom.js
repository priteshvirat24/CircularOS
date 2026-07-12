const { chromium } = require('@playwright/test');

async function inspectDOM() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  
  try {
    await page.goto('http://localhost:3007/', { waitUntil: 'networkidle' });
    // Wait for the dynamic import to complete
    await page.waitForTimeout(2000);
    
    // Evaluate and get the HTML of the right side container
    const rightSideHtml = await page.evaluate(() => {
      // The container has class "relative h-[600px] w-full z-0 lg:scale-110 xl:scale-125 origin-center"
      const el = document.querySelector('.h-\\[600px\\]');
      return el ? el.outerHTML : 'Element not found';
    });
    
    console.log(rightSideHtml);
  } catch (e) {
    console.error(`ERROR: ${e.message}`);
  }

  await browser.close();
}

inspectDOM();
