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
    R5: `sunny + ≥ ${ht ?? "?"} °C + Sonne > ${hs ?? "?"}° + late_morning bis afternoon`,
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
.topbar { display:flex; align-items:center; gap:10px; }
.menu { display:none; align-items:center; justify-content:center; flex:0 0 auto;
  width:38px; height:38px; padding:0; font-size:20px; line-height:1; border-radius:10px; }
@media (max-width: 870px) { .menu { display:inline-flex; } }
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
.cardhead { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px; }
.cardhead h2 { margin:0; }
.note { font-size:10px; color:#565f89; line-height:1.3; }
.thead, .trow { display:grid; grid-template-columns:14px 28px minmax(140px,1fr) 90px 90px 30px; gap:8px; align-items:center; }
.thead { padding:0 6px 6px; color:#565f89; font-size:10px; text-transform:uppercase; letter-spacing:.04em; }
.thead .ppcol { text-align:center; color:#7aa2f7; }
.ttable { font-size:13px; display:flex; flex-direction:column; gap:2px; }
.trow { padding:5px 6px; border-radius:8px; }
.trow.win { background:#243b2a; }
.trow .rid { color:#565f89; }
.trow .nmwrap { display:flex; flex-direction:column; gap:1px; min-width:0; }
.trow .nm { color:#c0caf5; display:flex; align-items:center; gap:6px; }
.trow .cond { font-size:10px; color:#565f89; line-height:1.25; }
.aktiv { font-size:9px; padding:1px 6px; border-radius:999px; background:#2d3a2e;
  border:1px solid #9ece6a55; color:#9ece6a; letter-spacing:.04em; }
.ppcell { display:flex; align-items:center; justify-content:center; gap:3px; border-radius:8px;
  padding:3px; border:1px solid transparent; }
.ppcell.cellact { background:rgba(98,179,120,.18); border-color:#62b378; }
.ppcell input[type=number] { width:46px; background:#24283b; color:#c0caf5; border:1px solid #2a2e42;
  border-radius:6px; padding:4px 6px; font-size:12px; text-align:right; }
.ppcell input[type=number]:focus { outline:none; border-color:#7aa2f7; }
.ppcell .pct { font-size:10px; color:#565f89; }
.rowedit { padding:3px 7px; font-size:13px; line-height:1; }
.resetbox { display:flex; align-items:center; justify-content:space-between; gap:10px;
  margin-top:12px; border-top:1px solid #2a2e42; padding-top:10px; }
.resetbox .note { flex:1; }
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
    } catch (e) {
      this.shadowRoot.getElementById("root").innerHTML =
        `<div class="err">Blind Policy nicht geladen oder keine Berechtigung.<br>${e.message || e}</div>`;
      return;
    }
    try {
      this._render();
    } catch (e) {
      this.shadowRoot.getElementById("root").innerHTML =
        `<div class="err">Render-Fehler im Panel.<br>${e.message || e}</div>`;
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
    const inv = !!s.invert_position;
    const pp = s.position_profile || {};
    const ppi = s.position_profile_inverted || {};
    const winRule = (s.trace || []).find((e) => e.matched);
    const cond = ruleConditions(s.thresholds);
    const trace = (s.trace || []).map((e) => {
      const m = RULE_LABEL[e.rule] || e.mode;
      const isWin = winRule && e.rule === winRule.rule;
      const nv = pp[m], iv = ppi[m];
      const nAct = (!inv && isWin) ? "cellact" : "";
      const iAct = (inv && isWin) ? "cellact" : "";
      return `<div class="trow ${isWin ? "win" : ""}">
        <span class="dot ${isWin ? "win" : e.matched ? "true" : ""}"></span>
        <span class="rid">${e.rule}</span>
        <div class="nmwrap"><span class="nm">${m}${isWin ? ` <span class="aktiv">AKTIV</span>` : ""}</span><span class="cond">${cond[e.rule] || ""}</span></div>
        <span class="ppcell ${nAct}"><input type="number" min="0" max="100" step="5" id="n_${m}" value="${nv ?? ""}"><span class="pct">%</span></span>
        <span class="ppcell ${iAct}"><input type="number" min="0" max="100" step="5" id="i_${m}" value="${iv ?? ""}"><span class="pct">%</span></span>
        <button class="rowedit" id="e_${m}" title="Zeile speichern">✎</button>
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


    const root = this.shadowRoot.getElementById("root");
    root.className = "";
    root.innerHTML = `
      <div class="topbar">
        <button class="menu" id="menu" title="Menü / Sidebar">☰</button>
        <h1>Blind Policy · ${s.profile || ""}</h1>
      </div>
      <div class="subrow">
        <div class="sub">Wohnzimmer-Rollo — ${s.apply_enabled ? "Automatik aktiv" : "Shadow (Automatik aus)"}</div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="badge ${inv ? "on" : "neutral"}" title="Achsen-Invertierung — bei umgekehrter Fahrtrichtung des Rollos">↕ Achse: ${inv ? "invertiert" : "normal"}</span>
          <button class="tiny ${s.apply_enabled ? "on" : "off"}" id="toggle">Automatik: ${s.apply_enabled ? "an" : "aus"}</button>
        </div>
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
        ${this._badge("Achse invertiert", s.invert_position)}
        <span class="badge neutral">Bio: ${c.bio_state || "—"}</span>
      </div>

      <div class="grid" style="grid-template-columns: 1fr 1fr;">
        <div class="card">
          <div class="cardhead">
            <h2>Decision Trace (Prioritätskette)</h2>
            <span class="note">ⓘ Inversion betrifft nur Zielpositionen.</span>
          </div>
          <div class="thead">
            <span></span><span>Prio</span><span>Regel / ID · Bedingung</span>
            <span class="ppcol">Normal</span><span class="ppcol">Invertiert</span><span></span>
          </div>
          <div class="ttable">${trace}</div>
        </div>
        <div class="card">
          <h2>Input-States</h2>
          ${inputs}
        </div>
      </div>

      <div class="grid" style="grid-template-columns: 1fr 1fr; margin-top:14px;">
        <div class="card">
          <div class="cardhead">
            <h2>Debug-Sensor</h2>
            <button class="tiny" id="dbgcopy" title="JSON in die Zwischenablage">⧉ Kopieren</button>
          </div>
          <pre>${debug}</pre>
        </div>
        <div class="card">
          <h2>Aktionen</h2>
          <div class="actions">
            <button class="go" id="apply" ${s.apply_enabled ? "" : "disabled"} title="${s.apply_enabled ? "" : "Automatik ist aus — fährt nicht"}">Jetzt anwenden</button>
            <button id="bed">Privacy-Bett ${s.privacy_bed ? "aus" : "an"}</button>
            <button class="warn" id="clr" ${s.manual_override ? "" : "disabled"} title="${s.manual_override ? "" : "Kein Override aktiv"}">Override löschen</button>
            <button id="inv" class="${s.invert_position ? "on" : ""}" title="Spiegelt jede Zielposition (0↔100) — bei umgekehrter Fahrtrichtung des Rollos">Achse invertieren: ${s.invert_position ? "an" : "aus"}</button>
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
              <select id="mmode">${(s.manual_modes || []).map((m) => `<option value="${m}" ${s.manual_mode === m ? "selected" : ""}>${MODE_LABEL[m] || m} · ${(inv ? ppi : pp)[m] ?? "—"}%</option>`).join("")}</select>
              <button class="tiny" id="mset">Setzen</button>
            </div>
          </div>
          <div class="mut">${s.manual_explicit
            ? `Manuell aktiv: ${s.manual_mode ? (MODE_LABEL[s.manual_mode] || s.manual_mode) : (s.manual_target + "%")} — „Override löschen" gibt an die Automatik zurück.`
            : (s.apply_enabled ? "Automatik steuert das Rollo." : "Shadow: Automatik aus — nur der Manuell-Slider/Modus fährt.")}</div>
          <div class="mut">Blocker: ${(s.blockers || []).join(", ") || "keine"} · Apply erlaubt: ${s.apply_allowed}</div>
          <div class="mut">Cover: ${s.cover?.entity_id || "—"} @ ${s.cover?.current_position ?? "—"}%</div>
          <div class="resetbox">
            <span class="note">ⓘ Die Inversion wirkt nur auf Zielpositionen. Alle Bedingungen und Prioritäten bleiben unverändert.</span>
            <button id="ppreset" title="Beide Profile (Normal + Invertiert) auf Default zurücksetzen">↺ Zurücksetzen</button>
          </div>
        </div>
      </div>`;

    const $ = (id) => this.shadowRoot.getElementById(id);
    $("menu").onclick = () =>
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    $("toggle").onclick = () => this._call("benni_blind_policy/set_apply_enabled", { enabled: !s.apply_enabled });
    $("apply").onclick = () => this._call("benni_blind_policy/apply_now");
    $("bed").onclick = () => this._call("benni_blind_policy/set_privacy_bed", { enabled: !s.privacy_bed });
    $("clr").onclick = () => this._call("benni_blind_policy/clear_manual_override");
    $("inv").onclick = () => this._call("benni_blind_policy/set_invert_position", { enabled: !s.invert_position });
    const mpos = $("mpos"), mval = $("mval");
    mpos.oninput = () => { mval.textContent = mpos.value + "%"; };
    $("mgo").onclick = () => this._call("benni_blind_policy/set_manual_position", { position: Number(mpos.value) });
    $("mset").onclick = () => this._call("benni_blind_policy/set_manual_decision", { mode: $("mmode").value });

    // Pro-Zeile: Stift speichert Normal + Invertiert dieses Modus unabhängig.
    const clamp = (v) => Math.max(0, Math.min(100, Number(v)));
    (s.trace || []).forEach((e) => {
      const m = RULE_LABEL[e.rule] || e.mode;
      const btn = $("e_" + m);
      if (!btn) return;
      btn.onclick = () => {
        const nEl = $("n_" + m), iEl = $("i_" + m);
        const np = {}, ip = {};
        if (nEl && nEl.value !== "") np[m] = clamp(nEl.value);
        if (iEl && iEl.value !== "") ip[m] = clamp(iEl.value);
        this._call("benni_blind_policy/set_position_profile",
          { position_profile: np, position_profile_inverted: ip });
      };
    });
    const reset = $("ppreset");
    if (reset) reset.onclick = () => this._call("benni_blind_policy/reset_position_profile");
    const copy = $("dbgcopy");
    if (copy) copy.onclick = () => { try { navigator.clipboard.writeText(debug); copy.textContent = "✓ Kopiert"; } catch (_) {} };
  }
}

customElements.define("bbp-app", BbpApp);
