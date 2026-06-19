/**
 * Benni Blind Policy — Diagnose/Trace-Panel (Vanilla Web Component, kein Build-Step).
 *
 * Holt den konsolidierten Status über die WS-API (benni_blind_policy/get_status)
 * und rendert Live-Diagnose, Decision-Trace (Prioritätskette), Input-States,
 * Debug-JSON + Aktionen. Layout nach Referenz-Screenshot (Dracula-ish Dark).
 */

const MODE_LABEL = {
  window_open: "Fenster offen",
  privacy_bed: "Privacy Bett",
  privacy: "Privacy",
  alarm_wakeup: "Wecker",
  open_weekday: "Offen (Werktag)",
  open_weekend: "Offen (Wochenende)",
  sleep: "Schlafen",
  heat: "Hitzeschutz",
  glare_tv: "Blendschutz TV",
  glare_pc: "Blendschutz PC",
  open: "Offen",
  manual: "Manuell",
};

const RULE_LABEL = {
  R1: "window_open", R2: "privacy_bed", R3: "privacy", R4: "alarm_wakeup",
  R5: "heat", R6: "open_weekday", R7: "open_weekend", R8: "sleep",
  R9: "glare_tv", R10: "glare_pc", R11: "open",
};

const PRESENCE_LABEL = { nicht_leer: "Anwesend", leer: "Niemand da" };
const presenceLabel = (v) => PRESENCE_LABEL[v] || v || "—";

const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const fmtK = (n) => (n % 1000 === 0 ? `${n / 1000}k` : `${(n / 1000).toFixed(1)}k`);

/** Kurz-Bedingung je Regel ("ab wann greift sie"), parametriert mit den Live-Schwellen. */
function ruleConditions(thr = {}) {
  const { gate_open_lux: go, gate_sun_min_deg: gs, heat_temp_c: ht, heat_sun_min_deg: hs,
    privacy_latch_lux: pl, open_weekday_min_minutes: wd, open_weekend_min_minutes: we } = thr;
  return {
    R1: "Fenster offen — absolut (Safety)",
    R2: "Privacy-Bett-Schalter an",
    R3: `Haushalt leer ODER Privacy-Latch (Latch abends < ${pl ?? "?"} lx)`,
    R4: "Wecker-Schalter an",
    R5: `sunny + ≥ ${ht ?? "?"} °C + Sonne > ${hs ?? "?"}° + late_morning bis early_evening`,
    R6: `late_morning + Werktag + ab ${wd != null ? hhmm(wd) : "?"}`,
    R7: `forenoon + Wochenende/frei + ab ${we != null ? hhmm(we) : "?"}`,
    R8: "Bio = sleep ODER Nachtphase",
    R9: `Lux-Gate an (> ${go != null ? fmtK(go) : "?"} lx) + TV/Streaming/Gaming + nicht PC`,
    R10: `Lux-Gate an (> ${go != null ? fmtK(go) : "?"} lx) + Gaming am PC`,
    R11: "Fallback — trifft immer zu",
  };
}

const css = `
:host { display:block; font-family: ui-sans-serif, system-ui, sans-serif;
  background:#1a1b26; color:#c0caf5; min-height:100vh; padding:18px 22px; box-sizing:border-box; }
h1 { font-size:18px; margin:0 0 2px; color:#bb9af7; }
.sub { color:#565f89; font-size:12px; margin-bottom:16px; }
.grid { display:grid; gap:14px; }
.cols { grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
.card { background:#1f2335; border:1px solid #2a2e42; border-radius:12px; padding:14px 16px; }
.card h2 { font-size:13px; margin:0 0 10px; color:#7aa2f7; text-transform:uppercase; letter-spacing:.04em; }
.kpi { font-size:24px; font-weight:600; color:#7dcfff; }
.kpi.mode { color:#bb9af7; }
.row { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; padding:4px 0; font-size:13px; border-bottom:1px solid #20243450; }
.row .k { color:#787c99; padding-top:1px; } .row .v { color:#c0caf5; }
.row .vwrap { display:flex; flex-direction:column; align-items:flex-end; gap:1px; }
.row .hint { font-size:10px; color:#565f89; text-align:right; line-height:1.2; }
.badges { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 18px; }
.badge { font-size:12px; padding:4px 10px; border-radius:999px; background:#24283b; border:1px solid #2a2e42; }
.badge.on { background:#2d3a2e; border-color:#9ece6a55; color:#9ece6a; }
.badge.off { background:#3a2d33; border-color:#f7768e55; color:#f7768e; }
.badge.neutral { color:#7dcfff; }
.trace { font-size:13px; }
.trace .t { display:flex; align-items:center; gap:10px; padding:5px 6px; border-radius:8px; }
.trace .t.win { background:#243b2a; }
.trace .t.skip { opacity:.45; }
.dot { width:9px; height:9px; border-radius:50%; background:#414868; flex:0 0 auto; }
.dot.true { background:#9ece6a; } .dot.win { background:#9ece6a; box-shadow:0 0 0 3px #9ece6a33; }
.trace .t { align-items:flex-start; }
.trace .rid { width:34px; color:#565f89; padding-top:1px; }
.trace .nmwrap { flex:1; display:flex; flex-direction:column; gap:1px; }
.trace .nm { color:#c0caf5; }
.trace .cond { font-size:10px; color:#565f89; line-height:1.25; }
.trace .res { font-size:12px; } .trace .res.true { color:#9ece6a; } .trace .res.false { color:#f7768e; }
.trace .pos { width:48px; text-align:right; color:#787c99; }
pre { background:#16161e; border-radius:10px; padding:12px; overflow:auto; font-size:12px; color:#a9b1d6; margin:0; }
.actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:6px; }
button { background:#24283b; color:#c0caf5; border:1px solid #2a2e42; border-radius:8px;
  padding:7px 12px; font-size:12px; cursor:pointer; }
button:hover { border-color:#7aa2f7; }
button.warn { color:#f7768e; } button.go { color:#9ece6a; }
button:disabled { opacity:.4; cursor:not-allowed; }
button:disabled:hover { border-color:#2a2e42; }
button.tiny { padding:3px 10px; font-size:11px; border-radius:999px; }
button.tiny.on { background:#2d3a2e; border-color:#9ece6a55; color:#9ece6a; }
button.tiny.off { background:#3a2d33; border-color:#f7768e55; color:#f7768e; }
.err { color:#f7768e; padding:20px; }
.mut { color:#565f89; font-size:11px; margin-top:6px; }
.subrow { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:16px; }
.subrow .sub { margin:0; }
.manual { margin-top:12px; border-top:1px solid #2a2e42; padding-top:10px; display:flex; flex-direction:column; gap:8px; }
.manual .line { display:flex; align-items:center; gap:8px; }
.manual label { font-size:11px; color:#787c99; min-width:58px; }
.manual input[type=range] { flex:1; accent-color:#7aa2f7; }
.manual select { background:#24283b; color:#c0caf5; border:1px solid #2a2e42; border-radius:8px; padding:6px 8px; font-size:12px; flex:1; }
.manual .val { width:44px; text-align:right; color:#7dcfff; font-size:12px; }
`;

class BbpApp extends HTMLElement {
  set hass(h) { this._hass = h; if (!this._timer) this._tick(); }

  connectedCallback() {
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${css}</style><div id="root" class="err">Lade…</div>`;
    this._timer = setInterval(() => this._tick(), 3000);
  }
  disconnectedCallback() { clearInterval(this._timer); this._timer = null; }

  async _tick() {
    if (!this._hass) return;
    try {
      this._status = await this._hass.callWS({ type: "benni_blind_policy/get_status" });
      this._render();
    } catch (e) {
      this.shadowRoot.getElementById("root").innerHTML =
        `<div class="err">Blind Policy nicht geladen oder keine Berechtigung.<br>${e.message || e}</div>`;
    }
  }

  async _call(type, extra = {}) {
    try { this._status = await this._hass.callWS({ type, ...extra }); this._render(); }
    catch (e) { /* require_admin etc. */ console.error(e); }
  }

  _badge(label, on) {
    return `<span class="badge ${on ? "on" : "off"}">${label}: ${on ? "an" : "aus"}</span>`;
  }

  _render() {
    const s = this._status; if (!s) return;
    const c = s.context || {};
    const pos = s.target_position;
    const winRule = (s.trace || []).find((e) => e.matched);
    const cond = ruleConditions(s.thresholds);
    const trace = (s.trace || []).map((e) => {
      const isWin = winRule && e.rule === winRule.rule;
      const afterWin = winRule && Number(e.rule.slice(1)) > Number(winRule.rule.slice(1));
      return `<div class="t ${isWin ? "win" : ""} ${afterWin ? "skip" : ""}">
        <span class="dot ${isWin ? "win" : e.matched ? "true" : ""}"></span>
        <span class="rid">${e.rule}</span>
        <div class="nmwrap"><span class="nm">${RULE_LABEL[e.rule] || e.mode}</span><span class="cond">${cond[e.rule] || ""}</span></div>
        <span class="res ${e.matched ? "true" : "false"}">${afterWin ? "skip" : e.matched}</span>
        <span class="pos">${e.position != null ? e.position + "%" : "—"}</span>
      </div>`;
    }).join("");

    const thr = s.thresholds || {};
    const inputs = [
      ["Außenhelligkeit", c.lux != null ? c.lux + " lx" : "—",
        thr.gate_open_lux ? `Lux-Gate: > ${fmtK(thr.gate_open_lux)} auf / < ${fmtK(thr.gate_close_lux)} zu` : ""],
      ["Day State", c.day_state || "—", ""],
      ["Day Context", c.day_context || "—", ""],
      ["Media Scenario", c.media_scenario || "—", "TV/Streaming/Gaming → Glare (mit Lux-Gate)"],
      ["Gaming Source", c.gaming_source || "—", "pc → glare_pc, sonst glare_tv"],
      ["Sonnenhöhe", c.sun_elevation != null ? c.sun_elevation + "°" : "—",
        thr.gate_sun_min_deg ? `> ${thr.gate_sun_min_deg}° für Gate & Heat` : ""],
      ["Wetterlage", c.weather_condition || "—", "sunny nötig für Heat"],
      ["Außentemperatur", c.outdoor_temp != null ? c.outdoor_temp + " °C" : "—",
        thr.heat_temp_c ? `Heat ab ≥ ${thr.heat_temp_c} °C` : ""],
      ["Bio-State", c.bio_state || "—", ""],
      ["Fenster offen", String(c.window_open), "true → R1 absolut"],
      ["Haushalt", presenceLabel(c.presence_household), "leer → privacy (R3)"],
    ].map(([label, v, hint]) =>
      `<div class="row"><span class="k">${label}</span><span class="vwrap"><span class="v">${v}</span>${hint ? `<span class="hint">${hint}</span>` : ""}</span></div>`
    ).join("");

    const debug = JSON.stringify({
      profile: s.profile, mode: s.mode, position: pos, reason: s.reason,
      gate_active: s.gate_on, apply_enabled: s.apply_enabled,
      apply_allowed: s.apply_allowed, blockers: s.blockers,
      writing_active: s.writing_active, cover: s.cover,
    }, null, 2);

    this.shadowRoot.getElementById("root").outerHTML = `<div id="root">
      <h1>Blind Policy · ${s.profile || ""}</h1>
      <div class="subrow">
        <div class="sub">Wohnzimmer-Rollo — ${s.apply_enabled ? "Automatik aktiv" : "Shadow (Automatik aus)"}</div>
        <button class="tiny ${s.apply_enabled ? "on" : "off"}" id="toggle">Automatik: ${s.apply_enabled ? "an" : "aus"}</button>
      </div>

      <div class="grid cols">
        <div class="card"><h2>Aktiver Modus</h2><div class="kpi mode">${MODE_LABEL[s.mode] || s.mode || "—"}</div></div>
        <div class="card"><h2>Zielposition</h2><div class="kpi">${pos != null ? pos + " %" : "—"}</div></div>
        <div class="card"><h2>Fensterstatus</h2><div class="kpi">${c.window_open ? "offen" : "geschlossen"}</div></div>
        <div class="card"><h2>Haushalt</h2><div class="kpi">${presenceLabel(c.presence_household)}</div></div>
      </div>

      <div class="badges">
        ${this._badge("Privacy-Latch", s.privacy_latch)}
        ${this._badge("Manual Override", s.manual_override)}
        ${this._badge("Lux-Gate", s.gate_on)}
        ${this._badge("Writing aktiv", s.writing_active)}
        ${this._badge("Apply aktiv", s.apply_enabled)}
        <span class="badge neutral">Bio: ${c.bio_state || "—"}</span>
      </div>

      <div class="grid" style="grid-template-columns: 1fr 1fr;">
        <div class="card">
          <h2>Decision Trace (Prioritätskette)</h2>
          <div class="trace">${trace}</div>
        </div>
        <div class="card">
          <h2>Input-States</h2>
          ${inputs}
        </div>
      </div>

      <div class="grid" style="grid-template-columns: 1fr 1fr; margin-top:14px;">
        <div class="card">
          <h2>Debug-Sensor</h2>
          <pre>${debug}</pre>
        </div>
        <div class="card">
          <h2>Aktionen</h2>
          <div class="actions">
            <button class="go" id="apply" ${s.apply_enabled ? "" : "disabled"} title="${s.apply_enabled ? "" : "Automatik ist aus — fährt nicht"}">Jetzt anwenden</button>
            <button id="bed">Privacy-Bett ${s.privacy_bed ? "aus" : "an"}</button>
            <button class="warn" id="clr" ${s.manual_override ? "" : "disabled"} title="${s.manual_override ? "" : "Kein Override aktiv"}">Override löschen</button>
          </div>
          <div class="manual">
            <div class="line">
              <label>Manuell</label>
              <input type="range" min="0" max="100" step="5" id="mpos" value="${s.manual_target ?? s.cover?.current_position ?? s.target_position ?? 100}">
              <span class="val" id="mval">${s.manual_target ?? s.cover?.current_position ?? s.target_position ?? 100}%</span>
              <button class="tiny" id="mgo">Fahren</button>
            </div>
            <div class="line">
              <label>Modus</label>
              <select id="mmode">${(s.manual_modes || []).map((m) => `<option value="${m}" ${s.manual_mode === m ? "selected" : ""}>${MODE_LABEL[m] || m} · ${(s.position_profile || {})[m] ?? "—"}%</option>`).join("")}</select>
              <button class="tiny" id="mset">Setzen</button>
            </div>
          </div>
          <div class="mut">${s.manual_explicit
            ? `Manuell aktiv: ${s.manual_mode ? (MODE_LABEL[s.manual_mode] || s.manual_mode) : (s.manual_target + "%")} — „Override löschen" gibt an die Automatik zurück.`
            : (s.apply_enabled ? "Automatik steuert das Rollo." : "Shadow: Automatik aus — nur der Manuell-Slider/Modus fährt.")}</div>
          <div class="mut">Blocker: ${(s.blockers || []).join(", ") || "keine"} · Apply erlaubt: ${s.apply_allowed}</div>
          <div class="mut">Cover: ${s.cover?.entity_id || "—"} @ ${s.cover?.current_position ?? "—"}%</div>
        </div>
      </div>
    </div>`;

    const $ = (id) => this.shadowRoot.getElementById(id);
    $("toggle").onclick = () => this._call("benni_blind_policy/set_apply_enabled", { enabled: !s.apply_enabled });
    $("apply").onclick = () => this._call("benni_blind_policy/apply_now");
    $("bed").onclick = () => this._call("benni_blind_policy/set_privacy_bed", { enabled: !s.privacy_bed });
    $("clr").onclick = () => this._call("benni_blind_policy/clear_manual_override");
    const mpos = $("mpos"), mval = $("mval");
    mpos.oninput = () => { mval.textContent = mpos.value + "%"; };
    $("mgo").onclick = () => this._call("benni_blind_policy/set_manual_position", { position: Number(mpos.value) });
    $("mset").onclick = () => this._call("benni_blind_policy/set_manual_decision", { mode: $("mmode").value });
  }
}

customElements.define("bbp-app", BbpApp);
