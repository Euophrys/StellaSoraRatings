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
const calcKey = (s) => JSON.stringify({ ...s, name: undefined, budget: undefined, budget_total: undefined, max_level: undefined });

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
  return { name: "new_team", fight_length: 120, tick: 0.05, mark_icd: 1.0, enemy: { preset: "generic" },
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
  doc.enemy = doc.enemy || { preset: "generic" };
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
    m.value ? h("input", { value: m.value, readonly: true, size: 44, onfocus: (e) => e.target.select() }) : null,
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
  const kit = t.roles[role].kit;
  const kitMsg = kit === "missing"
    ? h("div", { class: "msg err" }, `${t.name} has no ${role} kit; this can't be simulated.`)
    : kit === "stub"
      ? h("div", { class: "msg warn small" }, `${t.name}'s ${role} kit is a placeholder, not timed in game, and its potentials aren't modelled. Don't trust these numbers.`)
      : null;
  const skills = h("div", { class: "field" }, SKILLS[role].map((sk) => h("label", {}, sk,
    select(String(m.skill_levels[sk] ?? 10), Array.from({ length: 10 }, (_, k) => ({ value: String(k + 1), label: String(k + 1) })),
      (v) => setState((s) => { s.members[i].skill_levels[sk] = Number(v); })))));
  const talents = h("div", { class: "field" }, h("label", {}, "Talents",
    select(String(m.talents || 0), Array.from({ length: t.talents + 1 }, (_, k) => ({ value: String(k), label: `T${k}` })),
      (v) => setState((s) => { s.members[i].talents = Number(v); }))));
  const legacy = m.emblems.length && typeof m.emblems[0] === "string"
    ? h("div", { class: "msg warn small" }, `Old-style emblems (top tier): ${m.emblems.join(", ")}. Editing a slot replaces them.`) : null;
  return h("div", { class: "panel" }, head, kitMsg, skills, talents, legacy, [1, 2, 3].map((slot) => emblemSlot(i, m, t, slot)));
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
  const enemies = catalog.enemies || [];
  const presetId = state.enemy.preset || "generic";
  const preset = enemies.find((x) => x.id === presetId) || {};
  const enemy = h("label", {}, "Enemy",
    select(presetId, enemies.map((x) => ({ value: x.id, label: x.label })), (v) => setState((s) => {
      const p = enemies.find((x) => x.id === v);
      s.enemy = { preset: v };   // drops RES/DEF overrides
      if (p && p.fight_length != null) s.fight_length = p.fight_length;
    })));
  const d = h("details", { ontoggle: (e) => { ui.open.advanced = e.target.open; } },
    h("summary", {}, "Advanced"),
    h("div", { class: "field" },
      enemy,
      num("Enemy RES", () => state.enemy.res ?? preset.res, (s, v) => { s.enemy.res = v; }),
      num("Enemy DEF", () => state.enemy.defense ?? preset.defense, (s, v) => { s.enemy.defense = v; }),
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

// ================================================================ potentials (preset grid)
const MAX_TARGET = 6;
const budgetOf = (i) => ((state.budget && state.budget[i] !== undefined) ? state.budget[i] : [30, 15, 15][i]);
const used = (m) => Object.values(m.targets || {}).reduce((a, b) => a + (Number(b) || 0), 0);
// shared budget: when set, the per-member budgets are caps on a pool of this size (null/0 = no shared total)
const totalBudget = () => (Number.isInteger(state.budget_total) && state.budget_total > 0 ? state.budget_total : null);

function setTarget(i, name, lv) {
  lv = Math.max(0, Math.min(MAX_TARGET, lv));
  setState((s) => {
    const t = { ...s.members[i].targets };
    if (lv > 0) t[name] = lv; else delete t[name];
    s.members[i].targets = t;
  });
}

function emblemPlus(m, potName) {
  // owned Lv90 "+N" line on this potential (sum if several)
  return slotLines(m, 3).filter((l) => l.line === potName && /^\+\d$/.test(l.tier))
    .reduce((a, l) => a + Number(l.tier.slice(1)), 0);
}

function cell(v) {
  if (v === undefined || v === null) return h("span", { class: "muted" }, "·");
  return h("span", { class: v > 0 ? "pos" : v < 0 ? "neg" : "" }, pct(v));
}

function potentialCard(i, m, p) {
  const lv = Number(m.targets[p.name] || 0);
  const plus = emblemPlus(m, p.name);
  const vals = results && results.grid ? results.grid[`${i}:${p.id}`] : null;
  return h("div", { class: "pcard" }, h("h4", {}, p.name),
    h("div", { class: "ctl" },
      h("button", { onclick: () => setTarget(i, p.name, lv - 1), disabled: lv <= 0 }, "−"),
      h("span", {}, `Lv ${lv}`),
      plus ? h("span", { class: "plus", title: "owned emblem line; doesn't count toward the budget" },
        `(+${plus} → ${Math.min(9, lv + plus)})`) : null,
      h("button", { onclick: () => setTarget(i, p.name, lv + 1), disabled: lv >= MAX_TARGET }, "+")),
    h("div", { class: "lv numbers" }, [1, 2, 3, 4, 5, 6].map((n) => h("div", {
      class: [n === lv ? "cur" : "", n <= lv ? "have" : ""].join(" ").trim() || null,
      title: `set target to ${n}${plus ? ` (fights at ${Math.min(9, n + plus)})` : ""}`,
      onclick: () => setTarget(i, p.name, n) }, h("small", {}, n), cell(vals ? vals[n - 1] : null)))));
}

function pinkCard(m, p) {
  const on = m.pinks.includes(p.name);
  return h("div", { class: `pcard pink${on ? "" : " off"}` }, h("h4", {}, p.name),
    h("div", { class: "ctl small" }, on ? "pink ✓" : "pink"));
}

function potentialsBlock(i) {
  const m = state.members[i];
  const t = trekker(m.trekker);
  if (!t) return null;
  const r = t.roles[roleOf(i)];
  const n = used(m), b = budgetOf(i);
  return h("div", { class: "panel", style: "margin-bottom:12px" },
    h("h3", {}, `${t.name} `, h("span", { class: `budget${n > b ? " over" : ""}` }, `${n} / ${b}`),
      h("span", { class: "small muted" }, i === 0 ? " · main" : " · support")),
    [1, 2, 3].map((row) => {
      const pinks = r.pinks.filter((p) => p.row === row);
      const pots = r.potentials.filter((p) => p.row === row);
      if (!pinks.length && !pots.length) return null;
      return [h("div", { class: "rowlabel" }, ROWS[row]),
        h("div", { class: "cards" }, pinks.map((p) => pinkCard(m, p)), pots.map((p) => potentialCard(i, m, p)))];
    }));
}

function potentialsSection() {
  const ready = state.members.every((m) => trekker(m.trekker));
  const head = h("div", { class: "field" },
    h("button", { class: "primary", onclick: recalc, disabled: !!ui.job || !ready }, results ? "Recalculate" : "Calculate"),
    results ? h("span", { class: "small muted" },
      `Team total ${(results.total / 1e6).toFixed(1)}M${results.breaks != null ? ` · ${results.breaks} break${results.breaks === 1 ? "" : "s"}` : ""} · calculated ${new Date(results.at).toLocaleString()}`)
      : h("span", { class: "small muted" }, "Each cell: total change in team damage if this potential's target were that level (current = 0). ~1 min."));
  const tb = totalBudget(), nAll = state.members.reduce((a, m) => a + used(m), 0);
  const shared = tb ? h("div", { class: "small" }, "Team total ",
    h("span", { class: `budget${nAll > tb ? " over" : ""}` }, `${nAll} / ${tb}`), " (per-Trekker numbers are caps)") : null;
  return h("section", {}, h("h2", {}, "Potentials"), head, shared, [0, 1, 2].map(potentialsBlock));
}

// ================================================================ optimize
async function runOptimize() {
  const split = [0, 1, 2].map(budgetOf);
  const maxLevel = state.max_level || MAX_TARGET;
  const total = totalBudget();
  try {
    const r = await runJob("optimize", { split, max_level: maxLevel, total });
    setState((s) => { s.members.forEach((m, i) => { m.targets = { ...r.targets[i] }; }); });
    ui.optimizeNote = `method: ${r.method}, total ×${(r.total / r.base_total).toFixed(2)} vs pinks only (${total ? `total ${total}, caps` : "split"} ${split.join(" / ")}, max Lv${maxLevel})`;
    await recalc();
  } catch (e) { /* shown */ }
}

function optimizeSection() {
  const num = (label, value, set, min, max) => h("label", {}, label, h("input", { type: "number", min, max, step: 1, value,
    onchange: (e) => { const v = Math.round(Number(e.target.value)); if (Number.isFinite(v) && v >= min && v <= max) setState((s) => set(s, v)); else render(); } }));
  const names = state.members.map((m, i) => (m.trekker || (i === 0 ? "Main" : `Support ${i}`)));
  const setBudget = (i) => (s, v) => { s.budget = [0, 1, 2].map(budgetOf); s.budget[i] = v; };
  return h("section", {}, h("h2", {}, "Optimize"),
    h("div", { class: "panel" },
      h("div", { class: "field" },
        num(names[0], budgetOf(0), setBudget(0), 0, 200), num(names[1], budgetOf(1), setBudget(1), 0, 200),
        num(names[2], budgetOf(2), setBudget(2), 0, 200),
        num("Total (0 = none)", totalBudget() || 0, (s, v) => { s.budget_total = v > 0 ? v : null; }, 0, 600),
        num("Max level", state.max_level || MAX_TARGET, (s, v) => { s.max_level = v; }, 1, MAX_TARGET),
        h("button", { class: "primary", onclick: runOptimize, disabled: !!ui.job || !state.members.every((m) => trekker(m.trekker)) }, "Optimize")),
      h("div", { class: "small muted" }, "Fills target levels with the best found for this split (greedy +1 steps, then swaps between a trekker's potentials), then recalculates. With a total, the per-Trekker numbers are caps on a shared pool and swaps can also move levels between Trekkers. Emblem +N levels are free. Takes minutes."),
      ui.optimizeNote ? h("div", { class: "small" }, ui.optimizeNote) : null));
}

// ================================================================ emblem tables
function emblemTables(i) {
  const m = state.members[i];
  const t = trekker(m.trekker);
  const rows = results && results.emblems ? results.emblems[String(i)] : null;
  if (!t || !rows) return null;
  const tables = [1, 2, 3].map((slot) => {
    const gains = (r) => (r.by_slot && r.by_slot[slot]) || r.tiers.map((x) => x[2]);
    const top = (r) => { const g = gains(r); return g[g.length - 1]; };
    const rs = rows.filter((r) => r.slots.includes(slot)).sort((a, b) => top(b) - top(a));
    const ordered = rs.filter((r) => r.relevant).concat(rs.filter((r) => !r.relevant));
    return h("div", {}, h("div", { class: "small muted" }, SLOT_NAMES[slot]),
      h("div", { class: "scroll" }, h("table", { class: "em numbers" },
        h("tr", {}, h("th", {}, "Line"), h("th", { colspan: 4 }, "team damage per roll")),
        ordered.map((r) => {
          let sub = null;
          if (r.kind === "potential") {
            const lv = Number(m.targets[r.name] || 0);
            const top = Number(r.tiers[r.tiers.length - 1][0].slice(1));
            sub = h("div", { class: "small muted" }, `Lv ${lv}→${Math.min(9, lv + emblemPlus(m, r.name) + top)} at +${top}`);
          }
          const pad = Array.from({ length: 4 - r.tiers.length }, () => h("td", {}));
          return h("tr", { class: r.relevant ? null : "irrelevant" }, h("td", {}, r.name, sub), pad,
            r.tiers.map(([label, colour], k) => [label, colour, gains(r)[k]]).map(([label, colour, g]) => h("td", { title: `${colour}${label !== colour ? ` ${label}` : ""}` },
              h("span", { class: `tier ${colour}` }, label !== colour ? `${label} ` : "", r.relevant ? pct(g) : "—"))));
        }))));
  });
  return h("div", { class: "panel", style: "margin-bottom:12px" }, h("h3", {}, t.name), h("div", { class: "emtables" }, tables));
}

function emblemSection() {
  return h("section", {}, h("h2", {}, "Emblem lines"),
    results ? h("div", { class: "small muted" }, "Each line's team damage on top of the current build and owned emblems, per roll tier. Stat lines count as stacking: Lv80 is a 2nd copy on top of the same line on Lv70, Lv90 a 3rd. Sorted by the best tier.",
      h("span", { class: "legend" }, ["green", "blue", "yellow", "purple"].map((c) => h("span", { class: `tier ${c}` }, c))))
      : h("div", { class: "small muted" }, "Calculate to see emblem lines."),
    [0, 1, 2].map(emblemTables));
}

SECTIONS.push(potentialsSection, optimizeSection, emblemSection);

// ================================================================ export
async function exportHtml() {
  const css = await fetch("/static/app.css").then((r) => r.text()).catch(() => "");
  const clone = document.getElementById("app").cloneNode(true);
  const live = document.getElementById("app").querySelectorAll("select");
  clone.querySelectorAll("select").forEach((s, k) => {
    const v = live[k].value;
    const text = live[k].selectedOptions[0] ? live[k].selectedOptions[0].textContent : "";
    if (!v && s.closest(".emblem-slot")) { s.remove(); return; }
    const span = document.createElement("span");
    span.className = `${s.className} picked`;
    span.textContent = v ? text : "—";
    s.replaceWith(span);
  });
  clone.querySelectorAll("input").forEach((x) => { const s = document.createElement("span"); s.textContent = x.value; x.replaceWith(s); });
  clone.querySelectorAll("button").forEach((b) => b.remove());
  clone.querySelectorAll("details").forEach((d) => d.setAttribute("open", ""));
  clone.querySelectorAll(".emblem-slot .lines").forEach((l) => { if (!l.children.length) l.append("none"); });
  [...clone.querySelectorAll("section")].filter((s) => s.querySelector("h2")?.textContent === "Optimize").forEach((s) => {
    s.querySelectorAll(".muted").forEach((x) => x.remove());
  });
  const name = state.name || ui.stem || "build";
  const when = results ? new Date(results.at).toLocaleString() : "never";
  const note = !results ? "<p class=\"msg warn\">No numbers: this build wasn't calculated.</p>"
    : results.stale ? "<p class=\"msg warn\">Numbers are stale: levels changed after the last calculation.</p>" : "";
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(name)} — build</title><style>${css}
.picked{font-weight:600} .lv div, .pink-toggle, .pink-results td{cursor:default} body{padding-bottom:20px}</style></head>
<body><main class="${results && results.stale ? "stale" : ""}"><h1 style="font-size:20px;margin:16px 0 0">${esc(name)}</h1>
<p class="small muted">Stella Sora build guide · calculated ${esc(when)} · all numbers from the ssr simulator (% team damage)</p>${note}
${clone.innerHTML}</main></body></html>`;
  const a = h("a", { href: URL.createObjectURL(new Blob([html], { type: "text/html" })), download: `${name}.html` });
  document.body.append(a); a.click(); a.remove();
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

headerExtras.push(() => h("button", { onclick: exportHtml }, "Export"));

// ================================================================ game share codes
async function importCode() {
  const code = prompt("Paste a preset share code from the game:");
  if (!code) return;
  let d;
  try { d = await api("POST", "/api/sharecode/decode", { code: code.trim() }); } catch (e) { message("err", e.message); return; }
  const missing = d.members.filter((m) => !trekker(m.trekker)).map((m) => m.trekker);
  if (missing.length) { message("err", `No kit spec for ${missing.join(", ")}; those trekkers can't be simulated yet.`); return; }
  const same = d.members.every((m, i) => state.members[i].trekker === m.trekker);
  setState((s) => {
    d.members.forEach((dm, i) => {
      const keep = s.members[i].trekker === dm.trekker;
      const m = keep ? s.members[i] : blankMember(i);
      m.trekker = dm.trekker; m.pinks = dm.pinks.slice(); m.targets = { ...dm.targets };
      s.members[i] = m;
    });
    if (!same) s.discs = { main: ["filler", "filler", "filler"], support: ["filler", "filler", "filler"] };
  });
  if (!same) { results = null; ui.pinkRows = {}; ui.optimizeNote = null; render(); }
  message("info", same ? "Imported pinks and target levels (discs and emblems kept)."
    : "Imported trekkers, pinks and target levels. Set discs and emblems for the new team.");
}

async function copyCode() {
  let code;
  try { code = (await api("POST", "/api/sharecode/encode", { state })).code; } catch (e) { message("err", e.message); return; }
  let copied = false;
  try { await navigator.clipboard.writeText(code); copied = true; } catch (e) { /* fallback below */ }
  ui.messages = ui.messages.filter((m) => !m.value);
  ui.messages.push({ kind: "info", value: code, text: copied ? "Copied preset code:" : "Preset code (copy it):" });
  renderBanner();
}

headerExtras.push(() => h("button", { onclick: importCode }, "Import code"),
  () => h("button", { onclick: copyCode, disabled: !state.members.every((m) => trekker(m.trekker)) }, "Copy code"));
