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
  const panel=page.locator("daybreak-alarm-panel");
  assert.equal(await panel.locator('[data-action="test"]').count(),0);
  await panel.getByRole("button",{name:"Settings for Slow weekend",exact:true}).click();
  await panel.getByRole("button",{name:"Send phone-only test",exact:true}).click();
  await panel.getByText("mobile_app_phone: accepted by Home Assistant",{exact:true}).waitFor();
  await panel.getByRole("button",{name:"Cancel",exact:true}).click();
  await panel.getByRole("button",{name:"Add a dashboard card →",exact:true}).click();
  await panel.getByText(/The card loads automatically with Daybreak Alarms/).waitFor();
  await panel.getByText(/Native controls: Settings/).waitFor();
  await panel.getByRole("button",{name:"Done",exact:true}).click();
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
  await page.getByRole("button",{name:"Dashboard view",exact:true}).click();
  const card=page.locator("daybreak-alarm-card").first();
  await card.getByRole("button",{name:"Settings for Browser smoke test",exact:true}).click();
  await card.getByRole("switch",{name:"Snooze",exact:true}).check();
  await card.getByRole("button",{name:"Save & test alarm",exact:true}).click();
  await card.getByText("Ringing now",{exact:true}).last().waitFor();
  await card.getByRole("button",{name:"Cancel",exact:true}).click();
  await card.locator(".ring-popup[open]").waitFor();
  await card.locator('[data-popup-action="snooze"]').click();
  await card.getByText(/Snoozed until/).waitFor();
  assert.equal(await card.locator(".ring-popup[open]").count(),0);
  await card.getByRole("button",{name:"Dismiss",exact:true}).click();
  // Reconnection to an already-ringing alarm opens the popup; hiding never dismisses.
  await page.evaluate(()=>daybreakPreview.ring("demo-morning"));
  await card.locator(".ring-popup[open]").waitFor();
  await card.locator('[data-popup-action="hide"]').click();
  assert.equal(await page.evaluate(()=>daybreakPreview.snapshot().alarms.find(a=>a.id==="demo-morning").runtime.status),"ringing");
  await card.getByRole("button",{name:"Dismiss",exact:true}).click();
  // Popup-off and alarm-ID filtering do not affect the backend alarm.
  await card.evaluate(element=>element.setConfig({show_popup:false,alarm_ids:["demo-weekend"]}));
  await page.evaluate(()=>daybreakPreview.ring("demo-morning"));
  await card.getByRole("button",{name:"Settings for Slow weekend",exact:true}).waitFor();
  assert.equal(await card.locator(".ring-popup[open]").count(),0);
  assert.equal(await card.getByRole("button",{name:"Settings for A little head start",exact:true}).count(),0);
  await page.evaluate(()=>daybreakPreview.hass.callWS({type:"daybreak_alarm/action",alarm_id:"demo-morning",action:"dismiss"}));
  await card.evaluate(element=>element.setConfig({show_popup:true}));
  // Two cards must not stack two modal dialogs for the same ring.
  await page.evaluate(()=>{const extra=document.createElement("daybreak-alarm-card");extra.setConfig({show_popup:true});extra.hass=daybreakPreview.hass;document.querySelector("#demo-dashboard").append(extra);});
  await page.evaluate(()=>daybreakPreview.ring("demo-weekend"));
  await page.locator("daybreak-alarm-card .ring-popup[open]").waitFor();
  assert.equal(await page.locator("daybreak-alarm-card .ring-popup[open]").count(),1);
  await page.locator('daybreak-alarm-card .ring-popup[open] [data-popup-action="dismiss"]').click();
  await page.waitForFunction(()=>[...document.querySelectorAll("daybreak-alarm-card")].every(c=>!c.shadowRoot.querySelector(".ring-popup[open]")));
  await page.locator("daybreak-alarm-card").last().evaluate(element=>element.remove());
  // HA's visual editor emits config-changed and preserves existing choices.
  await page.evaluate(()=>{const editor=document.createElement("daybreak-alarm-card-editor");editor.setConfig({show_popup:true});editor.addEventListener("config-changed",e=>globalThis.editorResult=e.detail.config);document.querySelector("#demo-dashboard").append(editor);});
  await page.locator("daybreak-alarm-card-editor").getByLabel("Ringing popup",{exact:true}).uncheck();
  assert.equal(await page.evaluate(()=>editorResult.show_popup),false);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(errors,[]);
  console.log("Browser smoke passed: desktop/mobile, editor, weekdays, phone diagnostic, card setup, save/test, popup snooze/dismiss/hide, popup-off/filter, duplicate-card coordination, card editor and theme. Simulated backend only.");
}catch(error){console.error("Browser checks did not pass:",error.message);process.exitCode=1;}
finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
