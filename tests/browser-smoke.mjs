/* Optional REAL browser smoke test. Not part of the dependency-free unit suite.
   Run: npm install --no-save playwright && npx playwright install chromium
        node tests/browser-smoke.mjs
*/
import assert from "node:assert/strict";
import {createRequire} from "node:module";
import {createServer} from "node:http";
import {readFile} from "node:fs/promises";
const require=createRequire(import.meta.url);
let chromium;
try { ({chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH || (process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES ? process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES+"/playwright" : "playwright"))); }
catch {console.error("Browser checks not run: install Playwright and Chromium first.");process.exit(2);}
const html=await readFile(new URL("../preview.html",import.meta.url));
const server=createServer((req,res)=>{res.writeHead(200,{"Content-Type":"text/html; charset=utf-8"});res.end(html);});
await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
let browser;
try{
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  page.on("dialog",dialog=>dialog.accept());
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.getByRole("heading",{name:"Alarms",exact:true}).waitFor();
  await page.getByRole("button",{name:"Add alarm"}).click();
  await page.getByLabel("Alarm time",{exact:true}).fill("08:15");
  await page.locator('[data-field="label"]').fill("Browser smoke test");
  await page.getByRole("switch",{name:"Repeat",exact:true}).check();
  await page.getByLabel("Saturday",{exact:true}).check();
  await page.getByRole("switch",{name:"Snooze",exact:true}).uncheck();
  await page.getByRole("button",{name:"Save",exact:true}).click();
  await page.getByRole("button",{name:"Edit Browser smoke test at 08:15",exact:true}).waitFor();
  await page.getByRole("button",{name:"Edit Browser smoke test at 08:15",exact:true}).click();
  assert.equal(await page.getByRole("switch",{name:"Snooze",exact:true}).isChecked(),false);
  assert.equal(await page.getByLabel("Saturday",{exact:true}).isChecked(),true);
  await page.getByRole("button",{name:"Cancel",exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.getByRole("button",{name:"Add alarm"}).click();
  const dialog=await page.getByRole("dialog").boundingBox();
  assert.ok(dialog.x>=0 && dialog.width<=390);
  await page.keyboard.press("Escape");
  await page.getByRole("button",{name:"Light / dark"}).click();
  assert.equal(await page.locator("daybreak-alarm-panel").getAttribute("data-theme"),"light");
  assert.deepEqual(errors,[]);
  console.log("Browser smoke checks passed: desktop, mobile, editor, weekdays, toggles, persistence in preview, and theme.");
}catch(error){console.error("Browser checks did not pass:",error.message);process.exitCode=1;}
finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
