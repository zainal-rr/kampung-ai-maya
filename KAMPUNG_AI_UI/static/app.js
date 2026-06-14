"use strict";

const token = new URLSearchParams(location.search).get("token") ||
  sessionStorage.getItem("maya-ui-token") || "";
if (token) sessionStorage.setItem("maya-ui-token", token);
const q = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const api = (p) => fetch(p + (p.includes("?") ? "&" : "?") + "token=" +
  encodeURIComponent(token)).then((r) => { if (!r.ok) throw r; return r.json(); });

const hr = new Date().getHours();
q("greet").textContent = (hr < 12 ? "Selamat pagi" : hr < 15 ? "Selamat tengah hari" :
  hr < 19 ? "Selamat petang" : "Selamat malam") + ", Zainal.";
const root = document.documentElement, themeBtn = q("themeBtn");
const saved = localStorage.getItem("maya-theme"); if (saved) root.dataset.theme = saved;
const syncBtn = () => { themeBtn.textContent = root.dataset.theme === "dark" ? "Light" : "Dark"; };
syncBtn();
themeBtn.addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("maya-theme", root.dataset.theme); syncBtn();
});

q("nav").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#nav button").forEach((x) => x.classList.toggle("on", x === b));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("on", v.id === "v-" + b.dataset.v));
});

const bell = q("bellBtn"), pop = q("alertsPop");
bell.addEventListener("click", (e) => { e.stopPropagation(); pop.classList.toggle("on"); });
document.addEventListener("click", (e) => { if (!e.target.closest("#alertsPop")) pop.classList.remove("on"); });

const STATE = { completed: "ok", waiting_approval: "wait", waiting_user: "wait",
  running: "wait", executing: "wait", paused: "wait", failed: "bad", cancelled: "idle" };
const dotFor = (cls) => cls === "ok" ? "var(--bamboo)" : cls === "wait" ? "var(--gold)"
  : cls === "bad" ? "var(--rose)" : "var(--ink3)";
const ACTIVE = new Set(["running", "waiting_approval", "waiting_user", "paused", "executing"]);

function lrow(dot, busy, nm, sb, end) {
  return `<div class="lrow"><span class="d${busy ? " busy" : ""}" style="background:${dot}"></span>
    <div style="min-width:0"><div class="nm">${nm}</div><div class="sb">${sb}</div></div>
    <span class="end">${end || ""}</span></div>`;
}

function renderDesk(d) {
  const strip = q("apprStrip");
  if (d.approvals.length) {
    strip.style.display = "flex";
    q("apprCount").textContent = `${d.approvals.length} approval${d.approvals.length > 1 ? "s" : ""} waiting.`;
    q("apprNames").textContent = d.approvals.slice(0, 3).map((a) => a.action).join(" · ");
  } else strip.style.display = "none";

  const n = q("bellN");
  n.style.display = d.approvals.length ? "grid" : "none";
  n.textContent = d.approvals.length;
  pop.innerHTML = d.approvals.length ? d.approvals.slice(0, 6).map((a) =>
    `<div class="al"><div><b>${esc(a.action)}</b><br>${esc((a.details || "").slice(0, 90))}…</div></div>`).join("")
    : `<div class="al"><div><b>Nothing waiting</b><br>all clear</div></div>`;

  const active = d.runs.filter((r) => ACTIVE.has(r.status)).slice(0, 4);
  q("runcards").innerHTML = active.length ? active.map((r) => {
    const cls = STATE[r.status] || "idle";
    return `<div class="runcard">
      <div class="rc-h"><span class="pulse ok" style="background:${dotFor(cls)}"></span>
        <span class="nm2">${esc(r.goal || r.workflow_type)}</span>
        <span class="rc-id">${esc(r.run_id)}</span>
        <span style="margin-left:auto"><span class="state ${cls}">${esc(r.status)}</span></span></div>
      <div class="cone">${esc(r.thread_id || "")} · ${esc(r.channel || "")} · step ${esc(r.current_step ?? "—")}<br>
        updated ${esc(r.updated_at || "")}</div></div>`;
  }).join("") : `<div class="empty">no active runs right now</div>`;

  q("approvals").innerHTML = d.approvals.length ? d.approvals.slice(0, 5).map((a) =>
    lrow("var(--gold)", true, esc(a.action), esc((a.details || "").slice(0, 70)),
      `<span class="state wait">pending</span>`)).join("")
    : `<div class="empty">nothing waiting — all clear</div>`;

  q("runs").innerHTML = d.runs.slice(0, 6).map((r) => {
    const cls = STATE[r.status] || "idle";
    return lrow(dotFor(cls), cls === "wait", esc(r.goal || r.workflow_type),
      `${esc(r.run_id)} · ${esc(r.channel || "")}`, `<span class="state ${cls}">${esc(r.status)}</span>`);
  }).join("") || `<div class="empty">—</div>`;

  const t = d.tasks || {}, open = (t.open || 0) + (t.pending || 0) + (t.scheduled || 0);
  const lastRoute = d.last_routes[0];
  q("today").innerHTML =
    lrow("var(--gold)", false, "Waiting on you", `${d.approvals.length} approvals`, "") +
    lrow("var(--bamboo)", false, "Open tasks", `${open} open · ${t.done || t.completed || 0} done`, "") +
    (lastRoute ? lrow("var(--ink3)", false, "Last route", `${esc(lastRoute.input_type)} · ${esc(lastRoute.created_at)}`, "") : "");

  q("routes").innerHTML = `<tr><th>route</th><th>lane</th><th>when</th></tr>` +
    d.last_routes.map((r) =>
      `<tr><td class="k">${esc(r.input_type)} → ${esc((r.reason || "").slice(0, 40))}</td>
       <td>${esc((r.lane || "").slice(0, 60))}</td><td class="k">${esc((r.created_at || "").slice(5, 16))}</td></tr>`).join("");

  q("threads").innerHTML = (d.threads || []).slice(0, 6).map((th) =>
    lrow(th.busy ? "var(--gold)" : "var(--bamboo)", th.busy, esc(th.thread_id),
      `${th.runs} runs · ${esc(th.updated_at || "")}`, "")).join("") || `<div class="empty">—</div>`;

  const canHtml = d.canaries.map((c) => {
    const ok = (c.last_result || "").toLowerCase() === "pass" || !c.failure_reason;
    return lrow(ok ? "var(--bamboo)" : "var(--rose)", false, esc(c.subject_key),
      `expect ${esc(c.expected_state)} · ${esc(c.last_checked_at || "never checked")}`,
      `<span class="state ${ok ? "ok" : "bad"}">${ok ? "clean" : "leak"}</span>`);
  }).join("") || `<div class="empty">no canaries seeded</div>`;
  q("canaries").innerHTML = canHtml;
  q("canaries2").innerHTML = canHtml;

  q("usage").innerHTML = d.usage_today.length ? d.usage_today.map((u) =>
    lrow("var(--ink3)", false, esc(u.lane), `${u.calls} calls`, "")).join("")
    : `<div class="empty">no provider calls today</div>`;
}

function renderMemory(items, summary) {
  q("memTable").innerHTML = `<tr><th>subject key</th><th>class</th><th>reinforced</th><th>preview</th></tr>` +
    items.map((m) => {
      const cls = m.pinned ? "ok" : m.status === "active" ? "ok" : m.status === "forgotten" ? "bad" : "idle";
      const label = m.pinned ? "pinned" : m.status;
      return `<tr><td class="k">${esc(m.subject_key)}</td>
        <td><span class="state ${cls}">${esc(label)}</span></td>
        <td class="k">${esc(m.reinforced ?? "—")}</td><td>${esc(m.preview)}</td></tr>`;
    }).join("");
  const s = summary || {};
  q("memSummary").textContent = `${s.total ?? 0} canonical facts · ${s.pinned ?? 0} pinned · ` +
    Object.entries(s.by_status || {}).map(([k, v]) => `${v} ${k}`).join(" · ");
}

const EXT = { document: "DOCX", presentation: "PPTX", spreadsheet: "XLSX", drawing: "SVG",
  markdown: "MD", html: "HTML", model: "STL", screenshot: "PNG" };
function renderArtifacts(items) {
  q("gallery").innerHTML = items.map((a) =>
    `<div class="file"><div class="ic2">${esc(EXT[a.kind] || (a.kind || "?").slice(0, 4).toUpperCase())}</div>
     <div style="min-width:0"><div class="nm">${esc(a.name)}</div>
     <div class="st">${esc(a.summary)} · ${esc(a.delivery_status || "")}</div></div></div>`).join("")
    || `<div class="empty">no artifacts yet</div>`;
}

const CHAT = { desk: null, messages: [], events: [], artifacts: [] };
const cut = (s, n = 120) => String(s || "").length > n ? String(s).slice(0, n - 1) + "…" : String(s || "");
const when = (ts) => ts ? String(ts).replace("T", " ").slice(5, 16) : "now";
const channelName = (c) => ({ telegram: "Telegram", imac_voice: "iMac voice",
  history: "History", imac: "iMac", screen: "Screen" }[c] || c || "Maya");

function rememberEvents(items) {
  const byKey = new Map(CHAT.events.map((e) => [`${e.type}:${e.id}`, e]));
  (items || []).forEach((e) => { if (e && ["harness", "route"].includes(e.type)) byKey.set(`${e.type}:${e.id}`, e); });
  CHAT.events = [...byKey.values()].sort((a, b) =>
    String(a.ts || "").localeCompare(String(b.ts || ""))).slice(-50);
}

function renderThreads() {
  const d = CHAT.desk || {}, rows = (d.threads || []).slice(0, 9);
  const fallback = rows.length ? rows : [{ thread_id: "maya:conversation",
    runs: CHAT.messages.length, updated_at: (CHAT.messages[CHAT.messages.length - 1] || {}).created_at,
    busy: (d.runs || []).some((r) => ACTIVE.has(r.status)) }];
  q("chatThreads").innerHTML = fallback.map((th, i) =>
    `<button class="thread-row ${i === 0 ? "active" : ""} ${th.busy ? "busy" : ""}" type="button">
      <span class="d"></span><span style="min-width:0"><span class="nm">${esc(th.thread_id)}</span>
      <span class="sb">${esc(th.runs || 0)} turns · ${esc(when(th.updated_at))}</span></span></button>`).join("");
}

function renderChatItem(item) {
  if (item.ui === "message") {
    const m = item.data, maya = m.role !== "user";
    const meta = maya ? `<b>Maya</b> · ${esc(channelName(m.channel))} · ${esc(when(m.created_at))}`
      : `Zainal · ${esc(channelName(m.channel))} · ${esc(when(m.created_at))}`;
    return `<div class="bubble ${maya ? "maya" : "user"}"><div class="meta">${meta}</div>
      <div class="txt">${esc(m.content).replace(/\n/g, "<br>")}</div></div>`;
  }
  if (item.ui === "event") {
    const e = item.data;
    return `<div class="event-block"><div class="k">${esc(e.type)} · ${esc(when(e.ts))}</div>
      <div>${esc(e.lane ? e.lane + " · " : "")}${esc(e.summary)}</div></div>`;
  }
  if (item.ui === "approval") {
    const a = item.data;
    return `<div class="ask"><div class="h">Approval — ${esc(a.action)}</div>
      <p>${esc(a.details || "Waiting for your confirmation.")}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn yes" disabled>Approve once</button>
      <button class="btn" disabled>Deny</button><button class="btn" disabled>Later</button></div></div>`;
  }
  const a = item.data, label = EXT[a.kind] || (a.kind || "file").slice(0, 4).toUpperCase();
  return `<div class="bubble maya"><div class="meta"><b>Maya</b> · artifact · ${esc(when(a.created_at))}</div>
    <div class="file"><div class="ic2">${esc(label)}</div><div style="min-width:0">
    <div class="nm">${esc(a.name)}</div><div class="st">${esc(a.summary)} · ${esc(a.delivery_status || "")}</div></div></div></div>`;
}

function renderContext(active) {
  const art = CHAT.artifacts[0], rows = [];
  if (art) {
    q("ctxTitle").innerHTML = `${esc(art.name)} <span class="sub">latest artifact</span>`;
    q("ctxBadges").innerHTML = `<span class="state ok">${esc(art.exists_status || "tracked")}</span><span class="state ok">${esc(art.delivery_status || "local")}</span>`;
    rows.push(["kind", EXT[art.kind] || art.kind || "file"], ["created", when(art.created_at)], ["summary", cut(art.summary, 80)]);
    q("ctxChipName").textContent = art.name || "latest artifact";
    q("ctxChipText").textContent = "Latest artifact is pinned beside the conversation.";
  } else if (active) {
    const cls = STATE[active.status] || "idle";
    q("ctxTitle").innerHTML = `${esc(cut(active.goal || active.workflow_type, 36))} <span class="sub">active run</span>`;
    q("ctxBadges").innerHTML = `<span class="state ${cls}">${esc(active.status)}</span>`;
    rows.push(["run", active.run_id], ["thread", active.thread_id], ["channel", active.channel], ["updated", when(active.updated_at)]);
    q("ctxChipName").textContent = active.workflow_type || "active run";
    q("ctxChipText").textContent = "Active run context is mirrored here.";
  } else {
    q("ctxTitle").innerHTML = `Context <span class="sub">idle</span>`;
    q("ctxBadges").innerHTML = `<span class="state idle">read-only</span>`;
    rows.push(["store", "live"], ["mode", "mirror"]);
  }
  q("ctxTable").innerHTML = rows.map(([k, v]) => `<tr><td class="k">${esc(k)}</td><td>${esc(v)}</td></tr>`).join("");
  const evs = CHAT.events.filter((e) => !active || !e.run_id || e.run_id === active.run_id).slice(-6).reverse();
  q("traceRun").textContent = active ? cut(active.run_id, 16) : "latest";
  q("traceList").innerHTML = evs.length ? evs.map((e) =>
    `<div class="ev"><i class="${e.type === "route" ? "gate" : ""}"></i><div class="w"><b>${esc(e.type)}</b>
    <span>${esc(cut(e.summary, 54))}</span></div><time>${esc(when(e.ts).slice(6))}</time></div>`).join("")
    : `<div class="empty">no run trace yet</div>`;
  const step = Number(active && active.current_step || 0), meter = q("traceMeter");
  meter.style.display = active ? "block" : "none";
  q("traceStep").textContent = `${step} / 8`;
  q("traceFill").style.width = Math.min(100, Math.max(0, step * 12.5)) + "%";
}

function renderChat() {
  const d = CHAT.desk || { approvals: [], runs: [], threads: [] };
  const active = (d.runs || []).find((r) => ACTIVE.has(r.status)) || (d.runs || [])[0];
  q("chatTitle").textContent = active ? cut(active.goal || active.workflow_type, 58) : "Maya conversation";
  q("chatSub").textContent = active ? `${active.thread_id || active.channel || "runtime"} · step ${active.current_step ?? "—"}`
    : `${CHAT.messages.length} recent turns · ${CHAT.events.length} runtime events`;
  q("chatChip").innerHTML = active ? `<i></i>${esc(String(active.status || "run").toUpperCase())}` : `<i></i>LIVE MIRROR`;
  renderThreads();
  const merged = [
    ...CHAT.messages.map((m) => ({ ui: "message", ts: m.created_at, data: m })),
    ...CHAT.events.map((e) => ({ ui: "event", ts: e.ts, data: e })),
    ...(d.approvals || []).map((a) => ({ ui: "approval", ts: a.created_at, data: a })),
    ...CHAT.artifacts.slice(0, 8).map((a) => ({ ui: "artifact", ts: a.created_at, data: a })),
  ].sort((a, b) => String(a.ts || "").localeCompare(String(b.ts || ""))).slice(-42);
  q("chatBody").innerHTML = merged.length ? merged.map(renderChatItem).join("")
    : `<div class="divider">conversation</div><div class="empty">No recent conversation rows in this store yet.</div>`;
  q("chatBody").scrollTop = q("chatBody").scrollHeight;
  renderContext(active);
}

const feed = q("feed");
function addFeedItem(item) {
  if (!item || !["harness", "route"].includes(item.type)) return;
  rememberEvents([item]); if (CHAT.desk) renderChat();
  const first = feed.querySelector(".empty"); if (first) first.remove();
  const div = document.createElement("div");
  div.className = "ev";
  div.innerHTML = `<span class="tp ${esc(item.type)}">${esc(item.type.toUpperCase())}</span>
    <span class="sum">${esc(item.lane ? item.lane + " · " : "")}${esc(item.summary)}</span>
    <time>${esc((item.ts || "").slice(11, 19) || item.ts)}</time>`;
  feed.prepend(div);
  while (feed.children.length > 80) feed.lastChild.remove();
}
function connectStream(cursor) {
  const es = new EventSource(`/events?token=${encodeURIComponent(token)}&he=${cursor.he}&re=${cursor.re}`);
  const onItem = (e) => { try { addFeedItem(JSON.parse(e.data)); } catch { /* tolerant */ }
    q("feed-cursor").textContent = "cursor " + (e.lastEventId || "live"); };
  es.addEventListener("harness", onItem);
  es.addEventListener("route", onItem);
}

async function boot() {
  try {
    const h = await api("/api/health");
    q("health-dot").className = "pulse " + (h.ok ? "ok" : "bad");
    q("health-text").textContent = h.ok ? "runtime store live · read-only" : "store unavailable";
    q("sub").textContent = h.ok ?
      "live view of the runtime — actions happen in chat, not here" : `expected store at ${h.db}`;
    if (!h.ok) return;
    const [d, recent, mem, arts, conv] = await Promise.all([
      api("/api/desk"), api("/api/events/recent?limit=25"),
      api("/api/memory?limit=40"), api("/api/artifacts?limit=25"),
      api("/api/conversation?limit=70")]);
    CHAT.desk = d; CHAT.messages = conv.items || []; CHAT.artifacts = arts.items || [];
    renderDesk(d); renderMemory(mem.items, d.memory); renderArtifacts(arts.items);
    recent.items.forEach(addFeedItem); renderChat();
    connectStream(recent.cursor);
    setInterval(async () => { try {
      CHAT.desk = await api("/api/desk"); renderDesk(CHAT.desk); renderChat();
    } catch { /* keep last */ } }, 20000);
    setInterval(async () => { try {
      const [nextConv, nextArts] = await Promise.all([
        api("/api/conversation?limit=70"), api("/api/artifacts?limit=25")]);
      CHAT.messages = nextConv.items || []; CHAT.artifacts = nextArts.items || [];
      renderArtifacts(CHAT.artifacts); renderChat();
    } catch { /* keep last */ } }, 30000);
  } catch (err) {
    q("health-dot").className = "pulse bad";
    q("health-text").textContent = (err && err.status === 401) ?
      "unauthorized — add ?token=… to the URL" : "server unreachable";
  }
}
boot();
