import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
page.on("console", (msg) => console.log("[console]", msg.type(), msg.text()));
page.on("pageerror", (err) => console.log("[pageerror]", err.message));

await page.goto("http://127.0.0.1:8799/", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);
const primeraTarjeta = page.locator(".tarjeta-doc").first();
await primeraTarjeta.waitFor({ state: "visible", timeout: 15000 });
await primeraTarjeta.click();
await page.waitForSelector("svg.typst-doc", { timeout: 30000 });
await page.waitForTimeout(1500);

const resultado = await page.evaluate(async () => {
  if (!window.__probarRenderDom2) return { error: "no está definido" };
  return await window.__probarRenderDom2();
});
console.log("RESULTADO round 2:", JSON.stringify(resultado, null, 2));

await page.screenshot({ path: "/home/andres/proyectos-personales/doctyp/web/.tmp-dom2.png" });

await browser.close();
