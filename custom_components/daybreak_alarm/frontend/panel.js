/* Daybreak Alarms — a self-contained Home Assistant custom panel. No CDN. */
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const FRONTEND_VERSION = "0.1.2";
export const escapeHTML = (value = "") => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const e = escapeHTML;
const clone = value => JSON.parse(JSON.stringify(value));
const checked = value => value ? " checked" : "";
const disabled = value => value ? " disabled" : "";
const ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" aria-hidden="true"><circle cx="12" cy="13" r="8"/><path d="M12 8v5l3 2M5 3 2 6m17-3 3 3M6 20l-2 2m14-2 2 2"/></svg>';

export function repeatLabel(c) {
  if (!c.repeat_enabled) return "One time";
  const days = [...c.days].sort((a,b) => a-b);
  if (days.length === 7) return "Every day";
  if (days.join() === "0,1,2,3,4") return "Weekdays";
  if (days.join() === "5,6") return "Weekends";
  return days.map(d => DAYS[d].slice(0,3)).join(", ");
}

export function clockParts(time, use24 = false) {
  const [h,m] = time.split(":").map(Number);
  return {time: `${use24 ? String(h).padStart(2,"0") : h % 12 || 12}:${String(m).padStart(2,"0")}`, period: use24 ? "" : h < 12 ? "AM" : "PM"};
}

export function nextAlarm(alarms) {
  return alarms.map(a => ({...a, due: a.runtime.snooze_until || (a.config.enabled ? a.runtime.next_at : null)}))
    .filter(a => a.due).sort((a,b) => Date.parse(a.due) - Date.parse(b.due))[0] || null;
}

export function countdown(when, now = Date.now()) {
  const minutes = Math.max(0, Math.ceil((Date.parse(when)-now)/60000));
  if (minutes < 1) return "Due now";
  const d = Math.floor(minutes/1440), h = Math.floor(minutes%1440/60), m = minutes%60;
  return `In ${[d && `${d}d`, h && `${h}h`, (m || (!d && !h)) && `${m}m`].filter(Boolean).join(" ")}`;
}

function dateLabel(when, tz) {
  return when ? new Intl.DateTimeFormat(undefined, {timeZone:tz, weekday:"short", month:"short", day:"numeric", hour:"numeric", minute:"2-digit"}).format(new Date(when)) : "";
}

function toggle(field, label, value, description = "") {
  return `<label class="setting"><span><span class="setting-name">${e(label)}</span>${description ? `<span class="hint">${e(description)}</span>` : ""}</span><input class="switch" role="switch" type="checkbox" data-field="${e(field)}" aria-label="${e(label)}"${checked(value)}></label>`;
}

function choices(items, selected, field, empty, kind = "") {
  const known = new Set(items.map(x=>x.id));
  const all = [...items, ...selected.filter(id=>!known.has(id)).map(id=>({id,name:id,state:"unavailable"}))];
  if (!all.length) return `<p class="hint empty-choice">${e(empty)}</p>`;
  return `<div class="choices">${all.map(item => {
    const unsupported = kind === "speaker" && !item.members?.length && (!item.can_play || (!item.can_stop && !item.can_pause));
    const unavailable = item.state === "unavailable";
    const note = unsupported ? "Playback or stop unavailable" : unavailable ? "Currently unavailable" : item.id;
    return `<label class="choice"><input type="checkbox" data-list="${e(field)}" value="${e(item.id)}"${checked(selected.includes(item.id))}${disabled(unsupported && !selected.includes(item.id))}><span>${e(item.name)}<small>${e(note)}</small></span></label>`;
  }).join("")}</div>`;
}

export function editorTemplate(d, catalog, record, error = "") {
  const soundChoice = d.sound.media_id.startsWith("builtin:") ? d.sound.media_id : "custom";
  const areas = (catalog.areas || []).filter(area => catalog.speakers.some(s=>s.area_id===area.id && s.is_speaker));
  return `<dialog aria-labelledby="editor-title"><form id="alarm-form">
    <div class="modal-head"><button type="button" class="text-button" data-action="close">Cancel</button><h2 id="editor-title">${record ? "Edit alarm" : "New alarm"}</h2><button type="submit" class="text-button accent" id="save-alarm">Save</button></div>
    <div class="editor-body">
      ${error ? `<p class="error" role="alert">${e(error)}</p>` : ""}
      ${record?.runtime.status !== "idle" && record ? '<p class="notice">Saving changes will stop this alarm’s current ringing or snooze.</p>' : ""}
      <label class="time-picker"><span class="sr-only">Alarm time</span><input type="time" required aria-label="Alarm time" data-field="time" value="${e(d.time)}"></label>
      <div class="section"><label class="field"><span>Label</span><input type="text" maxlength="80" required data-field="label" value="${e(d.label)}" placeholder="Morning alarm"></label>${toggle("enabled", "Alarm enabled", d.enabled)}</div>
      <div class="section">${toggle("repeat_enabled", "Repeat", d.repeat_enabled, d.repeat_enabled ? "Choose the days this alarm should ring" : "Ring once, then turn off")}
        <fieldset${disabled(!d.repeat_enabled)} class="subsection ${d.repeat_enabled ? "" : "hidden"}"><legend class="sr-only">Repeat days</legend><div class="days">${DAYS.map((day,i)=>`<label class="day"><input type="checkbox" data-list="days" value="${i}" aria-label="${day}"${checked(d.days.includes(i))}><span>${day.slice(0,2)}</span></label>`).join("")}</div><p class="hint">Each alarm has its own weekly schedule.</p></fieldset>
      </div>
      <div class="section">${toggle("sound.enabled", "Sound", d.sound.enabled, "Play only on your selected speakers")}
        <fieldset${disabled(!d.sound.enabled)} class="subsection ${d.sound.enabled ? "" : "hidden"}">
          <label class="field"><span>Alarm sound</span><select data-choice="sound" aria-label="Alarm sound">${[["builtin:daybreak","Daybreak · warm chimes"],["builtin:soft","Soft · gentle notes"],["builtin:pulse","Pulse · clear beeps"],["custom","Custom media / URL"]].map(([value,label])=>`<option value="${value}"${value===soundChoice ? " selected" : ""}>${label}</option>`).join("")}</select></label>
          ${soundChoice === "custom" ? `<label class="field stacked"><span>Media URL or identifier</span><input data-field="sound.media_id" type="text" required value="${e(d.sound.media_id)}" placeholder="https://… or media-source://…"></label><label class="field"><span>Media type</span><input data-field="sound.media_type" value="${e(d.sound.media_type)}" required placeholder="music"></label>` : ""}
          <h3>Speakers & groups</h3>${choices(catalog.speakers || [],d.sound.targets,"sound.targets","Connect speakers to Home Assistant to see them here.","speaker")}
          <details><summary>Or choose a room</summary>${choices(areas,d.sound.areas,"sound.areas","Assign speakers to areas in Home Assistant first.")}</details>
          <p class="hint">Room selection includes audio players in that area. Existing groups containing unselected speakers are blocked to keep audio in your chosen rooms.</p>
          ${toggle("sound.loop","Repeat sound",d.sound.loop,"Custom audio repeats when the player reports it has finished")}
          ${toggle("sound.volume_enabled","Set alarm volume",d.sound.volume_enabled,"Off keeps the speaker’s existing volume")}
          <label class="field ${d.sound.volume_enabled ? "" : "hidden"}"><span>Volume <output>${Math.round(d.sound.volume*100)}%</output></span><input type="range" min="0" max="1" step="0.05" data-field="sound.volume" aria-label="Alarm volume" value="${d.sound.volume}"${disabled(!d.sound.volume_enabled)}></label>
          ${d.sound.volume_enabled ? toggle("sound.restore_volume","Restore volume afterwards",d.sound.restore_volume) : ""}
        </fieldset>
      </div>
      <div class="section">${toggle("lights.enabled","Lights",d.lights.enabled,"Turn on selected lights when the alarm rings")}
        <fieldset${disabled(!d.lights.enabled)} class="subsection ${d.lights.enabled ? "" : "hidden"}">${choices(catalog.lights||[],d.lights.targets,"lights.targets","No lights are available.")}${toggle("lights.brightness_enabled","Set brightness",d.lights.brightness_enabled)}<label class="field ${d.lights.brightness_enabled ? "" : "hidden"}"><span>Brightness (%)</span><input type="number" min="1" max="100" data-field="lights.brightness" value="${d.lights.brightness}"${disabled(!d.lights.brightness_enabled)}></label><p class="hint">Lights stay on after dismissing the alarm.</p></fieldset>
      </div>
      <div class="section">${toggle("scripts.enabled","Scripts",d.scripts.enabled,"Run your existing Home Assistant routines")}
        <fieldset${disabled(!d.scripts.enabled)} class="subsection ${d.scripts.enabled ? "" : "hidden"}">${choices(catalog.scripts||[],d.scripts.targets,"scripts.targets","Create a script in Home Assistant to see it here.")}<p class="hint">Scripts run on each ring, including after snooze. Dismiss does not undo script actions.</p></fieldset>
      </div>
      <div class="section">${toggle("notify.enabled","App notifications",d.notify.enabled,"Send to selected Home Assistant companion apps")}
        <fieldset${disabled(!d.notify.enabled)} class="subsection ${d.notify.enabled ? "" : "hidden"}">${choices(catalog.notifications||[],d.notify.targets,"notify.targets","No phone notification actions found. Open the Home Assistant companion app, allow notifications, and refresh this page.")}${toggle("notify.actions_enabled","Notification controls",d.notify.actions_enabled,"Show Dismiss and, when enabled, Snooze")}${toggle("notify.prompt_delivery","Prompt delivery on Android",d.notify.prompt_delivery,"Request immediate delivery; an offline phone will not receive a delayed alert. Does not override silent mode or Focus.")}
          <button type="button" class="secondary" data-action="test-notification"${disabled(!d.notify.targets.length)}>Send phone-only test</button><p class="hint">Uses your selected phones without saving or running other outputs. The test stays on your phone until you clear it.</p><div id="notification-result" role="status" aria-live="polite"></div>
          <details><summary>Phone did not receive it?</summary><p class="hint">Check the exact notify.mobile_app_* target above, notification permission for the Home Assistant app, Focus / Do Not Disturb, and the app’s notification settings. If Home Assistant accepts the action, that confirms submission, not delivery. Try the same action in Developer tools → Actions to check delivery independently.</p></details>
        </fieldset>
      </div>
      <div class="section">${toggle("snooze_enabled","Snooze",d.snooze_enabled)}<label class="field ${d.snooze_enabled ? "" : "hidden"}"><span>Snooze minutes</span><input type="number" min="1" max="120" required data-field="snooze_minutes" value="${d.snooze_minutes}"${disabled(!d.snooze_enabled)}></label>${toggle("skip_enabled","Allow skip next",d.skip_enabled)}${toggle("auto_dismiss_enabled","Auto-dismiss",d.auto_dismiss_enabled,"Stop ringing after a time limit")}<label class="field ${d.auto_dismiss_enabled ? "" : "hidden"}"><span>Ring minutes</span><input type="number" min="1" max="120" required data-field="ring_minutes" value="${d.ring_minutes}"${disabled(!d.auto_dismiss_enabled)}></label></div>
      <div class="section test-section"><h3>Test this alarm</h3><p class="hint">Saves these settings, then runs all enabled outputs now. Audio stops after 10 seconds. Lights and scripts are not undone; test notifications stay on your phone.</p><button type="button" class="secondary" data-action="test-editor">Save & test alarm</button><div id="test-status" role="status" aria-live="polite"></div></div>
      ${record ? `<details class="technical"><summary>Automation ID</summary><code>${e(record.id)}</code><p class="hint">Use this ID with the Daybreak alarm actions in Home Assistant.</p></details><button class="delete-button" type="button" data-action="delete" data-id="${e(record.id)}">Delete alarm</button>` : ""}
      <p class="editor-foot">All times use your Home Assistant timezone.</p>
    </div>
  </form></dialog>`;
}

export function listTemplate(data, use24 = false, connected = true) {
  const alarms = [...data.alarms].sort((a,b) => Number(b.runtime.status!=="idle") - Number(a.runtime.status!=="idle") || a.config.time.localeCompare(b.config.time));
  const next = nextAlarm(alarms);
  const nextParts = next ? clockParts(new Intl.DateTimeFormat("en-GB",{timeZone:data.timezone,hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).format(new Date(next.due)), use24) : null;
  return `<header class="topbar"><div class="brand"><button class="menu icon-button" aria-label="Open sidebar" data-action="menu">☰</button>${ICON}<span>DAYBREAK</span></div><button class="icon-button" data-action="format" aria-label="Switch to ${use24 ? "12" : "24"}-hour time">${use24 ? "24h" : "12h"}</button></header>
    <main><div class="title-row"><div><p class="eyebrow">YOUR DAILY RHYTHM</p><h1>Alarms</h1></div><button class="primary" data-action="new"${disabled(!connected)}><span aria-hidden="true">＋</span> Add alarm</button></div><button class="text-button accent dashboard-setup" data-action="dashboard-setup">Add a dashboard card →</button>
    ${!connected ? '<p class="error" role="alert">Disconnected. Reconnecting… Your saved alarms continue on Home Assistant.</p>' : ""}
    <section class="next-card" aria-label="Next alarm"><div><p class="eyebrow">${next ? "NEXT ALARM" : "A QUIET MOMENT"}</p>${next ? `<div class="next-time">${nextParts.time}<small>${nextParts.period}</small></div><p class="next-label">${e(next.config.label)} <span>· ${e(dateLabel(next.due,data.timezone))}</span></p>` : '<div class="next-empty">Your next morning starts here.</div><p class="next-label">Set an alarm and make it your own.</p>'}</div><div class="next-orbit">${ICON}${next ? `<span>${countdown(next.due)}</span>` : ""}</div></section>
    <div class="list-heading"><h2>All alarms <span>${alarms.length}</span></h2><span>${e(data.timezone.replaceAll("_"," "))}</span></div>
    <section class="alarm-list" aria-label="Alarms">${alarms.length ? alarms.map(a=>{
      const c = a.config, r = a.runtime, time = clockParts(c.time,use24);
      const active = r.status !== "idle";
      const tags = [[c.sound.enabled,"Sound"],[c.lights.enabled,"Lights"],[c.scripts.enabled,"Scripts"],[c.notify.enabled,"Notify"]].filter(([on])=>on).map(([,name])=>name);
      return `<article class="alarm ${!c.enabled && !active ? "off" : ""} ${active ? "active" : ""}" data-alarm-id="${e(a.id)}">
        <div class="alarm-line"><button class="alarm-edit" data-action="edit" data-id="${e(a.id)}" aria-label="Edit ${e(c.label)} at ${e(c.time)}"><span class="alarm-time">${time.time}<small>${time.period}</small></span><span class="alarm-label">${e(c.label)} <span>· ${e(repeatLabel(c))}</span></span></button><input class="switch" type="checkbox" role="switch" data-enable="${e(a.id)}" aria-label="Enable ${e(c.label)}"${checked(c.enabled)}${disabled(!connected)}></div>
        <div class="alarm-bottom"><span class="tags">${active ? `<span class="status">${r.status === "ringing" ? "Ringing now" : `Snoozed · ${e(dateLabel(r.snooze_until,data.timezone))}`}</span>` : tags.length ? tags.map(name=>`<span>${name}</span>`).join("") : '<span>No outputs enabled</span>'}</span><div class="row-actions"><button data-action="edit" data-id="${e(a.id)}" aria-label="Settings for ${e(c.label)}">Edit</button>${active ? `${r.status==="ringing" && c.snooze_enabled ? `<button data-action="snooze" data-id="${e(a.id)}">Snooze</button>` : ""}<button class="accent" data-action="dismiss" data-id="${e(a.id)}">Dismiss</button>` : `${c.enabled && c.skip_enabled && r.next_at ? `<button data-action="skip" data-id="${e(a.id)}">Skip next</button>` : ""}`}</div></div>
        ${r.skipped_at && r.next_at ? `<p class="hint">Next: ${e(dateLabel(r.next_at,data.timezone))}</p>` : ""}
        ${["missed","interrupted"].includes(r.last_result) ? `<p class="notice">${r.last_result==="missed" ? "An occurrence was missed while Home Assistant was unavailable." : "Ringing was interrupted by a restart. Audio was not replayed."}</p>` : ""}
        ${r.errors?.length ? `<details class="alarm-errors"><summary>${r.errors.length} output ${r.errors.length===1 ? "issue" : "issues"} · view details</summary><ul>${r.errors.map(error=>`<li>${e(error)}</li>`).join("")}</ul></details>` : ""}
      </article>`;
    }).join("") : `<div class="empty-state">${ICON}<h3>A fresh start.</h3><p>Add your first alarm. Pick the days, choose a sound,<br>and decide what wakes up with you.</p><button class="text-button accent" data-action="new"${disabled(!connected)}>Create an alarm →</button></div>`}</section>
    <footer>Scheduled on Home Assistant <span>·</span> Your dashboard can be closed.</footer></main>`;
}

export function setDraftField(draft, path, value) {
  const keys = path.split(".");
  if (keys.some(k=>["__proto__","prototype","constructor"].includes(k))) throw new Error("Invalid field");
  let object = draft;
  for (const key of keys.slice(0,-1)) {
    if (!Object.hasOwn(object,key) || typeof object[key] !== "object") throw new Error("Unknown field");
    object = object[key];
  }
  if (!Object.hasOwn(object, keys.at(-1))) throw new Error("Unknown field");
  object[keys.at(-1)] = value;
}

const STYLES = `
  .secondary{background:var(--accent-bg);color:var(--accent);padding:12px 16px;border-radius:10px;font-size:13px;margin:10px 0}.test-section{padding:15px}.test-section h3{font-size:14px}.dashboard-setup{margin:0 0 18px}.setup-body{padding:22px;font-size:14px;line-height:1.7}.setup-body code,.setup-body pre{display:block;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--surface);padding:12px;border-radius:8px;user-select:all;font-size:12px}.row-actions{flex-wrap:wrap}#test-status:empty,#notification-result:empty{display:none}
  :host{--bg:#111215;--surface:#1b1c20;--surface2:#24252a;--line:#303137;--text:#f6f4ef;--muted:#a4a4ad;--accent:#ffc078;--accent-bg:#362b20;--danger:#ff8585;display:block;height:100%;color:var(--text);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark;background:var(--bg)}
  :host([data-theme=light]){--bg:#f7f6f2;--surface:#fff;--surface2:#f2f1ed;--line:#e3e1db;--text:#242421;--muted:#71716b;--accent:#9c530e;--accent-bg:#fff0db;--danger:#b32828;color-scheme:light}
  *{box-sizing:border-box}button,input,select{font:inherit}button{cursor:pointer}button:disabled,input:disabled{cursor:not-allowed;opacity:.45}button{color:inherit}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:4px}button{border:0}svg{width:25px;height:25px}h1,h2,h3,p{margin:0}.app{height:100%;overflow:auto;padding-bottom:env(safe-area-inset-bottom)}.topbar{height:76px;padding:0 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:12px;font-size:11px;font-weight:650;letter-spacing:3px}.brand>svg{color:var(--accent)}.icon-button{background:transparent;color:var(--muted);padding:10px;font-size:13px;border-radius:9px}.menu{display:none}main{max-width:950px;margin:0 auto;padding:44px 40px}.title-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;gap:20px}.eyebrow{font-size:10px;letter-spacing:2px;font-weight:650;color:var(--muted)}h1{font-size:44px;font-weight:600;letter-spacing:-1.6px;margin-top:6px}.primary{background:var(--accent);color:#241a11;border-radius:13px;padding:13px 19px;font-size:14px;font-weight:650;white-space:nowrap}.primary span{font-size:21px;font-weight:400;vertical-align:-1px;margin-right:4px}.next-card{border:1px solid var(--line);border-radius:22px;padding:29px 32px;display:flex;justify-content:space-between;align-items:center;gap:18px;background:radial-gradient(ellipse at 100% 100%,#aa6c2622,transparent 70%),var(--surface)}.next-card .eyebrow{color:var(--accent)}.next-time{font-size:62px;font-weight:300;letter-spacing:-2px;line-height:1.3;margin:6px 0}.next-time small{font-size:20px;letter-spacing:0;margin-left:8px;font-weight:400;color:var(--muted)}.next-label{font-size:14px;line-height:1.7}.next-label span{color:var(--muted)}.next-empty{font-size:26px;letter-spacing:-.6px;margin:18px 0 8px;max-width:300px}.next-orbit{display:flex;flex-direction:column;align-items:center;gap:14px;min-width:100px}.next-orbit svg{width:60px;height:60px;color:var(--accent);stroke-width:.8;opacity:.8}.next-orbit span{border-radius:20px;background:var(--accent-bg);color:var(--accent);padding:8px 13px;font-size:12px;white-space:nowrap}.list-heading{display:flex;align-items:center;justify-content:space-between;margin:32px 2px 14px;gap:12px}.list-heading h2{font-size:15px;font-weight:550}.list-heading h2 span{display:inline-flex;margin-left:6px;font-size:11px;background:var(--surface2);padding:3px 7px;border-radius:6px;color:var(--muted)}.list-heading>span{font-size:11px;color:var(--muted)}.alarm-list{border:1px solid var(--line);border-radius:20px;background:var(--surface);overflow:hidden}.alarm{padding:23px 27px;border-bottom:1px solid var(--line)}.alarm:last-child{border:0}.alarm-line{display:flex;align-items:center;gap:20px;justify-content:space-between}.alarm-edit{text-align:left;background:none;min-width:0;padding:0}.alarm-time{display:block;font-size:50px;letter-spacing:-1.5px;font-weight:300;line-height:1.2}.alarm-time small{font-size:17px;color:var(--muted);margin-left:7px;letter-spacing:0}.alarm-label{display:block;font-size:13px;margin-top:7px;overflow-wrap:anywhere}.alarm-label>span{color:var(--muted)}.off .alarm-time,.off .alarm-label{color:var(--muted)}.alarm-bottom{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:17px}.tags{display:flex;gap:5px;flex-wrap:wrap}.tags>span{font-size:10px;background:var(--surface2);color:var(--muted);border-radius:5px;padding:4px 7px}.tags>.status{color:var(--accent);background:var(--accent-bg);font-size:12px}.row-actions{display:flex;gap:12px;flex-shrink:0}.row-actions button{background:transparent;color:var(--muted);padding:7px 0;font-size:12px}.row-actions .accent,.accent{color:var(--accent)!important}.active{background:linear-gradient(110deg,#ffb85c09,transparent);box-shadow:inset 3px 0 var(--accent)}.switch{appearance:none;flex:0 0 47px;width:47px;height:28px;background:#5a5b60;border-radius:99px;position:relative;margin:0;border:0;transition:background .15s;cursor:pointer}.switch:before{content:"";position:absolute;left:3px;top:3px;background:#fff;width:22px;height:22px;border-radius:50%;box-shadow:0 1px 3px #0004;transition:transform .15s}.switch:checked{background:#35b875}.switch:checked:before{transform:translateX(19px)}.empty-state{text-align:center;padding:45px 20px}.empty-state>svg{width:42px;height:42px;color:var(--muted);margin-bottom:18px}.empty-state h3{font-size:22px;font-weight:500}.empty-state p{font-size:13px;line-height:1.8;color:var(--muted);margin:12px 0 22px}footer{text-align:center;font-size:11px;color:var(--muted);margin:24px 0 0}footer span{padding:0 7px}.text-button{background:none;padding:8px 0;font-size:14px}.error{border:1px solid #e6777744;color:var(--danger);background:#d74e4e12;border-radius:10px;padding:12px;font-size:13px;line-height:1.6;margin:12px 0}.notice{font-size:12px;color:var(--accent);line-height:1.6;margin-top:10px}.alarm-errors{margin-top:12px;color:var(--danger);font-size:12px;line-height:1.6}.alarm-errors ul{padding-left:18px;overflow-wrap:anywhere}.hint{display:block;color:var(--muted);font-size:12px;line-height:1.6;margin-top:5px}.hidden{display:none!important}.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}dialog{padding:0;border:1px solid var(--line);border-radius:23px;background:var(--bg);color:var(--text);width:min(540px,calc(100vw - 32px));max-height:90dvh;box-shadow:0 20px 100px #0008;overflow:auto}dialog::backdrop{background:#0009;backdrop-filter:blur(5px)}.modal-head{display:flex;align-items:center;justify-content:space-between;padding:16px 22px;position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);z-index:3}.modal-head h2{font-size:16px;font-weight:550}.editor-body{padding:0 18px 22px}.time-picker{display:flex;justify-content:center;padding:26px 0}.time-picker input{font-size:46px;font-weight:300;background:none;border:0;padding:10px;color:var(--text);max-width:100%;font-variant-numeric:tabular-nums}.section{border:1px solid var(--line);background:var(--surface);border-radius:14px;margin-bottom:12px;overflow:hidden}.setting{padding:15px;display:flex;align-items:center;justify-content:space-between;gap:16px;cursor:pointer}.setting+.setting,.field+.setting{border-top:1px solid var(--line)}.setting-name{font-size:14px}.setting .hint{font-size:11px;max-width:330px}.field{display:flex;justify-content:space-between;align-items:center;gap:18px;padding:13px 15px;font-size:13px}.field>span{flex-shrink:0}.field input:not([type=range]),.field select{width:60%;max-width:260px;min-width:0;background:var(--surface2);border:1px solid var(--line);border-radius:7px;color:var(--text);padding:9px;font-size:13px}.field input[type=number]{max-width:90px}.field input[type=range]{width:60%;accent-color:var(--accent)}.field output{color:var(--muted);font-size:11px;margin-left:4px}.field.stacked{display:block}.field.stacked input{width:100%;max-width:none;margin-top:9px}.subsection{padding:0 13px 13px;margin:0;border:0;min-width:0}.subsection .field{padding:10px 0}.subsection .setting{padding:13px 0}.subsection h3{font-size:12px;font-weight:550;margin:15px 0 7px}.subsection details{margin-top:12px}.subsection summary{font-size:12px;cursor:pointer;color:var(--accent);padding:6px 0}.days{display:flex;justify-content:space-between;gap:6px;margin-top:3px}.day{position:relative;flex:1;cursor:pointer;text-align:center}.day input{position:absolute;opacity:0;width:100%;height:100%;margin:0}.day span{display:block;border:1px solid var(--line);border-radius:10px;padding:11px 0;font-size:12px;background:var(--surface2)}.day input:checked+span{background:var(--accent-bg);border-color:var(--accent);color:var(--accent)}.day input:focus-visible+span{outline:2px solid var(--accent);outline-offset:2px}.choices{max-height:205px;overflow:auto;border:1px solid var(--line);border-radius:9px;background:var(--bg)}.choice{display:flex;align-items:center;gap:9px;padding:10px;font-size:12px;border-bottom:1px solid var(--line);cursor:pointer}.choice:last-child{border:0}.choice input{accent-color:var(--accent);width:16px;height:16px;flex-shrink:0}.choice small{display:block;font-size:10px;line-height:1.5;color:var(--muted);overflow-wrap:anywhere}.choice>span{min-width:0}.empty-choice{padding:5px 0}.technical{padding:12px;font-size:11px;color:var(--muted)}.technical code{display:block;overflow-wrap:anywhere;margin-top:9px;user-select:all}.delete-button{background:var(--surface);border:1px solid var(--line);width:100%;padding:14px;color:var(--danger);border-radius:12px;margin-top:12px;font-size:13px}.editor-foot{text-align:center;font-size:10px;color:var(--muted);margin-top:17px}#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--text);color:var(--bg);padding:12px 18px;border-radius:12px;font-size:13px;z-index:20;max-width:90%;box-shadow:0 6px 30px #0004}#toast:empty{display:none}.loading{padding:80px 30px;text-align:center;color:var(--muted)}
  @media(max-width:600px){.topbar{height:58px;padding:0 17px}.menu{display:inline-block}.brand{font-size:10px;letter-spacing:2px;gap:10px}main{padding:28px 17px}.title-row{margin-bottom:22px}h1{font-size:36px}.eyebrow{font-size:9px;letter-spacing:1.5px}.primary{padding:10px 12px;font-size:12px;border-radius:11px}.next-card{padding:23px 20px;border-radius:17px}.next-time{font-size:48px}.next-time small{font-size:16px}.next-label{font-size:12px}.next-label span{display:block}.next-orbit{min-width:72px}.next-orbit svg{width:45px;height:45px}.next-orbit span{font-size:10px;padding:7px 9px}.next-empty{font-size:23px}.list-heading{margin-top:27px}.list-heading>span{font-size:10px;max-width:45%;text-align:right}.alarm{padding:20px}.alarm-time{font-size:44px}.alarm-label{font-size:12px}.alarm-bottom{align-items:flex-start}.row-actions{gap:12px}.tags>span{font-size:9px}.switch{transform:scale(.95);transform-origin:right center}dialog{max-height:95dvh;border-radius:20px 20px 0 0;width:100%;max-width:100%;margin:auto 0 0;border-bottom:0}.editor-body{padding-bottom:max(24px,env(safe-area-inset-bottom))}.modal-head{padding:15px 20px}.days{gap:5px}.time-picker input{font-size:42px}footer{font-size:10px}.empty-state p br{display:none}}
  @media(prefers-reduced-motion:reduce){*{transition:none!important}}
`;

export class DaybreakAlarmPanel extends (globalThis.HTMLElement || class {}) {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._data = null; this._draft = null; this._editing = null; this._connected = true;
    this._epoch = 0; this._busy = false; this._use24 = false; this._generation = 0;
    this.shadowRoot.innerHTML = `<style>${STYLES}</style><div class="app"><div id="page"><p class="loading">Loading your alarms…</p></div></div><div id="modal-root"></div><div id="toast" role="status" aria-live="polite"></div>`;
    this.shadowRoot.addEventListener("click",event=>this._click(event));
    this.shadowRoot.addEventListener("change",event=>this._change(event));
    this.shadowRoot.addEventListener("input",event=>this._input(event));
    this.shadowRoot.addEventListener("submit",event=>{event.preventDefault();this._save();});
  }
  set hass(value) {
    const connectionChanged = this._hass?.connection !== value.connection;
    this._hass = value;
    this.setAttribute("data-theme",value.themes?.darkMode === false ? "light" : "dark");
    if (connectionChanged && this.isConnected) this._subscribe();
  }
  set narrow(value) { this._narrow = value; }
  set panel(value) { this._panel = value; }
  connectedCallback() {
    try { this._use24 = localStorage.getItem("daybreak:24h") === "true"; } catch {}
    if (this._hass) this._subscribe();
    this._poll = setInterval(()=>this._load(),15000);
  }
  disconnectedCallback() {
    this._generation++;
    this._unsub?.(); this._unsub = null;
    clearInterval(this._poll);clearTimeout(this._toastTimer);
  }
  async _subscribe() {
    const generation = ++this._generation;
    this._unsub?.();this._unsub=null;
    this._load();
    try {
      const unsub = await this._hass.connection.subscribeEvents(()=>this._load(),"daybreak_alarm_changed");
      if (generation !== this._generation || !this.isConnected) unsub();
      else this._unsub = unsub;
    } catch { /* Polling also covers reconnects. */ }
  }
  async _load() {
    if (!this._hass || !this.isConnected) return;
    if(this._loading || this._busy){this._reloadPending=true;return;}
    const epoch = this._epoch;
    const generation = this._generation;
    this._loading = true;
    try {
      const data = await this._hass.callWS({type:"daybreak_alarm/get"});
      if (epoch !== this._epoch || generation !== this._generation || !this.isConnected) return;
      this._data=data;this._connected=true;this._renderList();
    } catch (err) {
      if (epoch !== this._epoch || generation !== this._generation || !this.isConnected) return;
      this._connected=false;
      if (this._data) this._renderList();
      else this.shadowRoot.querySelector("#page").innerHTML=`<div class="loading"><p>${e(err.message || "Could not load alarms. Check that Daybreak Alarms is configured and you are an administrator.")}</p><button class="text-button accent" data-action="retry">Retry</button></div>`;
    } finally { this._loading=false;this._flushLoad(); }
  }
  _flushLoad(){if(this._reloadPending && !this._busy){this._reloadPending=false;this._load();}}
  _renderList() {
    if (this._data) this.shadowRoot.querySelector("#page").innerHTML=listTemplate(this._data,this._use24,this._connected);
    this._renderEditorStatus();
  }
  _renderEditorStatus() {
    const area=this.shadowRoot.querySelector("#test-status");
    const record=this._data?.alarms.find(a=>a.id===this._editing?.id);
    if(area && record) {
      const r=record.runtime;
      area.innerHTML=`${r.status!=="idle" ? `<p class="notice">${r.status==="ringing" ? "Ringing now" : "Snoozed"}</p><div class="row-actions">${r.status==="ringing" && record.config.snooze_enabled ? `<button type="button" data-action="snooze" data-id="${e(record.id)}">Snooze</button>` : ""}<button type="button" data-action="dismiss" data-id="${e(record.id)}">Dismiss</button></div>` : r.last_result ? '<p class="hint">Alarm is idle. You can test again.</p>' : ""}${r.errors?.length ? `<p class="error">${r.errors.map(e).join("<br>")}</p>` : ""}`;
    }
    const result=this.shadowRoot.querySelector("#notification-result");
    if(result) result.innerHTML=this._notificationResult || "";
  }
  _renderEditor(error="") {
    const root=this.shadowRoot.querySelector("#modal-root");
    const old=this.shadowRoot.querySelector("dialog");
    const scroll=old?.scrollTop || 0;
    const field=this.shadowRoot.activeElement?.dataset?.field;
    old?.close();
    root.innerHTML=editorTemplate(this._draft,this._data.catalog,this._editing,error);
    const dialog=root.querySelector("dialog");
    dialog.addEventListener("cancel",event=>{event.preventDefault();if(!this._busy)this._close();});
    dialog.showModal();dialog.scrollTop=scroll;
    this._renderEditorStatus();
    if (field) dialog.querySelector(`[data-field="${CSS.escape(field)}"]`)?.focus({preventScroll:true});
  }
  _open(record=null) {
    if (!this._data || !this._connected) return;
    this._returnFocus=this.shadowRoot.activeElement;
    this._notificationResult="";
    this._editing=record ? clone(record) : null;
    this._draft=clone(record ? record.config : this._data.catalog.defaults);
    this._renderEditor();
  }
  _close() {
    this.shadowRoot.querySelector("dialog")?.close();
    this.shadowRoot.querySelector("#modal-root").innerHTML="";
    this._draft=null;this._editing=null;
    if (this._returnFocus?.isConnected) this._returnFocus.focus();
    else this.shadowRoot.querySelector('[data-action="new"]')?.focus();
  }
  _input(event) {
    const input=event.target;
    if (!this._draft || !input.dataset.field || input.type==="checkbox") return;
    const value=["number","range"].includes(input.type) ? input.valueAsNumber : input.value;
    setDraftField(this._draft,input.dataset.field,value);
    if(input.type==="range") {
      const out=input.closest("label")?.querySelector("output");
      if(out)out.textContent=`${Math.round(value*100)}%`;
    }
  }
  _change(event) {
    const input=event.target;
    if (input.dataset.enable) { this._command(input.dataset.enable,input.checked ? "enable" : "disable");return; }
    if (!this._draft) return;
    if(input.dataset.field && input.type==="checkbox") {
      setDraftField(this._draft,input.dataset.field,input.checked);
      this._renderEditor();
    } else if(input.dataset.list) {
      const path=input.dataset.list;
      const values=[...this.shadowRoot.querySelectorAll(`[data-list="${CSS.escape(path)}"]:checked`)].map(el=>path==="days" ? Number(el.value) : el.value);
      setDraftField(this._draft,path,values);
    } else if(input.dataset.choice==="sound") {
      this._draft.sound.media_id=input.value==="custom" ? "" : input.value;
      this._draft.sound.media_type="music";
      this._renderEditor();
    }
  }
  async _click(event) {
    const button=event.target.closest("[data-action]");
    if(!button || button.disabled || this._busy)return;
    const {action,id}=button.dataset;
    if(action==="new")this._open();
    else if(action==="edit")this._open(this._data.alarms.find(a=>a.id===id));
    else if(action==="close")this._close();
    else if(action==="retry")this._load();
    else if(action==="menu")this.dispatchEvent(new CustomEvent("hass-toggle-menu",{bubbles:true,composed:true}));
    else if(action==="format") {
      this._use24=!this._use24;
      try{localStorage.setItem("daybreak:24h",String(this._use24));}catch{}
      this._renderList();
    } else if(action==="delete") {
      if(globalThis.confirm("Delete this alarm? This also stops it if it is ringing.")) {
        if(await this._mutate({type:"daybreak_alarm/delete",alarm_id:id}))this._close();
      }
    } else if(action==="test-editor") {
      if(globalThis.confirm("Save these settings and test all enabled outputs now? Lights and scripts will also run.")) {
        const saved=await this._save(true);
        if(saved)await this._command(saved.id,"test");
      }
    } else if(action==="test-notification") {
      await this._testNotification();
    } else if(action==="dashboard-setup") {
      this.shadowRoot.querySelector("#modal-root").innerHTML=dashboardSetupTemplate();
      const dialog=this.shadowRoot.querySelector("dialog");
      dialog.addEventListener("cancel",()=>this._close());dialog.showModal();
    } else this._command(id,action);
  }
  async _command(id,action,token=null) {
    if(!this._connected || this._busy) {this._renderList();return;}
    return await this._mutate({type:"daybreak_alarm/action",alarm_id:id,action,...(token ? {token} : {})});
  }
  async _mutate(message) {
    if(this._busy)return false;
    this._busy=true;this._epoch++;
    const save=this.shadowRoot.querySelector("#save-alarm");if(save)save.disabled=true;
    try {
      const result=await this._hass.callWS(message);
      this._data={...this._data,...result};this._connected=true;
      this._renderList();return result;
    } catch(err) {
      if(this._draft)this._renderEditor(err.message || "Could not save. Please try again.");
      else this._toast(err.message || "Could not update the alarm.");
      this._renderList();return false;
    } finally {this._busy=false;const save=this.shadowRoot.querySelector("#save-alarm");if(save)save.disabled=false;this._flushLoad();}
  }
  async _save(keepOpen=false) {
    if(!this._draft || this._busy)return;
    if(!this.shadowRoot.querySelector("form").reportValidity())return;
    if(this._draft.repeat_enabled && !this._draft.days.length) {this._renderEditor("Choose at least one repeat day.");return;}
    const message={type:"daybreak_alarm/save",config:clone(this._draft)};
    if(this._editing)Object.assign(message,{alarm_id:this._editing.id,revision:this._editing.revision});
    const result=await this._mutate(message);
    if(result) {
      const saved=result.alarms.find(a=>a.id===result.saved_alarm_id);
      if(keepOpen && saved){this._editing=clone(saved);this._draft=clone(saved.config);this._renderEditor();}
      else {this._close();this._toast("Alarm saved");}
      return saved;
    }
  }
  async _testNotification() {
    if(!this._draft?.notify.enabled || !this._draft.notify.targets.length || this._busy)return;
    this._busy=true;this._epoch++;
    this._notificationResult='<p class="hint">Submitting phone test…</p>';this._renderEditorStatus();
    try {
      const result=await this._hass.callWS({type:"daybreak_alarm/test_notification",notify:clone(this._draft.notify)});
      this._notificationResult=result.results.map(r=>`<p class="${r.accepted ? "notice" : "error"}">${e(r.target)}: ${r.accepted ? "accepted by Home Assistant" : e(r.error)}</p>`).join("")+'<p class="hint">Acceptance does not confirm delivery. Check your phone for “Daybreak · notification test”.</p>';
    }catch(err){this._notificationResult=`<p class="error">${e(err.message || "Phone test failed")}</p>`;}
    finally{this._busy=false;this._renderEditorStatus();this._flushLoad();}
  }
  _toast(message) {
    clearTimeout(this._toastTimer);
    this.shadowRoot.querySelector("#toast").textContent=message;
    this._toastTimer=setTimeout(()=>{this.shadowRoot.querySelector("#toast").textContent="";},5000);
  }
}
if(globalThis.customElements && !customElements.get("daybreak-alarm-panel"))customElements.define("daybreak-alarm-panel",DaybreakAlarmPanel);

export function dashboardSetupTemplate() {
  return `<dialog aria-labelledby="setup-title"><div class="modal-head"><h2 id="setup-title">Add a dashboard card</h2><button type="button" class="text-button accent" data-action="close">Done</button></div><div class="setup-body"><p>1. Enable Advanced mode in your Home Assistant profile, then open Settings → Dashboards → menu → Resources. Add this URL as a <strong>JavaScript module</strong>:</p><code>/daybreak_alarm/static/card.js?v=${FRONTEND_VERSION}</code><p>2. Reload your browser. Edit a dashboard → Add card → search for <strong>Daybreak Alarms</strong>. Or use a Manual card:</p><pre>type: custom:daybreak-alarm-card\nshow_popup: true</pre><p>Create and edit alarms, snooze, and dismiss directly on the card. Turn off “Ringing popup” in the card editor if desired. Popups work while this dashboard is open and visible. Your backend alarms run with the dashboard closed.</p><p>The card uses the same administrator access as the Alarms page. HACS installs its files with this integration.</p></div></dialog>`;
}

export function cardConfig(config={}) {
  const value={title:"Alarms",show_popup:true,show_add:true,show_edit:true,use_24h:false,alarm_ids:[],...config};
  if(typeof value.title!=="string" || value.title.length>80)throw new Error("Card title must be at most 80 characters.");
  for(const key of ["show_popup","show_add","show_edit","use_24h"])
    if(typeof value[key]!=="boolean")throw new Error(`${key} must be true or false.`);
  if(!Array.isArray(value.alarm_ids) || value.alarm_ids.some(id=>typeof id!=="string" || !/^[a-zA-Z0-9_-]{1,200}$/.test(id)))throw new Error("alarm_ids must be a list of alarm IDs.");
  value.alarm_ids=[...new Set(value.alarm_ids)];
  return value;
}

export function cardAlarms(data,config) {
  return data.alarms.filter(a=>!config.alarm_ids.length || config.alarm_ids.includes(a.id))
    .sort((a,b)=>Number(b.runtime.status!=="idle")-Number(a.runtime.status!=="idle") || a.config.time.localeCompare(b.config.time));
}

export function cardTemplate(data,config,connected=true) {
  const alarms=cardAlarms(data,config);
  const next=nextAlarm(alarms);
  return `<ha-card><div class="db-card"><div class="db-head"><h2>${ICON} ${e(config.title)}</h2>${config.show_add ? `<button class="secondary" data-action="new"${disabled(!connected)}>Add alarm</button>` : ""}</div>
    <p class="hint">${next ? `Next: ${e(next.config.label)} · ${e(dateLabel(next.due,data.timezone))}` : "No upcoming alarms"}</p>
    ${!connected ? '<p class="error" role="alert">Disconnected. Controls are unavailable until Home Assistant reconnects.</p>' : ""}
    <div class="db-alarms">${alarms.map(a=>{
      const c=a.config,r=a.runtime,t=clockParts(c.time,config.use_24h);
      return `<article class="db-row ${r.status!=="idle" ? "active" : ""}"><div class="db-row-head"><div class="db-label"><span class="db-time">${t.time}<small>${t.period}</small></span><span>${e(c.label)}</span><small class="hint">${e(repeatLabel(c))}</small></div><input class="switch" type="checkbox" role="switch" data-enable="${e(a.id)}" aria-label="Enable ${e(c.label)}"${checked(c.enabled)}${disabled(!connected)}></div>
        <div class="row-actions">${config.show_edit ? `<button data-action="edit" data-id="${e(a.id)}" aria-label="Settings for ${e(c.label)}"${disabled(!connected)}>Edit</button>` : ""}
        ${r.status==="ringing" && c.snooze_enabled ? `<button data-action="snooze" data-id="${e(a.id)}"${disabled(!connected)}>Snooze ${c.snooze_minutes} min</button>` : ""}
        ${r.status!=="idle" ? `<button class="accent" data-action="dismiss" data-id="${e(a.id)}"${disabled(!connected)}>Dismiss</button>` : c.enabled && c.skip_enabled && r.next_at ? `<button data-action="skip" data-id="${e(a.id)}"${disabled(!connected)}>Skip next</button>` : ""}</div>
        ${r.status!=="idle" ? `<p class="notice">${r.status==="ringing" ? "Ringing now" : `Snoozed until ${e(dateLabel(r.snooze_until,data.timezone))}`}</p>` : ""}
        ${r.errors?.length ? `<details class="alarm-errors"><summary>Output issues</summary><p>${r.errors.map(e).join("<br>")}</p></details>` : ""}</article>`;
    }).join("") || '<p class="hint">No alarms match this card. Add an alarm or clear the card’s alarm ID filter.</p>'}</div><a class="db-link" href="/daybreak-alarms">Open Alarms & setup →</a></div></ha-card>`;
}

export function popupTemplate(alarm,use24=false,connected=true) {
  const t=clockParts(alarm.config.time,use24);
  return `<dialog class="ring-popup" aria-labelledby="ring-title"><div class="popup-body"><p class="eyebrow">${alarm.runtime.test_run ? "TEST ALARM" : "ALARM RINGING"}</p><h2 id="ring-title">${e(alarm.config.label)}</h2><div class="db-time">${t.time}<small>${t.period}</small></div><p class="popup-errors error hidden"></p><div class="popup-actions">${alarm.config.snooze_enabled ? `<button class="secondary" data-popup-action="snooze"${disabled(!connected)}>Snooze ${alarm.config.snooze_minutes} min</button>` : ""}<button class="primary" data-popup-action="dismiss"${disabled(!connected)}>Dismiss</button></div><button class="text-button" data-popup-action="hide">Hide popup · keep ringing</button></div></dialog>`;
}

// One popup per ring in this browser, even with multiple cards on the view.
const popupOwners=new Map();
const hiddenPopups=new Set();
const CARD_STYLES=`
  :host{height:auto;background:transparent;--bg:var(--ha-card-background,var(--card-background-color,#1b1c20));--text:var(--primary-text-color,#f6f4ef);--muted:var(--secondary-text-color,#a4a4ad);--line:var(--divider-color,#303137)}
  .app{overflow:visible;height:auto;padding:0}ha-card{display:block;color:var(--text)}.db-card{padding:20px}.db-head,.db-row-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.db-head h2{display:flex;align-items:center;gap:9px;font-size:20px;overflow-wrap:anywhere}.db-head svg{color:var(--accent);flex-shrink:0}.db-head .secondary{white-space:nowrap;font-size:12px;margin:0}.db-alarms{margin-top:14px}.db-row{padding:17px 5px;border-top:1px solid var(--line)}.db-row.active{padding-left:13px}.db-label{min-width:0;overflow-wrap:anywhere}.db-label>span{display:block}.db-time{font-size:36px;font-weight:300;letter-spacing:-1px}.db-time small{font-size:14px;margin-left:6px;letter-spacing:0;color:var(--muted)}.db-row .row-actions{justify-content:flex-end;margin-top:8px}.db-link{display:block;margin-top:12px;font-size:12px;color:var(--accent)}.popup-body{padding:30px;text-align:center}.popup-body h2{font-size:26px;margin:16px 0;overflow-wrap:anywhere}.popup-body .db-time{font-size:54px}.popup-actions{display:flex;justify-content:center;gap:12px;align-items:center;margin:18px 0}.ring-popup{width:min(420px,calc(100vw - 24px));border-radius:24px;margin:auto;max-height:90dvh}.ring-popup .text-button{font-size:12px;color:var(--muted)}
`;

export class DaybreakAlarmCard extends DaybreakAlarmPanel {
  constructor() {
    super();
    this._cardConfig=cardConfig();
    this.shadowRoot.querySelector("style").textContent+=CARD_STYLES;
    const root=document.createElement("div");root.id="popup-root";this.shadowRoot.append(root);
    this._visibility=()=>this._syncPopup();
  }
  setConfig(config) {this._cardConfig=cardConfig(config);this._renderList();}
  set preview(value) {this._preview=value;this._syncPopup();}
  getCardSize() {return 3+2*(this._data ? cardAlarms(this._data,this._cardConfig).length : 1);}
  getGridOptions() {return {columns:12,rows:"auto",min_columns:6};}
  static getStubConfig() {return {title:"Alarms",show_popup:true};}
  static getConfigElement() {return document.createElement("daybreak-alarm-card-editor");}
  connectedCallback() {super.connectedCallback();document.addEventListener("visibilitychange",this._visibility);}
  disconnectedCallback() {super.disconnectedCallback();document.removeEventListener("visibilitychange",this._visibility);this._releasePopup();}
  _renderList() {
    if(this._data && this._cardConfig)this.shadowRoot.querySelector("#page").innerHTML=cardTemplate(this._data,this._cardConfig,this._connected);
    this._renderEditorStatus();this._syncPopup();
  }
  _open(record=null) {this._releasePopup();super._open(record);}
  _close() {super._close();this._syncPopup();}
  _releasePopup() {
    if(popupOwners.get(this._popupKey)===this)popupOwners.delete(this._popupKey);
    this.shadowRoot.querySelector("#popup-root dialog")?.close();
    const root=this.shadowRoot.querySelector("#popup-root");if(root)root.innerHTML="";
    this._popupKey=null;this._popupAlarm=null;
  }
  _syncPopup() {
    if(!this._cardConfig || !this._data || !this.isConnected)return;
    const eligible=this._cardConfig.show_popup && !this._preview && !this._draft && document.visibilityState==="visible" && this.getClientRects().length;
    const ringing=eligible ? cardAlarms(this._data,this._cardConfig).filter(a=>a.runtime.status==="ringing" && a.runtime.token) : [];
    const alarm=ringing.find(a=>{const key=`${a.id}:${a.runtime.token}`;return !hiddenPopups.has(key) && (!popupOwners.has(key) || popupOwners.get(key)===this);});
    const key=alarm ? `${alarm.id}:${alarm.runtime.token}` : null;
    if(key!==this._popupKey)this._releasePopup();
    if(!alarm)return;
    if(!this._popupKey) {
      // Do not stack a second card's dialog over one already visible.
      if(popupOwners.size)return;
      this._popupKey=key;this._popupAlarm=alarm;popupOwners.set(key,this);
      const root=this.shadowRoot.querySelector("#popup-root");
      root.innerHTML=popupTemplate(alarm,this._cardConfig.use_24h,this._connected);
      const dialog=root.querySelector("dialog");
      dialog.addEventListener("cancel",event=>{event.preventDefault();this._hidePopup();});
      dialog.addEventListener("click",event=>this._popupClick(event));
      dialog.showModal();
    }
    const error=this.shadowRoot.querySelector(".popup-errors");
    const message=!this._connected ? "Disconnected. Reconnecting…" : (alarm.runtime.errors || []).join(" · ");
    if(error){error.textContent=message;error.classList.toggle("hidden",!message);}
    for(const button of this.shadowRoot.querySelectorAll('[data-popup-action]:not([data-popup-action="hide"])'))button.disabled=!this._connected || this._busy;
  }
  _hidePopup() {
    if(this._popupKey)hiddenPopups.add(this._popupKey);
    if(hiddenPopups.size>128)hiddenPopups.delete(hiddenPopups.values().next().value);
    this._releasePopup();this._syncPopup();
  }
  async _popupClick(event) {
    const button=event.target.closest("[data-popup-action]");
    if(!button || button.disabled || this._busy)return;
    if(button.dataset.popupAction==="hide"){this._hidePopup();return;}
    const a=this._popupAlarm;
    if(a)await this._command(a.id,button.dataset.popupAction,a.runtime.token);
    this._syncPopup();
  }
}

export class DaybreakAlarmCardEditor extends (globalThis.HTMLElement || class {}) {
  constructor(){super();this.attachShadow({mode:"open"});this.shadowRoot.addEventListener("change",event=>this._change(event));}
  setConfig(config){this._config=cardConfig(config);this._render();}
  set hass(value){this._hass=value;}
  _render(){
    if(!this._config)return;
    const c=this._config;
    this.shadowRoot.innerHTML=`<style>:host{display:block;color:var(--primary-text-color);font:14px system-ui}label{display:block;margin:16px 0}input[type=text],textarea{display:block;width:100%;box-sizing:border-box;padding:10px;margin:7px 0;border:1px solid var(--divider-color,#888);border-radius:8px;background:var(--card-background-color);color:inherit;font:inherit}input[type=checkbox]{margin-right:10px}small,p{color:var(--secondary-text-color);line-height:1.6}</style>
      <label>Title<input type="text" maxlength="80" data-key="title" value="${e(c.title)}"></label>
      ${[["show_popup","Ringing popup"],["show_add","Show Add alarm"],["show_edit","Show Edit buttons"],["use_24h","24-hour time"]].map(([key,label])=>`<label><input type="checkbox" data-key="${key}"${checked(c[key])}>${label}</label>`).join("")}
      <label>Alarm IDs (optional, one per line)<textarea rows="3" data-key="alarm_ids">${e(c.alarm_ids.join("\n"))}</textarea><small>Leave empty for all alarms. Copy an ID from the alarm’s settings → Automation ID. Popups follow this filter.</small></label><p>Popups appear only while this dashboard is visible. Previewing a card does not open a popup. All controls require a Home Assistant administrator.</p><p id="config-error" role="alert"></p>`;
  }
  _change(event){
    const input=event.target,key=input.dataset.key;if(!key)return;
    const value=input.type==="checkbox" ? input.checked : key==="alarm_ids" ? input.value.split(/[\s,]+/).filter(Boolean) : input.value;
    try{
      this._config=cardConfig({...this._config,[key]:value});
      this.shadowRoot.querySelector("#config-error").textContent="";
      this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:{...this._config,type:"custom:daybreak-alarm-card"}},bubbles:true,composed:true}));
    }catch(err){this.shadowRoot.querySelector("#config-error").textContent=err.message;}
  }
}
if(globalThis.customElements){
  if(!customElements.get("daybreak-alarm-card"))customElements.define("daybreak-alarm-card",DaybreakAlarmCard);
  if(!customElements.get("daybreak-alarm-card-editor"))customElements.define("daybreak-alarm-card-editor",DaybreakAlarmCardEditor);
  globalThis.customCards=globalThis.customCards || [];
  if(!globalThis.customCards.some(c=>c.type==="daybreak-alarm-card"))globalThis.customCards.push({type:"daybreak-alarm-card",name:"Daybreak Alarms",description:"Create alarms, snooze and dismiss, with an optional ringing popup.",preview:true});
}
