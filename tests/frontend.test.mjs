import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {escapeHTML,repeatLabel,clockParts,nextAlarm,countdown,editorTemplate,listTemplate,setDraftField,cardConfig,cardAlarms,cardTemplate,popupTemplate,DaybreakAlarmPanel,DaybreakAlarmCard} from "../custom_components/daybreak_alarm/frontend/panel.js";

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

test("test controls are confined to settings",()=>{
  assert.doesNotMatch(listTemplate(data([record()])),/data-action="test/);
  assert.doesNotMatch(cardTemplate(data([record()]),cardConfig()),/data-action="test/);
  assert.match(editorTemplate(defaults,catalog,record()),/data-action="test-editor"/);
  assert.match(editorTemplate(defaults,catalog,null),/data-action="test-editor"/);
});
test("visible Edit controls exist for idle and ringing alarms",()=>{
  for(const status of ["idle","ringing","snoozed"]){
    assert.match(listTemplate(data([record({}, {status})])),/>Edit<\/button>/);
    assert.match(cardTemplate(data([record({}, {status})]),cardConfig()),/>Edit<\/button>/);
  }
});
test("phone-only test explains submission versus delivery",()=>{
  const html=editorTemplate(defaults,catalog,null);
  assert.match(html,/Send phone-only test/);assert.match(html,/submission, not delivery/);
});
test("card configuration rejects invalid switch values and filters",()=>{
  assert.throws(()=>cardConfig({show_popup:"false"}));
  assert.throws(()=>cardConfig({alarm_ids:"alarm"}));
  assert.throws(()=>cardConfig({alarm_ids:['<script>']}));
  assert.equal(cardConfig({show_popup:false}).show_popup,false);
});
test("card filter limits visible alarms",()=>{
  const other=record();other.id="other";
  assert.deepEqual(cardAlarms(data([record(),other]),cardConfig({alarm_ids:["other"]})).map(a=>a.id),["other"]);
});
test("card active alarms sort before scheduled ones",()=>{
  const active=record({time:"23:00"},{status:"ringing"});active.id="active";
  assert.equal(cardAlarms(data([record(),active]),cardConfig())[0].id,"active");
});
test("card optional editing and add controls can be hidden",()=>{
  const html=cardTemplate(data([record()]),cardConfig({show_add:false,show_edit:false}));
  assert.doesNotMatch(html,/data-action="new"/);assert.doesNotMatch(html,/data-action="edit"/);
});
test("card labels and titles cannot inject HTML",()=>{
  const html=cardTemplate(data([record({label:'<img src=x onerror=alert(1)>'})]),cardConfig({title:'<svg onload=alert(1)>'}));
  assert.doesNotMatch(html,/<img|<svg onload/);assert.match(html,/&lt;img/);
});
test("card disconnected controls cannot send actions",()=>{
  const html=cardTemplate(data([record({}, {status:"ringing"})]),cardConfig(),false);
  for(const action of ["edit","dismiss","snooze"])
    assert.match(html,new RegExp(`data-action="${action}"[^>]+disabled`));
});
test("popup respects snooze switch and escapes labels",()=>{
  const html=popupTemplate(record({snooze_enabled:false,label:'<img src=x>'}));
  assert.doesNotMatch(html,/data-popup-action="snooze"|<img/);
  assert.match(html,/data-popup-action="dismiss"/);
  assert.match(html,/Hide popup · keep ringing/);
});
test("dashboard popup forwards its ring token",async()=>{
  const calls=[];
  const card={_busy:false,_popupAlarm:record({}, {token:"original-ring"}),_command:async(...args)=>calls.push(args),_syncPopup(){}};
  const button={dataset:{popupAction:"dismiss"},disabled:false};
  await DaybreakAlarmCard.prototype._popupClick.call(card,{target:{closest:()=>button}});
  assert.deepEqual(calls,[["example","dismiss","original-ring"]]);
});
test("phone test sends only notification draft and keeps unsaved edits",async()=>{
  const draft=structuredClone(defaults);draft.label="Unsaved";draft.notify={enabled:true,targets:["mobile_app_phone"],actions_enabled:true};
  const sent=[];
  const panel={_draft:draft,_busy:false,_epoch:0,_renderEditorStatus(){},_flushLoad(){},_hass:{callWS:async msg=>{sent.push(msg);return {results:[{target:"mobile_app_phone",accepted:true,error:""}]};}}};
  await DaybreakAlarmPanel.prototype._testNotification.call(panel);
  assert.equal(sent.length,1);assert.equal(sent[0].type,"daybreak_alarm/test_notification");
  assert.equal(panel._draft.label,"Unsaved");assert.equal(panel._busy,false);
  assert.match(panel._notificationResult,/does not confirm delivery/);
});
test("phone service errors are visible and HTML-safe",async()=>{
  const panel={_draft:{notify:{enabled:true,targets:["mobile_app_phone"]}},_epoch:0,_busy:false,_renderEditorStatus(){},_flushLoad(){},_hass:{callWS:async()=>{throw new Error('<script>bad</script>');}}};
  await DaybreakAlarmPanel.prototype._testNotification.call(panel);
  assert.match(panel._notificationResult,/&lt;script&gt;/);assert.doesNotMatch(panel._notificationResult,/<script>/);assert.equal(panel._busy,false);
});
test("save and test always uses the newly saved alarm ID",async()=>{
  const calls=[];
  const panel={_draft:structuredClone(defaults),_busy:false,_editing:null,shadowRoot:{querySelector:()=>({reportValidity:()=>true})},_data:data(),
    async _mutate(message){calls.push(message);this._data=data([record()]);return {...data([record()]),saved_alarm_id:"example"};},_renderEditor(){},_close(){throw new Error("Test should keep settings open");}};
  const saved=await DaybreakAlarmPanel.prototype._save.call(panel,true);
  assert.equal(saved.id,"example");assert.equal(panel._editing.revision,1);assert.equal(calls[0].type,"daybreak_alarm/save");
});

test("change events during a fetch queue a fresh snapshot",async()=>{
  const panel=Object.create(DaybreakAlarmPanel.prototype);
  let finish,calls=0;
  panel.isConnected=true;panel._epoch=0;panel._generation=0;panel._renderList=()=>{};
  panel._hass={callWS:()=>++calls===1 ? new Promise(resolve=>finish=resolve) : Promise.resolve(data([record({label:"Newest"})]))};
  const first=panel._load();await panel._load();
  finish(data());await first;await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls,2);assert.equal(panel._data.alarms[0].config.label,"Newest");
});
test("a response from a disconnected card is ignored",async()=>{
  const panel=Object.create(DaybreakAlarmPanel.prototype);let finish;
  panel.isConnected=true;panel._epoch=0;panel._generation=0;panel._renderList=()=>assert.fail("Detached card rendered");
  panel._hass={callWS:()=>new Promise(resolve=>finish=resolve)};
  const request=panel._load();panel.isConnected=false;panel._generation++;finish(data());await request;
  assert.equal(panel._data,undefined);
});

// DOM boundaries below are small doubles. These test popup policy, not layout.
function popupCard(alarms,options={}) {
  const card=Object.create(DaybreakAlarmCard.prototype);
  const dialog={open:false,close(){this.open=false;},showModal(){this.open=true;},addEventListener(){}};
  const root={innerHTML:"",querySelector:()=>dialog};
  const error={textContent:"",classList:{toggle(){}}};
  Object.assign(card,{_data:data(alarms),_cardConfig:cardConfig(options),isConnected:true,_connected:true,_busy:false,_draft:null,
    getClientRects:()=>[{}],shadowRoot:{querySelector(selector){return selector==="#popup-root" ? root : selector===".popup-errors" ? error : dialog;},querySelectorAll:()=>[]}});
  return {card,dialog};
}
test("popup-off, card preview, hidden view and ID filters suppress the dialog",()=>{
  const previous=globalThis.document;globalThis.document={visibilityState:"visible"};
  try{
    for(const scenario of ["off","preview","hidden","filter","background"]){
      const {card,dialog}=popupCard([record({}, {status:"ringing",token:scenario})]);
      if(scenario==="off")card._cardConfig.show_popup=false;
      if(scenario==="preview")card._preview=true;
      if(scenario==="hidden")card.getClientRects=()=>[];
      if(scenario==="filter")card._cardConfig.alarm_ids=["different"];
      if(scenario==="background")globalThis.document.visibilityState="hidden";
      card._syncPopup();assert.equal(dialog.open,false,scenario);card._releasePopup();
    }
  }finally{globalThis.document=previous;}
});
test("multiple dashboard cards share one popup and release it on stop",()=>{
  const previous=globalThis.document;globalThis.document={visibilityState:"visible"};
  const alarm=record({}, {status:"ringing",token:"shared-ring"});
  const first=popupCard([alarm]),second=popupCard([alarm]);
  try{
    first.card._syncPopup();second.card._syncPopup();
    assert.equal(first.dialog.open,true);assert.equal(second.dialog.open,false);
    alarm.runtime.status="idle";first.card._syncPopup();second.card._syncPopup();
    assert.equal(first.dialog.open,false);assert.equal(second.dialog.open,false);
  }finally{first.card._releasePopup();second.card._releasePopup();globalThis.document=previous;}
});
test("hiding a popup keeps ringing and a new ring may pop up again",()=>{
  const previous=globalThis.document;globalThis.document={visibilityState:"visible"};
  const alarm=record({}, {status:"ringing",token:"hidden-ring"});
  const {card,dialog}=popupCard([alarm]);
  try{
    card._syncPopup();assert.equal(dialog.open,true);
    card._hidePopup();assert.equal(dialog.open,false);assert.equal(alarm.runtime.status,"ringing");
    card._syncPopup();assert.equal(dialog.open,false);
    alarm.runtime.token="later-ring";card._syncPopup();assert.equal(dialog.open,true);
  }finally{card._releasePopup();globalThis.document=previous;}
});
