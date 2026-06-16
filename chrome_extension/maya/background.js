// Maya Browser Automation - background service worker.
// Connects to Maya's local bridge, keeps a named "Maya" tab group, shows a
// RUN badge while commands execute, and answers browser-control commands.

const BRIDGE_URL = "ws://127.0.0.1:8975/maya";
const HEALTH_URL = "http://127.0.0.1:8976/health";
const GROUP_TITLE = "Maya";
const GROUP_COLOR = "yellow";
const SENSITIVE_URL = /checkout|payment|signin|login|password|otp/i;
const RECONNECT_DELAY_MS = 1500;
const HEALTH_TIMEOUT_MS = 800;
const HEALTH_EXPECTED_BODY = "maya-extension-bridge-ok";
const HEARTBEAT_INTERVAL_MS = 20000;

let socket = null;
let groupId = null;
let automationWindowId = null;
let activeOps = 0;
let reconnectTimer = null;
let heartbeatTimer = null;

function setBadge() {
  const connected = socket && socket.readyState === WebSocket.OPEN;
  chrome.action.setBadgeText({ text: activeOps > 0 ? "RUN" : connected ? "ON" : "" });
  chrome.action.setBadgeBackgroundColor({ color: activeOps > 0 ? "#e8710a" : "#188038" });
}

async function bridgeToken() {
  const stored = await chrome.storage.local.get("token");
  return stored.token || "";
}

async function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
  const token = await bridgeToken();
  if (!token) {
    setBadge();
    return;
  }
  if (!(await bridgeReachable())) {
    setBadge();
    scheduleReconnect();
    return;
  }
  let ws;
  try {
    ws = new WebSocket(`${BRIDGE_URL}?token=${encodeURIComponent(token)}`);
    socket = ws;
  } catch (e) {
    scheduleReconnect();
    return;
  }
  ws.onopen = () => {
    safeSend(ws, { event: "connected", extension: "maya", version: 1 });
    sendHeartbeat();
    setBadge();
  };
  ws.onclose = async () => {
    if (socket === ws) socket = null;
    setBadge();
    scheduleReconnect();
  };
  ws.onerror = () => {};
  ws.onmessage = async (msg) => {
    let req;
    try { req = JSON.parse(msg.data); } catch (e) { return; }
    if (!req.id || !req.op) return;
    activeOps += 1; setBadge();
    let reply;
    try {
      reply = { id: req.id, ok: true, result: await handle(req.op, req.args || {}) };
    } catch (e) {
      reply = { id: req.id, ok: false, error: String(e && e.message ? e.message : e) };
    }
    activeOps -= 1; setBadge();
    safeSend(ws, reply);
  };
}

async function bridgeReachable() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
  try {
    const response = await fetch(`${HEALTH_URL}?t=${Date.now()}`, { cache: "no-store", signal: controller.signal });
    if (!response.ok) return false;
    const body = (await response.text()).trim();
    return body === HEALTH_EXPECTED_BODY;
  } catch (e) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

function safeSend(ws, payload) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return false;
  try {
    ws.send(JSON.stringify(payload));
    return true;
  } catch (e) {
    return false;
  }
}

function sendHeartbeat() {
  safeSend(socket, { event: "heartbeat", at: Date.now() });
}

function startHeartbeatLoop() {
  if (heartbeatTimer) return;
  heartbeatTimer = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      sendHeartbeat();
    } else {
      connect();
    }
  }, HEARTBEAT_INTERVAL_MS);
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, RECONNECT_DELAY_MS);
}

// Keep the service worker and the socket alive.
startHeartbeatLoop();
chrome.alarms.create("maya-keepalive", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => {
  startHeartbeatLoop();
  if (socket && socket.readyState === WebSocket.OPEN) {
    sendHeartbeat();
  } else {
    connect();
  }
});
chrome.runtime.onStartup.addListener(() => { startHeartbeatLoop(); connect(); });
chrome.runtime.onInstalled.addListener(() => { startHeartbeatLoop(); connect(); });
connect();

async function ensureGroup() {
  await loadAutomationWindowId();
  if (groupId !== null) {
    try {
      const group = await chrome.tabGroups.get(groupId);
      const tabs = await chrome.tabs.query({ groupId });
      if (!tabs.length || group.windowId === undefined) throw new Error("stale Maya group");
      automationWindowId = group.windowId;
      await chrome.tabGroups.update(groupId, { title: GROUP_TITLE, color: GROUP_COLOR });
      return groupId;
    } catch (e) { groupId = null; }
  }
  const groups = automationWindowId === null ? [] : await liveMayaGroups({ windowId: automationWindowId });
  for (const group of groups) {
    if (group.windowId === undefined) continue;
    const tabs = await chrome.tabs.query({ groupId: group.id });
    if (!tabs.length) continue;
    groupId = group.id;
    automationWindowId = group.windowId;
    await chrome.tabGroups.update(groupId, { title: GROUP_TITLE, color: GROUP_COLOR });
    return groupId;
  }
  const windowId = await ensureWindow();
  const windowTabs = await chrome.tabs.query({ windowId }).catch(() => []);
  const tab = windowTabs.find(isBannerTab) || await chrome.tabs.create({ url: "about:blank", active: false, windowId });
  groupId = await chrome.tabs.group({ tabIds: [tab.id] });
  automationWindowId = windowId;
  await saveAutomationWindowId(windowId);
  await chrome.tabGroups.update(groupId, { title: GROUP_TITLE, color: GROUP_COLOR });
  return groupId;
}

async function loadAutomationWindowId() {
  if (automationWindowId !== null) return automationWindowId;
  const stored = await chrome.storage.local.get("automationWindowId").catch(() => ({}));
  const value = Number(stored.automationWindowId || 0);
  if (!value) return null;
  try {
    const existing = await chrome.windows.get(value);
    if (existing && existing.type === "normal") {
      automationWindowId = value;
      return automationWindowId;
    }
  } catch (e) {}
  await chrome.storage.local.remove("automationWindowId").catch(() => {});
  return null;
}

async function saveAutomationWindowId(windowId) {
  automationWindowId = windowId;
  await chrome.storage.local.set({ automationWindowId: windowId }).catch(() => {});
}

async function ensureWindow() {
  await loadAutomationWindowId();
  if (automationWindowId !== null) {
    try {
      const existing = await chrome.windows.get(automationWindowId);
      if (existing && existing.type === "normal") return automationWindowId;
    } catch (e) {
      automationWindowId = null;
    }
  }
  const created = await chrome.windows.create({ url: "about:blank", focused: true });
  await saveAutomationWindowId(created.id);
  return automationWindowId;
}

async function liveMayaGroups(options = {}) {
  const windows = options.windowId !== undefined
    ? [await chrome.windows.get(options.windowId).catch(() => null)].filter(Boolean)
    : await chrome.windows.getAll({ windowTypes: ["normal"] }).catch(() => []);
  const rows = [];
  for (const win of windows) {
    if (win.id === undefined) continue;
    const groups = await chrome.tabGroups.query({ title: GROUP_TITLE, windowId: win.id }).catch(() => []);
    rows.push(...groups);
  }
  return rows;
}

async function groupTabs() {
  if (groupId === null) return [];
  return chrome.tabs.query({ groupId });
}

async function allMayaGroupTabs() {
  const groups = await liveMayaGroups();
  const rows = [];
  for (const group of groups) {
    const tabs = await chrome.tabs.query({ groupId: group.id });
    rows.push({ group, tabs });
  }
  return rows;
}

async function activeGroupTab() {
  const tabs = await groupTabs();
  if (!tabs.length) throw new Error("no Maya tab open yet");
  const usable = tabs.filter((t) => {
    const url = t.url || "";
    return url && !url.startsWith("about:blank") && !url.startsWith("chrome://") && !url.startsWith("chrome-extension://");
  });
  return usable.find((t) => t.active) || usable[usable.length - 1] || tabs.find((t) => t.active) || tabs[tabs.length - 1];
}

function isBannerTab(tab) {
  const url = tab.url || "";
  return url === "about:blank" || url.startsWith("chrome://newtab") || url.startsWith("chrome://new-tab-page");
}

async function targetTab(args) {
  if (args.tabId) return chrome.tabs.get(args.tabId);
  return activeGroupTab();
}

function pageTextFn(maxChars) {
  const text = document.body ? document.body.innerText : "";
  return { title: document.title, url: location.href, text: text.slice(0, Math.max(500, maxChars)) };
}

function mayaGroupProofForTab(tab) {
  const tabGroupId = tab.groupId === undefined ? -1 : tab.groupId;
  return {
    tabId: tab.id,
    groupId,
    windowId: tab.windowId,
    openedInMayaGroup: groupId !== null && tabGroupId === groupId && tab.windowId === automationWindowId,
  };
}

function elementsFn(maxItems) {
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const label = (e) => norm(e.innerText || e.value || e.getAttribute("aria-label") || e.placeholder || e.name || e.title || "");
  const nodes = [...document.querySelectorAll("a,button,input,textarea,select,[role=button],[role=link],summary")];
  return nodes
    .filter(visible)
    .map((e) => ({ kind: e.tagName.toLowerCase(), label: label(e) }))
    .filter((x) => x.label)
    .slice(0, Math.max(1, maxItems || 25));
}

function searchResultOptionsFn(maxItems) {
  const max = Math.max(1, Math.min(20, maxItems || 8));
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const pageHost = location.hostname.toLowerCase();
  const isYouTube = /youtube\.com$/.test(pageHost);
  const isReddit = /(^|\.)reddit\.com$/.test(pageHost);
  const badHref = (h) => !h || /google\.[^/]+\/(search|preferences|advanced_search|intl|policies)|accounts\.google|support\.google|javascript:|[?&]entry_point=/i.test(h);
  const badText = (t) => /(cached|similar|translate this page|privacy|terms|settings|tools|feedback|sign in|images|videos|maps|shopping|news|home|shorts|subscriptions|library|history|you|premium)$/i.test(t) || /monthly players/i.test(t);
  const siteAllowed = (x) => {
    if (isYouTube) return /\/watch\?v=/.test(x.href) || /\/shorts\//.test(x.href);
    if (isReddit) return /\/comments\//.test(x.href) || /\/r\/[^/]+\/comments\//.test(x.href);
    return true;
  };
  const siteScore = (x) => {
    if (isYouTube && /\/watch\?v=/.test(x.href)) return 0;
    if (isYouTube && /\/shorts\//.test(x.href)) return 1;
    if (isReddit && /\/comments\//.test(x.href)) return 0;
    if (x.e.querySelector && x.e.querySelector("h3")) return 0;
    return 2;
  };
  const ytTitle = (e) => {
    const host = e.closest("ytd-video-renderer,ytd-rich-item-renderer,ytd-compact-video-renderer,ytd-grid-video-renderer") || e;
    const title = host.querySelector("#video-title,a#video-title,yt-formatted-string#video-title");
    return (title && (title.title || title.getAttribute("aria-label") || title.innerText || title.textContent)) || e.title || e.getAttribute("aria-label") || e.innerText || "";
  };
  const linkText = (e) => isYouTube ? ytTitle(e) : (e.innerText || e.getAttribute("aria-label") || e.title || "");
  const candidates = [...document.querySelectorAll("a[href]")]
    .filter(visible)
    .map((e) => {
      const r = e.getBoundingClientRect();
      const t = linkText(e).replace(/\s+/g, " ").trim();
      return { e, r, t, n: norm(t), href: e.href };
    })
    .filter((x) => x.t.length >= 8 && x.t.length < 260 && !badHref(x.href) && !badText(x.t) && siteAllowed(x));
  const unique = [];
  const seen = new Set();
  for (const c of candidates.sort((a, b) => (siteScore(a) - siteScore(b)) || (a.r.y - b.r.y) || (a.r.x - b.r.x))) {
    const key = c.href.split("#")[0];
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push({ label: c.t.slice(0, 180), href: c.href });
    if (unique.length >= max) break;
  }
  return unique;
}

function clickTextFn(targetText) {
  const target = (targetText || "").toLowerCase();
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const label = (e) => norm(e.innerText || e.value || e.getAttribute("aria-label") || e.title || "");
  const nodes = [...document.querySelectorAll("a,button,input,[role=button],[role=link],select,summary")];
  const visibleNodes = nodes.filter((e) => visible(e));
  const match = visibleNodes.find((e) => label(e) === target)
    || visibleNodes.find((e) => label(e).startsWith(target))
    || visibleNodes.find((e) => label(e).includes(target));
  if (!match) return "NOT_FOUND";
  match.scrollIntoView({ block: "center", inline: "center" });
  match.click();
  return "CLICKED: " + label(match).slice(0, 120);
}

function clickExactLastFn(targetText) {
  const target = (targetText || "").toLowerCase();
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const label = (e) => norm(e.innerText || e.value || e.getAttribute("aria-label") || e.title || "");
  const nodes = [...document.querySelectorAll("a,button,input,[role=button],[role=link],select,summary")];
  const matches = nodes.filter((e) => visible(e) && label(e) === target);
  if (!matches.length) return "NOT_FOUND";
  const match = matches[matches.length - 1];
  match.scrollIntoView({ block: "center", inline: "center" });
  match.click();
  return "CLICKED: " + label(match).slice(0, 120);
}

function clickVisibleTextFn(targetText) {
  const target = (targetText || "").toLowerCase();
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const label = (e) => norm(e.innerText || e.value || e.getAttribute("aria-label") || e.title || "");
  const nodes = [...document.querySelectorAll("button,[role=button],[role=combobox],input,select,div,span")];
  const matches = nodes
    .filter((e) => visible(e) && label(e) === target)
    .map((e) => {
      const r = e.getBoundingClientRect();
      return { e, r, area: r.width * r.height };
    })
    .sort((a, b) => (a.area - b.area) || (a.r.y - b.r.y) || (a.r.x - b.r.x));
  if (!matches.length) return "NOT_FOUND";
  const match = matches[0].e;
  match.scrollIntoView({ block: "center", inline: "center" });
  const rr = match.getBoundingClientRect();
  const cx = rr.left + rr.width / 2;
  const cy = rr.top + rr.height / 2;
  for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
    match.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy }));
  }
  return "CLICKED: " + label(match).slice(0, 120);
}

function fillFieldFn(targetText, fieldValue) {
  const target = (targetText || "").toLowerCase();
  const value = String(fieldValue || "");
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const label = (e) => norm(e.getAttribute("aria-label") || e.placeholder || e.name || e.id || "");
  const nodes = [...document.querySelectorAll("input,textarea,select")];
  const match = nodes.find((e) => visible(e) && label(e).includes(target));
  if (!match) return "NOT_FOUND";
  match.focus();
  match.value = value;
  match.dispatchEvent(new Event("input", { bubbles: true }));
  match.dispatchEvent(new Event("change", { bubbles: true }));
  return "FILLED: " + (label(match) || target).slice(0, 120);
}

function targetVisibleFn(targetText) {
  const target = (targetText || "").toLowerCase();
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const label = (e) => norm(e.innerText || e.value || e.getAttribute("aria-label") || e.title || "");
  const nodes = [...document.querySelectorAll("a,button,input,[role=button],[role=link],select,summary")];
  return nodes.filter((e) => visible(e)).some((e) => label(e) === target || label(e).startsWith(target) || label(e).includes(target));
}

function clickPriceResultFn(targetText) {
  const target = (targetText || "").toLowerCase();
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const price = (s) => /\b(MYR|RM)\s*[\d,]+/i.test(s || "");
  const bad = (s) => /(filter|currency|privacy|terms|feedback|help center|google account|main menu|change appearance)/i.test(s || "");
  const nodes = [...document.querySelectorAll("a,[role=link],button,[role=button],li,div")];
  let candidates = nodes
    .filter((e) => visible(e))
    .map((e) => {
      const r = e.getBoundingClientRect();
      const t = (e.innerText || e.getAttribute("aria-label") || e.title || "").replace(/\s+/g, " ").trim();
      return { e, r, t, n: norm(t), area: r.width * r.height };
    })
    .filter((x) => x.t.length > 12 && x.t.length < 450 && price(x.t) && !bad(x.t));
  if (!candidates.length) {
    const priceNodes = [...document.querySelectorAll("a,[role=link],button,[role=button],li,div,span")]
      .filter((e) => visible(e) && price(e.innerText || e.textContent || ""));
    for (const node of priceNodes) {
      let p = node;
      let depth = 0;
      while (p && depth < 8) {
        const role = (p.getAttribute && p.getAttribute("role")) || "";
        const tag = (p.tagName || "").toLowerCase();
        const t = (p.innerText || p.textContent || "").replace(/\s+/g, " ").trim();
        if ((tag === "a" || tag === "button" || role === "link" || role === "button" || getComputedStyle(p).cursor === "pointer") && t.length > 12 && t.length < 600 && !bad(t)) {
          const r = p.getBoundingClientRect();
          candidates.push({ e: p, r, t, n: norm(t), area: r.width * r.height });
          break;
        }
        p = p.parentElement;
        depth += 1;
      }
    }
  }
  if (target) candidates = candidates.filter((x) => x.n.includes(target));
  if (!candidates.length) return "NOT_FOUND";
  candidates.sort((a, b) => (a.r.y - b.r.y) || (a.area - b.area) || (a.r.x - b.r.x));
  const chosen = candidates[0];
  chosen.e.scrollIntoView({ block: "center", inline: "center" });
  const link = (chosen.e.closest && chosen.e.closest("a[href]")) || (chosen.e.tagName && chosen.e.tagName.toLowerCase() === "a" ? chosen.e : null);
  if (link && link.href) {
    window.location.assign(link.href);
    return "CLICKED: " + chosen.t.slice(0, 180);
  }
  const rr = chosen.e.getBoundingClientRect();
  const cx = rr.left + rr.width / 2;
  const cy = rr.top + rr.height / 2;
  for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
    chosen.e.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy }));
  }
  return "CLICKED: " + chosen.t.slice(0, 180);
}

function clickSearchResultFn(targetText, rankValue) {
  const target = (targetText || "").toLowerCase();
  const rank = Math.max(1, Math.min(10, Number(rankValue || 1)));
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const pageHost = location.hostname.toLowerCase();
  const isYouTube = /youtube\.com$/.test(pageHost);
  const isReddit = /(^|\.)reddit\.com$/.test(pageHost);
  const badHref = (h) => !h || /google\.[^/]+\/(search|preferences|advanced_search|intl|policies)|accounts\.google|support\.google|javascript:|[?&]entry_point=/i.test(h);
  const badText = (t) => /(cached|similar|translate this page|privacy|terms|settings|tools|feedback|sign in|images|videos|maps|shopping|news|home|shorts|subscriptions|library|history|you|premium)$/i.test(t) || /monthly players/i.test(t);
  const siteAllowed = (x) => {
    if (isYouTube) return /\/watch\?v=/.test(x.href) || /\/shorts\//.test(x.href);
    if (isReddit) return /\/comments\//.test(x.href) || /\/r\/[^/]+\/comments\//.test(x.href);
    return true;
  };
  const siteScore = (x) => {
    if (isYouTube && /\/watch\?v=/.test(x.href)) return 0;
    if (isYouTube && /\/shorts\//.test(x.href)) return 1;
    if (isReddit && /\/comments\//.test(x.href)) return 0;
    if (x.e.querySelector && x.e.querySelector("h3")) return 0;
    return 2;
  };
  const ytTitle = (e) => {
    const host = e.closest("ytd-video-renderer,ytd-rich-item-renderer,ytd-compact-video-renderer,ytd-grid-video-renderer") || e;
    const title = host.querySelector("#video-title,a#video-title,yt-formatted-string#video-title");
    return (title && (title.title || title.getAttribute("aria-label") || title.innerText || title.textContent)) || e.title || e.getAttribute("aria-label") || e.innerText || "";
  };
  const linkText = (e) => isYouTube ? ytTitle(e) : (e.innerText || e.getAttribute("aria-label") || e.title || "");
  const links = [...document.querySelectorAll("a[href]")]
    .filter(visible)
    .map((e) => {
      const r = e.getBoundingClientRect();
      const t = linkText(e).replace(/\s+/g, " ").trim();
      return { e, r, t, n: norm(t), href: e.href };
    })
    .filter((x) => x.t.length >= 8 && x.t.length < 260 && !badHref(x.href) && !badText(x.t) && siteAllowed(x));
  const unique = [];
  const seen = new Set();
  for (const c of links.sort((a, b) => (siteScore(a) - siteScore(b)) || (a.r.y - b.r.y) || (a.r.x - b.r.x))) {
    const key = c.href.split("#")[0];
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(c);
  }
  let candidates = unique.map((x) => ({ ...x, label: x.t, n: norm(x.t) }));
  if (target) candidates = candidates.filter((x) => x.n.includes(target));
  if (candidates.length < rank) return "NOT_FOUND";
  const chosen = candidates[rank - 1];
  // Keep automation inside the Maya tab group. A normal DOM click can honor
  // target=_blank or site handlers and create an ungrouped Chrome tab; direct
  // same-tab navigation preserves the tab's group membership.
  window.location.assign(chosen.href);
  return "CLICKED_RESULT: " + chosen.label.slice(0, 160) + " | " + chosen.href;
}

function dismissReadingOverlayFn() {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const norm = (s) => (s || "").toLowerCase().replace(/\s+/g, " ").trim();
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden";
  };
  const label = (e) => norm(e.innerText || e.value || e.getAttribute("aria-label") || e.title || "");
  const allowed = new Set([
    "close", "×", "x", "no thanks", "not now", "continue reading",
    "got it", "accept cookies", "accept all", "agree", "i agree",
  ]);
  const before = location.href;
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true }));
  window.scrollBy(0, 1);
  return sleep(120).then(() => {
    const nodes = [...document.querySelectorAll("button,[role=button],a,input,summary")].filter(visible);
    const match = nodes.find((e) => allowed.has(label(e)));
    if (match) {
      match.click();
      return sleep(180).then(() => ({
        dismissed: true,
        method: "dismiss_control",
        before,
        after: location.href,
        sameHost: new URL(before).host === location.host,
      }));
    }
    return {
      dismissed: false,
      method: "escape_scroll",
      before,
      after: location.href,
      sameHost: new URL(before).host === location.host,
    };
  });
}

async function executeOnTab(tab, func, args) {
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func,
    args,
  });
  return res.result;
}

function waitForTabComplete(tabId, timeoutMs) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    };
    const listener = (updatedTabId, changeInfo) => {
      if (updatedTabId === tabId && changeInfo.status === "complete") finish();
    };
    const timer = setTimeout(finish, timeoutMs);
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then((tab) => {
      if (tab.status === "complete") finish();
    }).catch(finish);
  });
}

function assertSafeInteraction(tab) {
  if (SENSITIVE_URL.test(tab.url || "")) throw new Error("refused: sensitive page (defense in depth)");
}

async function handle(op, args) {
  if (op === "ping") return { pong: true, groupId, automationWindowId };
  if (op === "ensure_group") {
    const id = await ensureGroup();
    return { groupId: id, windowId: automationWindowId, openedInMayaGroup: id !== null && automationWindowId !== null };
  }
  if (op === "set_status") {
    const id = await ensureGroup();
    await chrome.tabGroups.update(id, { title: GROUP_TITLE, color: GROUP_COLOR });
    return { ok: true };
  }
  if (op === "open_url") {
    const id = await ensureGroup();
    const group = await chrome.tabGroups.get(id);
    const windowId = group.windowId === undefined ? await ensureWindow() : group.windowId;
    await saveAutomationWindowId(windowId);
    const tabs = await chrome.tabs.query({ groupId: id });
    const reusable = tabs.find(isBannerTab);
    const tab = reusable
      ? await chrome.tabs.update(reusable.id, { url: args.url, active: args.activate !== false })
      : await chrome.tabs.create({ url: args.url, active: args.activate !== false, windowId });
    if (!reusable) await chrome.tabs.group({ tabIds: [tab.id], groupId: id });
    await waitForTabComplete(tab.id, args.timeout_ms || 12000);
    let finalTab = await chrome.tabs.get(tab.id).catch(() => tab);
    let overlay = { dismissed: false, method: "", sameHost: true };
    if (!SENSITIVE_URL.test(finalTab.url || "")) {
      overlay = await executeOnTab(finalTab, dismissReadingOverlayFn, []).catch(() => overlay);
      await waitForTabComplete(tab.id, 1200);
      finalTab = await chrome.tabs.get(tab.id).catch(() => finalTab);
      if (overlay && overlay.sameHost === false) throw new Error("overlay dismissal changed page host; stopped for review");
    }
    const finalGroupId = finalTab.groupId === undefined ? -1 : finalTab.groupId;
    const openedInMayaGroup = finalGroupId === id && finalTab.windowId === windowId;
    return {
      tabId: tab.id,
      groupId: id,
      windowId,
      openedInMayaGroup,
      overlayDismissed: !!(overlay && overlay.dismissed),
      overlayMethod: overlay.method || "",
      url: finalTab.url || "",
      title: finalTab.title || ""
    };
  }
  if (op === "page_text") {
    const tab = await targetTab(args);
    const page = await executeOnTab(tab, pageTextFn, [args.max_chars || 4500]);
    return { ...page, ...mayaGroupProofForTab(tab) };
  }
  if (op === "elements") {
    const tab = await targetTab(args);
    return executeOnTab(tab, elementsFn, [args.max_items || 25]);
  }
  if (op === "result_options") {
    const tab = await targetTab(args);
    return { items: await executeOnTab(tab, searchResultOptionsFn, [args.max_items || 8]) };
  }
  if (op === "screenshot") {
    const tab = await targetTab(args);
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
    return { dataUrl };
  }
  if (op === "close_run_tabs") {
    const groups = await allMayaGroupTabs();
    const ids = [];
    const ungroupBeforeClose = [];
    let keptBanner = false;
    for (const row of groups) {
      const tabs = row.tabs || [];
      if (args.keep_banner && !keptBanner && tabs.length) {
        keptBanner = true;
        const keep = tabs.find(isBannerTab) || tabs[0];
        ids.push(...tabs.filter((t) => t.id !== keep.id).map((t) => t.id));
        if (!isBannerTab(keep)) await chrome.tabs.update(keep.id, { url: "about:blank", active: false });
      } else {
        const tabIds = tabs.map((t) => t.id);
        ids.push(...tabIds);
        ungroupBeforeClose.push(...tabIds);
      }
    }
    if (ungroupBeforeClose.length) {
      try { await chrome.tabs.ungroup(ungroupBeforeClose); } catch (e) {}
    }
    if (ids.length) await chrome.tabs.remove(ids);
    if (!args.keep_banner) groupId = null;
    return { closed: ids.length };
  }
  if (op === "click_text") {
    const tab = await targetTab(args);
    assertSafeInteraction(tab);
    return { result: await executeOnTab(tab, clickTextFn, [args.target || ""]) };
  }
  if (op === "click_exact_last") {
    const tab = await targetTab(args);
    assertSafeInteraction(tab);
    return { result: await executeOnTab(tab, clickExactLastFn, [args.target || ""]) };
  }
  if (op === "click_visible") {
    const tab = await targetTab(args);
    assertSafeInteraction(tab);
    return { result: await executeOnTab(tab, clickVisibleTextFn, [args.target || ""]) };
  }
  if (op === "click_price_result") {
    const tab = await targetTab(args);
    assertSafeInteraction(tab);
    return { result: await executeOnTab(tab, clickPriceResultFn, [args.target || ""]) };
  }
  if (op === "click_search_result") {
    const tab = await targetTab(args);
    assertSafeInteraction(tab);
    return { result: await executeOnTab(tab, clickSearchResultFn, [args.target || "", args.rank || 1]) };
  }
  if (op === "target_visible") {
    const tab = await targetTab(args);
    return { visible: await executeOnTab(tab, targetVisibleFn, [args.target || ""]) };
  }
  if (op === "fill_field" || op === "fill") {
    const tab = await targetTab(args);
    assertSafeInteraction(tab);
    return { result: await executeOnTab(tab, fillFieldFn, [args.target || "", args.value || ""]) };
  }
  throw new Error(`unknown op: ${op}`);
}
