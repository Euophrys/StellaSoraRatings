"use strict";
// Build guide page. `state` is the team document (same schema as teams/*.yaml); every number shown comes
// from a server job (ssr.sim.simulate). Edits never recalculate on their own.

let catalog = null;                 // GET /api/catalog
let state = null;                   // the team doc
let results = null;                 // {grid, emblems, total, forState, stale, at}
const ui = { stem: null, teams: [], pinkRows: {}, open: {}, messages: [], job: null, optimizeNote: null };
const SECTIONS = [];                // [render(): Node] after the team + pinks sections (potentials, optimize, emblems)

// ---------------------------------------------------------------- tiny DOM helper
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function select(value, options, onchange, attrs) {
  // options: [{value, label, class?, disabled?}]
  const s = h("select", { ...attrs, onchange: (e) => onchange(e.target.value) },
    options.map((o) => h("option", { value: o.value, class: o.class, disabled: o.disabled }, o.label)));
  s.value = value ?? "";
  return s;
}

// ---------------------------------------------------------------- API
async function api(method, path, body) {
  const r = await fetch(path, { method, headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok) { const e = new Error(data.error || `HTTP ${r.status}`); e.status = r.status; throw e; }
  return data;
}

function message(kind, text) {
  ui.messages = ui.messages.filter((m) => m.text !== text);
  ui.messages.push({ kind, text });
  renderBanner();
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function runJob(kind, extra) {
  // POST a job, poll every 500 ms driving the progress bar, resolve with its result.
  let job;
  try {
    job = await api("POST", "/api/jobs", { kind, state, ...(extra || {}) });
  } catch (e) { message("err", e.message); throw e; }
  ui.job = { id: job.id, kind, phase: "", done: 0, total: 0, t0: Date.now() };
  renderJobBar();
  try {
    for (;;) {
      await sleep(500);
      const s = await api("GET", `/api/jobs/${job.id}`);
      Object.assign(ui.job, { phase: s.phase, done: s.done, total: s.total });
      renderJobBar();
      if (s.state === "done") return s.result;
      if (s.state === "cancelled") throw Object.assign(new Error("cancelled"), { cancelled: true });
      if (s.state === "error") { message("err", s.error); throw new Error(s.error); }
    }
  } finally {
    ui.job = null;
    renderJobBar();
    render();
  }
}

// ---------------------------------------------------------------- state
const calcKey = (s) => JSON.stringify({ ...s, name: undefined, budget: undefined, max_level: undefined });

function setState(mutator) {
  mutator(state);
  state.members.forEach((m, i) => { m.role = i === 0 ? "main" : "support"; });
  if (results) results.stale = calcKey(state) !== results.forState;
  render();
}

const trekker = (name) => catalog.trekkers.find((t) => t.name === name);
const roleOf = (i) => (i === 0 ? "main" : "support");
const discByDoc = (d) => {
  if (d === "filler" || !d || d.name === "filler") return null;
  return catalog.discs.find((x) => (d.prefix ? x.name.startsWith(d.name) : x.name === d.name)) || null;
};
const discDocs = (side) => (state.discs[side] || []).concat(["filler", "filler", "filler"]).slice(0, 3);

function blankMember(i) {
  return { trekker: "", role: roleOf(i), pinks: [], skill_levels: i === 0 ? { auto: 10, skill: 10, ult: 10 } : { skill: 10, ult: 10 },
    emblems: [], talents: 0, targets: {} };
}

function newDoc() {
  return { name: "new_team", fight_length: 120, tick: 0.05, mark_icd: 1.0, enemy: { res: 145, defense: 0, broken: 1.0 },
    members: [0, 1, 2].map(blankMember), discs: { main: ["filler", "filler", "filler"], support: ["filler", "filler", "filler"] },
    budget: [30, 15, 15], max_level: 6 };
}

function normalise(doc) {
  doc.members = (doc.members || []).concat([0, 1, 2].map(blankMember)).slice(0, 3);
  doc.members.forEach((m, i) => {
    m.role = roleOf(i);
    m.pinks = m.pinks || [];
    m.emblems = m.emblems || [];
    m.targets = m.targets || {};
    m.skill_levels = m.skill_levels || {};
  });
  doc.discs = doc.discs || {};
  doc.discs.main = discDocsOf(doc.discs.main);
  doc.discs.support = discDocsOf(doc.discs.support);
  doc.enemy = doc.enemy || { res: 145, defense: 0, broken: 1.0 };
  return doc;
}
const discDocsOf = (xs) => (xs || []).concat(["filler", "filler", "filler"]).slice(0, 3);

// ---------------------------------------------------------------- header
function renderHeader() {
  const top = document.getElementById("top");
  top.replaceChildren(h("div", { class: "inner" },
    h("span", { class: "title" }, "Stella Sora Build Guide"),
    select(ui.stem || "", [{ value: "", label: "— team file —" }].concat(ui.teams.map((t) => ({ value: t, label: t }))),
      (v) => { ui.pick = v; }, { id: "teamfile" }),
    h("button", { onclick: () => loadTeam(document.getElementById("teamfile").value) }, "Load"),
    h("button", { onclick: () => { if (confirmDiscard()) { state = newDoc(); ui.stem = null; results = null; ui.pinkRows = {}; render(); } } }, "New"),
    h("button", { onclick: () => saveTeam(ui.stem), disabled: !ui.stem }, "Save"),
    h("button", { onclick: () => saveAs() }, "Save as…"),
    h("span", { class: "stem" }, ui.stem ? `teams/${ui.stem}.yaml` : "unsaved"),
    h("span", { class: "sep" }),
    ...headerExtras.map((f) => f()),
  ));
}
const headerExtras = [];   // more header buttons (Export, share codes)

let savedKey = null;
const confirmDiscard = () => savedKey === JSON.stringify(state) || confirm("Discard unsaved changes?");

async function loadTeam(stem) {
  if (!stem) return;
  if (!confirmDiscard()) return;
  try {
    state = normalise(await api("GET", `/api/teams/${encodeURIComponent(stem)}`));
    ui.stem = stem; results = null; ui.pinkRows = {}; ui.optimizeNote = null;
    savedKey = JSON.stringify(state);
    render();
  } catch (e) { message("err", e.message); }
}

async function saveTeam(stem) {
  if (!stem) return saveAs();
  try {
    state.name = stem;
    await api("PUT", `/api/teams/${encodeURIComponent(stem)}`, { state });
    ui.stem = stem;
    savedKey = JSON.stringify(state);
    ui.teams = await api("GET", "/api/teams");
    message("info", `Saved teams/${stem}.yaml`);
    render();
  } catch (e) { message("err", e.message); }
}

function saveAs() {
  const stem = prompt("Save as (letters, digits, _ and -):", ui.stem || state.name || "my_team");
  if (!stem) return;
  if (ui.teams.includes(stem) && stem !== ui.stem && !confirm(`teams/${stem}.yaml exists. Overwrite?`)) return;
  saveTeam(stem.trim());
}

// ---------------------------------------------------------------- banners and job bar
function renderBanner() {
  const b = document.getElementById("banner");
  const kids = ui.messages.map((m, k) => h("div", { class: `msg ${m.kind}` }, m.text,
    h("button", { class: "x", onclick: () => { ui.messages.splice(k, 1); renderBanner(); } }, "×")));
  if (results && results.stale) {
    kids.unshift(h("div", { class: "msg warn" }, "Levels changed — numbers are from the previous build.",
      h("button", { class: "primary", onclick: recalc, disabled: !!ui.job }, "Recalculate")));
  }
  b.replaceChildren(...kids);
}

function renderJobBar() {
  const bar = document.getElementById("jobbar");
  if (!ui.job) { bar.hidden = true; bar.replaceChildren(); return; }
  const j = ui.job;
  const pct = j.total ? Math.round((100 * j.done) / j.total) : 0;
  const secs = Math.round((Date.now() - j.t0) / 1000);
  bar.hidden = false;
  bar.replaceChildren(
    h("span", {}, `${j.kind}: ${j.phase || "starting"} ${j.total ? `${j.done}/${j.total}` : ""} · ${secs}s`),
    h("div", { class: "bar" }, h("div", { style: `width:${pct}%` })),
    h("button", { onclick: () => api("POST", `/api/jobs/${j.id}/cancel`, {}).catch(() => {}) }, "Cancel"));
}

async function recalc() {
  const key = calcKey(state);
  try {
    const r = await runJob("recalc");
    results = { ...r, forState: key, stale: calcKey(state) !== key, at: new Date().toISOString() };
    render();
  } catch (e) { /* shown already */ }
}

// ---------------------------------------------------------------- team section
const SKILLS = { main: ["auto", "skill", "ult"], support: ["skill", "ult"] };
const SLOT_KINDS = { 1: ["stat"], 2: ["stat", "skill"], 3: ["stat", "potential"] };
const SLOT_NAMES = { 1: "Emblem 1 (Lv70)", 2: "Emblem 2 (Lv80)", 3: "Emblem 3 (Lv90)" };

function changeTrekker(i, name) {
  setState((s) => {
    const m = s.members[i];
    m.trekker = name; m.pinks = []; m.targets = {}; m.emblems = [];
  });
  results = null; ui.pinkRows = {}; ui.optimizeNote = null;
  render();
}

function slotLines(m, slot) {
  if (m.emblems.length && typeof m.emblems[0] === "string") return [];
  const e = m.emblems.find((x) => x.slot === slot);
  return (e && e.lines) || [];
}

function setSlotLine(i, slot, k, line, tier) {
  setState((s) => {
    const m = s.members[i];
    if (m.emblems.length && typeof m.emblems[0] === "string") m.emblems = [];
    let e = m.emblems.find((x) => x.slot === slot);
    if (!e) { e = { slot, lines: [] }; m.emblems.push(e); m.emblems.sort((a, b) => a.slot - b.slot); }
    const lines = [0, 1, 2, 3].map((n) => e.lines[n] || null);
    lines[k] = line ? { line, tier } : null;
    e.lines = lines.filter(Boolean);
    m.emblems = m.emblems.filter((x) => x.lines.length);
  });
}

function emblemSlot(i, m, t, slot) {
  const opts = (catalog.emblems[String(t.id)] || []).filter((o) => SLOT_KINDS[slot].includes(o.kind));
  const lines = slotLines(m, slot);
  const rows = [0, 1, 2, 3].map((k) => {
    const cur = lines[k];
    const opt = cur && opts.find((o) => o.name === cur.line);
    const lineSel = select(cur ? cur.line : "", [{ value: "", label: "—" }].concat(
      ["stat", "skill", "potential"].flatMap((kind) => opts.filter((o) => o.kind === kind)
        .map((o) => ({ value: o.name, label: kind === "potential" ? `${o.name} Lv.` : o.name })))),
      (v) => {
        const o = opts.find((x) => x.name === v);
        setSlotLine(i, slot, k, v, o ? o.tiers[o.tiers.length - 1].label : null);
      });
    const tierSel = opt ? select(cur.tier, opt.tiers.map((x) => ({ value: x.label, label: x.label, class: x.colour })),
      (v) => setSlotLine(i, slot, k, cur.line, v)) : h("span");
    if (opt) { const tt = opt.tiers.find((x) => x.label === cur.tier); if (tt) tierSel.className = `tier-select ${tt.colour}`; }
    return [lineSel, tierSel];
  });
  return h("div", { class: "emblem-slot" }, h("div", { class: "small muted" }, SLOT_NAMES[slot]),
    h("div", { class: "lines" }, rows));
}

function memberPanel(i) {
  const m = state.members[i];
  const role = roleOf(i);
  const t = trekker(m.trekker);
  const taken = state.members.map((x) => x.trekker);
  const head = h("div", {},
    h("div", { class: "role" }, i === 0 ? "Main" : `Support ${i}`),
    select(m.trekker, [{ value: "", label: "— trekker —" }].concat(catalog.trekkers.map((x) => ({
      value: x.name, label: `${x.name} (${x.element})`, disabled: taken.includes(x.name) && x.name !== m.trekker })),
    ), (v) => changeTrekker(i, v)));
  if (!t) {
    const unknown = m.trekker ? h("div", { class: "msg err" }, `${m.trekker} has no kit spec; it can't be simulated.`) : null;
    return h("div", { class: "panel" }, head, unknown);
  }
  const skills = h("div", { class: "field" }, SKILLS[role].map((sk) => h("label", {}, sk,
    select(String(m.skill_levels[sk] ?? 10), Array.from({ length: 10 }, (_, k) => ({ value: String(k + 1), label: String(k + 1) })),
      (v) => setState((s) => { s.members[i].skill_levels[sk] = Number(v); })))));
  const talents = h("div", { class: "field" }, h("label", {}, "Talents",
    select(String(m.talents || 0), Array.from({ length: t.talents + 1 }, (_, k) => ({ value: String(k), label: `T${k}` })),
      (v) => setState((s) => { s.members[i].talents = Number(v); }))));
  const legacy = m.emblems.length && typeof m.emblems[0] === "string"
    ? h("div", { class: "msg warn small" }, `Old-style emblems (top tier): ${m.emblems.join(", ")}. Editing a slot replaces them.`) : null;
  return h("div", { class: "panel" }, head, skills, talents, legacy, [1, 2, 3].map((slot) => emblemSlot(i, m, t, slot)));
}

function discPanel(side) {
  const docs = discDocs(side);
  const opts = [{ value: "filler", label: "filler (stats only)" }].concat(catalog.discs.map((d) => ({
    value: d.name, label: `${d.name} · ${d.element}${d.modelled ? "" : " (effect not modelled)"}` })));
  return h("div", { class: "panel" }, h("div", { class: "role" }, side === "main" ? "Main discs" : "Support discs"),
    docs.map((d, k) => {
      const disc = discByDoc(d);
      const copies = d === "filler" || !d ? 6 : Number(d.copies || 1);
      return h("div", { class: "disc-row" },
        select(disc ? disc.name : "filler", opts, (v) => setState((s) => {
          s.discs[side] = discDocs(side);
          s.discs[side][k] = v === "filler" ? "filler" : { name: v, copies: disc ? copies : 1 };
        })),
        disc ? select(String(copies), [1, 2, 3, 4, 5, 6].map((c) => ({ value: String(c), label: `C${c}` })),
          (v) => setState((s) => { s.discs[side] = discDocs(side); s.discs[side][k] = { name: disc.name, copies: Number(v) }; }))
          : h("span", { class: "small muted" }, "C6 stats"));
    }));
}

function advanced() {
  const num = (label, get, set, step) => h("label", {}, label, h("input", { type: "number", step: step || "any", value: get(),
    onchange: (e) => { const v = Number(e.target.value); if (Number.isFinite(v)) setState((s) => set(s, v)); } }));
  const d = h("details", { ontoggle: (e) => { ui.open.advanced = e.target.open; } },
    h("summary", {}, "Advanced"),
    h("div", { class: "field" },
      num("Enemy RES", () => state.enemy.res, (s, v) => { s.enemy.res = v; }),
      num("Enemy DEF", () => state.enemy.defense, (s, v) => { s.enemy.defense = v; }),
      num("Fight length (s)", () => state.fight_length ?? 120, (s, v) => { s.fight_length = v; }),
      num("Mark ICD (s)", () => state.mark_icd ?? 1, (s, v) => { s.mark_icd = v; })),
    h("div", { class: "small muted" }, "Other settings (reference build, assumptions) are kept from the team file."));
  if (ui.open.advanced) d.open = true;
  return d;
}

function teamSection() {
  return h("section", {}, h("h2", {}, "Team"),
    h("div", { class: "cols" }, [0, 1, 2].map(memberPanel)),
    h("h3", {}, "Discs"), h("div", { class: "discs" }, discPanel("main"), discPanel("support")),
    advanced());
}

// ---------------------------------------------------------------- pinks section
function togglePink(i, name) {
  setState((s) => {
    const m = s.members[i];
    if (m.pinks.includes(name)) m.pinks = m.pinks.filter((p) => p !== name);
    else if (m.pinks.length < 2) m.pinks = m.pinks.concat([name]);
    else m.pinks = [m.pinks[1], name];
  });
}

async function calcPinks(i) {
  try {
    const rows = await runJob("pinks", { member: i });
    ui.pinkRows[i] = rows;
    if (rows.length) setState((s) => { s.members[i].pinks = rows[0].pinks.slice(); });
  } catch (e) { /* shown */ }
}

function pinkPanel(i) {
  const m = state.members[i];
  const t = trekker(m.trekker);
  if (!t) return h("div", { class: "panel muted" }, "Pick a trekker first.");
  const pinks = t.roles[roleOf(i)].pinks;
  const rows = ui.pinkRows[i];
  const same = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
  return h("div", { class: "panel" },
    h("div", { class: "role" }, `${t.name} · ${m.pinks.length}/2`),
    [1, 2, 3].map((row) => {
      const ps = pinks.filter((p) => p.row === row);
      if (!ps.length) return null;
      return h("div", {}, h("div", { class: "small muted" }, ROWS[row]), h("div", { class: "pinks" },
        ps.map((p) => h("span", { class: `pink-toggle${m.pinks.includes(p.name) ? " on" : ""}`,
          onclick: () => togglePink(i, p.name) }, p.name))));
    }),
    h("div", { class: "field" }, h("button", { onclick: () => calcPinks(i), disabled: !!ui.job }, "Calculate best pinks"),
      h("span", { class: "small muted" }, "reference build, your discs; a few minutes")),
    rows ? h("table", { class: "pink-results" }, rows.map((r) => h("tr", {
      class: same(r.pinks, m.pinks) ? "chosen" : null,
      onclick: () => setState((s) => { s.members[i].pinks = r.pinks.slice(); }) },
    h("td", {}, r.pinks.join(" + ")), h("td", { style: "text-align:right" }, r.vs_best === 0 ? "best" : pct(r.vs_best))))) : null);
}
const ROWS = { 1: "Main Build 1", 2: "Main Build 2", 3: "Generic" };

function pinksSection() {
  return h("section", {}, h("h2", {}, "Pinks"), h("div", { class: "cols" }, [0, 1, 2].map(pinkPanel)));
}

// ---------------------------------------------------------------- formatting
function pct(v, digits = 1) {
  if (v === 0) return "0";
  const s = (Math.abs(v) * 100).toFixed(digits);
  return `${v > 0 ? "+" : "−"}${s}%`;
}

// ---------------------------------------------------------------- render
function render() {
  renderHeader();
  renderBanner();
  const app = document.getElementById("app");
  app.className = results && results.stale ? "stale" : "";
  app.replaceChildren(teamSection(), pinksSection(), ...SECTIONS.map((f) => f()));
}

async function init() {
  try {
    [catalog, ui.teams] = await Promise.all([api("GET", "/api/catalog"), api("GET", "/api/teams")]);
  } catch (e) {
    document.getElementById("app").textContent = `Can't reach the server: ${e.message}`;
    return;
  }
  state = newDoc();
  savedKey = JSON.stringify(state);
  render();
  const first = ui.teams.includes("amber_flora_chixia") ? "amber_flora_chixia" : ui.teams[0];
  if (first) loadTeam(first);
}

window.addEventListener("beforeunload", (e) => { if (state && savedKey !== JSON.stringify(state)) e.preventDefault(); });
document.addEventListener("DOMContentLoaded", init);
