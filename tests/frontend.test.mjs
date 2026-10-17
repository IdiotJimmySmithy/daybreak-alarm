import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {escapeHTML,repeatLabel,clockParts,nextAlarm,countdown,editorTemplate,listTemplate,setDraftField} from "../custom_components/daybreak_alarm/frontend/panel.js";

const defaults={label:"Alarm",time:"07:00",enabled:true,repeat_enabled:false,days:[0,1,2,3,4],snooze_enabled:true,snooze_minutes:9,skip_enabled:true,auto_dismiss_enabled:true,ring_minutes:5,sound:{enabled:false,targets:[],areas:[],media_id:"builtin:daybreak",media_type:"music",loop:true,volume_enabled:false,volume:.35,restore_volume:true},lights:{enabled:false,targets:[],brightness_enabled:false,brightness:50},scripts:{enabled:false,targets:[]},notify:{enabled:false,targets:[],actions_enabled:true}};
const catalog={defaults,speakers:[],areas:[],lights:[],scripts:[],notifications:[]};
const record=(config={},runtime={})=>({id:"example",revision:1,config:{...structuredClone(defaults),...config},runtime:{status:"idle",next_at:"2026-10-17T11:00:00+00:00",snooze_until:null,errors:[],...runtime}});
const data=(alarms=[])=>({alarms,timezone:"America/New_York",catalog});

test("HTML metacharacters are escaped",()=>assert.equal(escapeHTML('<img onerror="x">&\''),"&lt;img onerror=&quot;x&quot;&gt;&amp;&#39;"));
test("one-time schedule label",()=>assert.equal(repeatLabel(defaults),"One time"));
test("weekday shortcut",()=>assert.equal(repeatLabel({...defaults,repeat_enabled:true}),"Weekdays"));
test("weekend shortcut",()=>assert.equal(repeatLabel({...defaults,repeat_enabled:true,days:[6,5]}),"Weekends"));
test("every-day shortcut",()=>assert.equal(repeatLabel({...defaults,repeat_enabled:true,days:[0,1,2,3,4,5,6]}),"Every day"));
test("individual repeat days",()=>assert.equal(repeatLabel({...defaults,repeat_enabled:true,days:[0,2,4]}),"Mon, Wed, Fri"));
test("12-hour midnight",()=>assert.deepEqual(clockParts("00:05"),{time:"12:05",period:"AM"}));
test("12-hour noon",()=>assert.deepEqual(clockParts("12:00"),{time:"12:00",period:"PM"}));
test("24-hour display",()=>assert.deepEqual(clockParts("07:05",true),{time:"07:05",period:""}));
test("disabled alarms are excluded from next alarm",()=>assert.equal(nextAlarm([record({enabled:false})]),null));
test("disabled one-time alarm can still be snoozed",()=>assert.equal(nextAlarm([record({enabled:false},{snooze_until:"2026-10-17T11:09:00+00:00"})]).due,"2026-10-17T11:09:00+00:00"));
test("earliest due alarm selected",()=>{const a=record();const b=record({}, {next_at:"2026-10-17T10:00:00+00:00"});b.id="earlier";assert.equal(nextAlarm([a,b]).id,"earlier");});
test("countdown never negative",()=>assert.equal(countdown("2026-01-01T00:00:00Z",Date.parse("2026-01-02T00:00:00Z")),"Due now"));
test("countdown handles day and minute",()=>assert.equal(countdown("2026-01-02T01:03:00Z",Date.parse("2026-01-01T00:00:00Z")),"In 1d 1h 3m"));
test("empty state has a create action",()=>assert.match(listTemplate(data()),/Create an alarm/));
test("alarm labels cannot inject markup",()=>{const html=listTemplate(data([record({label:'<script>alert(1)</script>'})]));assert.ok(!html.includes("<script>"));assert.ok(html.includes("&lt;script&gt;"));});
test("runtime errors cannot inject markup",()=>{const html=listTemplate(data([record({}, {errors:['<img src=x onerror="bad">']})]));assert.ok(!html.includes("<img"));});
test("ringing alarm offers dismiss and optional snooze",()=>{const html=listTemplate(data([record({snooze_enabled:false},{status:"ringing"})]));assert.match(html,/data-action="dismiss"/);assert.doesNotMatch(html,/data-action="snooze"/);});
test("skip button respects feature switch",()=>assert.doesNotMatch(listTemplate(data([record({skip_enabled:false})])),/data-action="skip"/));
test("offline state disables enable switch",()=>assert.match(listTemplate(data([record()]),false,false),/data-enable="example"[^>]+disabled/));
test("editor includes every weekday",()=>{const html=editorTemplate(defaults,catalog,null);for(const day of ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"])assert.ok(html.includes(`aria-label="${day}"`));});
test("editor has independent toggles for every optional feature",()=>{const html=editorTemplate(defaults,catalog,null);for(const field of ["sound.enabled","lights.enabled","scripts.enabled","notify.enabled","repeat_enabled","snooze_enabled","skip_enabled","auto_dismiss_enabled","notify.actions_enabled","sound.loop","sound.volume_enabled"])assert.ok(html.includes(`data-field="${field}"`));});
test("disabled output fields are disabled",()=>{const html=editorTemplate(defaults,catalog,null);assert.ok((html.match(/<fieldset disabled/g)||[]).length>=5);});
test("unsupported speakers remain visible with a reason",()=>{const c={...catalog,speakers:[{id:"media_player.old",name:"Old",can_play:false,can_stop:false}]};assert.match(editorTemplate(defaults,c,null),/Playback or stop unavailable/);});
test("missing targets remain selectable for removal",()=>{const d=structuredClone(defaults);d.sound.targets=["media_player.removed"];assert.match(editorTemplate(d,catalog,null),/media_player.removed/);});
test("script and light behavior is described",()=>{const html=editorTemplate(defaults,catalog,null);assert.match(html,/Lights stay on/);assert.match(html,/Dismiss does not undo script actions/);});
test("form updates one nested field",()=>{const d=structuredClone(defaults);setDraftField(d,"sound.enabled",true);assert.equal(d.sound.enabled,true);assert.equal(d.lights.enabled,false);});
test("form cannot write prototype paths",()=>{const d=structuredClone(defaults);assert.throws(()=>setDraftField(d,"__proto__.polluted",true));assert.equal({}.polluted,undefined);});
test("form rejects unknown fields",()=>assert.throws(()=>setDraftField(structuredClone(defaults),"sound.unknown",true)));
test("panel uses a local bundle without remote imports",()=>{const js=readFileSync(new URL("../custom_components/daybreak_alarm/frontend/panel.js",import.meta.url),"utf8");assert.doesNotMatch(js,/import\s.*https?:/);assert.match(js,/disconnectedCallback/);});

test('background refresh cannot race a save or action', async () => {
  const {DaybreakAlarmPanel} = await import('../custom_components/daybreak_alarm/frontend/panel.js');
  let calls = 0;
  const panel = {_hass: {callWS: async () => { calls++; }}, isConnected: true, _busy: true};
  await DaybreakAlarmPanel.prototype._load.call(panel);
  assert.equal(calls, 0);
});
