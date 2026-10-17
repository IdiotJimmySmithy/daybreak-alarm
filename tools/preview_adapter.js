/* Preview only: in-memory sample data. No network or device control. */
const sampleDefaults = __DEFAULTS__;
const sampleCatalog = {
  defaults: sampleDefaults,
  speakers: [
    {id:"media_player.bedroom",name:"Bedroom speaker",area_id:"bedroom",state:"idle",is_speaker:true,can_play:true,can_stop:true,can_pause:true,can_volume:true,members:[]},
    {id:"media_player.kitchen",name:"Kitchen speaker",area_id:"kitchen",state:"idle",is_speaker:true,can_play:true,can_stop:true,can_pause:true,can_volume:true,members:[]},
    {id:"media_player.whole_home",name:"Whole home group",area_id:null,state:"idle",is_speaker:true,can_play:true,can_stop:true,can_pause:true,can_volume:true,members:["media_player.bedroom","media_player.kitchen"]}
  ],
  areas:[{id:"bedroom",name:"Bedroom"},{id:"kitchen",name:"Kitchen"}],
  lights:[{id:"light.bedroom",name:"Bedroom lights",area_id:"bedroom",state:"off"}],
  scripts:[{id:"script.morning",name:"Morning routine",state:"off"}],
  notifications:[{id:"mobile_app_phone",name:"My phone"}]
};
const subscribers = new Set();
const demoZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
function demoNext(c) {
  if(!c.enabled)return null;
  const [hour,minute]=c.time.split(":").map(Number);
  for(let offset=0;offset<8;offset++){
    const d=new Date();d.setDate(d.getDate()+offset);d.setHours(hour,minute,0,0);
    if(d>Date.now() && (!c.repeat_enabled || c.days.includes((d.getDay()+6)%7)))return d.toISOString();
  }
  return null;
}
function demoRecord(id,changes) {
  const c={...structuredClone(sampleDefaults),...changes};
  return {id,revision:1,config:c,runtime:{next_at:demoNext(c),status:"idle",token:null,started_at:null,snooze_until:null,end_at:null,last_fired:null,last_result:null,errors:[],skipped_at:null}};
}
let demoAlarms=[
  demoRecord("demo-morning",{label:"A little head start",time:"06:45",repeat_enabled:true,days:[0,1,2,3,4],sound:{...sampleDefaults.sound,enabled:true,targets:["media_player.bedroom"]},lights:{...sampleDefaults.lights,enabled:true,targets:["light.bedroom"]}}),
  demoRecord("demo-weekend",{label:"Slow weekend",time:"09:00",repeat_enabled:true,days:[5,6],notify:{...sampleDefaults.notify,enabled:true,targets:["mobile_app_phone"]}}),
  demoRecord("demo-winddown",{label:"Time to wind down",time:"22:00",enabled:false,repeat_enabled:true,days:[0,1,2,3,4,5,6]})
];
const snapshot=()=>({alarms:structuredClone(demoAlarms),timezone:demoZone,server_time:new Date().toISOString(),catalog:structuredClone(sampleCatalog)});
const changed=()=>subscribers.forEach(cb=>cb({data:{}}));
const previewHass={
  themes:{darkMode:true},
  connection:{async subscribeEvents(cb){subscribers.add(cb);return ()=>subscribers.delete(cb);}},
  async callWS(msg){
    if(msg.type==="daybreak_alarm/get")return snapshot();
    if(msg.type==="daybreak_alarm/save"){
      const c=structuredClone(msg.config);
      for(const section of ["sound","lights","scripts","notify"]){
        const s=c[section];
        if(s.enabled && !s.targets.length && !(section==="sound" && s.areas.length))throw new Error(`Choose a target for ${section}.`);
      }
      if(c.repeat_enabled && !c.days.length)throw new Error("Choose at least one repeat day.");
      if(msg.alarm_id){
        const old=demoAlarms.find(a=>a.id===msg.alarm_id);
        if(!old || old.revision!==msg.revision)throw new Error("Alarm changed elsewhere. Reopen it.");
        const replacement=demoRecord(old.id,c);replacement.revision=old.revision+1;
        demoAlarms=demoAlarms.map(a=>a.id===old.id ? replacement : a);
      }else demoAlarms.push(demoRecord(crypto.randomUUID(),c));
    }else if(msg.type==="daybreak_alarm/delete"){
      demoAlarms=demoAlarms.filter(a=>a.id!==msg.alarm_id);
    }else if(msg.type==="daybreak_alarm/action"){
      const a=demoAlarms.find(a=>a.id===msg.alarm_id);if(!a)throw new Error("Alarm not found");
      const r=a.runtime;
      if(["enable","disable"].includes(msg.action)){
        a.config.enabled=msg.action==="enable";a.revision++;r.next_at=demoNext(a.config);r.status="idle";r.snooze_until=null;
      }else if(msg.action==="test"){
        r.status="ringing";r.last_result="test";
        setTimeout(()=>{if(r.status==="ringing"){r.status="idle";changed();}},10000);
      }else if(msg.action==="dismiss"){
        r.status="idle";r.snooze_until=null;
      }else if(msg.action==="snooze"){
        r.status="snoozed";r.snooze_until=new Date(Date.now()+a.config.snooze_minutes*60000).toISOString();
      }else if(msg.action==="skip"){
        r.skipped_at=r.next_at;
        if(!a.config.repeat_enabled){a.config.enabled=false;a.revision++;r.next_at=null;}
        else{const d=new Date(r.next_at);do{d.setDate(d.getDate()+1);}while(!a.config.days.includes((d.getDay()+6)%7));r.next_at=d.toISOString();}
      }
    }
    changed();return snapshot();
  }
};
document.querySelector("daybreak-alarm-panel").hass=previewHass;
document.querySelector("#preview-theme").addEventListener("click",()=>{previewHass.themes.darkMode=!previewHass.themes.darkMode;document.querySelector("daybreak-alarm-panel").hass=previewHass;});
