/* Phase 2.5 read-only surfaces: Proof, Automations, Memory Audit, Artifact QA. */
"use strict";

(() => {
  const token = new URLSearchParams(location.search).get("token") ||
    sessionStorage.getItem("maya-ui-token") || "";
  const q = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const api = (p) => fetch(p + (p.includes("?") ? "&" : "?") + "token=" +
    encodeURIComponent(token)).then((r) => { if (!r.ok) throw r; return r.json(); });
  const cut = (s, n = 110) => String(s || "").length > n ? String(s).slice(0, n - 1) + "…" : String(s || "");
  const state = (ok) => ok ? "ok" : "bad";
  const when = (ts) => ts ? String(ts).replace("T", " ").slice(5, 16) : "—";

  function row(title, sub, end = "", cls = "") {
    return `<div class="lrow ${cls}"><span class="d" style="background:var(--ink3)"></span>
      <div style="min-width:0"><div class="nm">${esc(title)}</div><div class="sb">${esc(sub)}</div></div>
      <span class="end">${end}</span></div>`;
  }

  function renderMemoryAudit(data) {
    const el = q("memoryAudit"); if (!el) return;
    const events = data.events || [];
    el.innerHTML = events.length ? events.map((e) =>
      row(e.event_type, `${e.subject_key || "memory"} · ${cut(e.content_preview, 72)} · ${when(e.created_at)}`,
        `<span class="state idle">${esc(e.status_after || e.status_before || "event")}</span>`)).join("")
      : `<div class="empty">no audit events yet</div>`;
  }

  function renderArtifactDetail(data) {
    const s = q("artifactSessions"), r = q("artifactReviews"); if (!s || !r) return;
    s.innerHTML = (data.sessions || []).slice(0, 8).map((a) =>
      row(a.short_name || a.title || a.artifact_type,
        `${a.artifact_type} · rev ${a.revision ?? 0} · expires ${when(a.expires_at)}`,
        `<span class="state ${a.status === "active" ? "ok" : "idle"}">${esc(a.status)}</span>`)).join("")
      || `<div class="empty">no active artifact sessions</div>`;
    r.innerHTML = (data.reviews || []).slice(0, 8).map((a) =>
      row(`${a.artifact_type} · ${a.topic || "artifact"}`,
        `${cut(a.review_text, 150)} · ${when(a.created_at)}`,
        `<span class="state ${state(!!a.passed)}">${a.passed ? "pass" : "reject"}</span>`)).join("")
      || `<div class="empty">no QA reviews yet</div>`;
  }

  function renderAutomations(data) {
    const stats = q("autoStats"), routines = q("routineRows"), weekly = q("weeklyRows");
    if (!stats || !routines || !weekly) return;
    const c = data.counts || {};
    stats.innerHTML = [
      ["Routines", `${c.active || 0}/${c.routines || 0} active`],
      ["Weekly failures", `${c.weekly_failures || 0}`],
      ["Nightly failures", `${c.nightly_failures || 0}`],
    ].map(([a, b]) => `<div class="statbox"><b>${esc(b)}</b><span>${esc(a)}</span></div>`).join("");
    routines.innerHTML = (data.routines || []).map((x) =>
      row(x.name, `${x.kind} · ${x.channel} · ${x.local_time} · ${x.autonomy_mode}`,
        `<span class="state ${x.active ? "ok" : "idle"}">${x.active ? "active" : "off"}</span>`)).join("")
      || `<div class="empty">no routines registered</div>`;
    weekly.innerHTML = [...(data.weekly_memory || []), ...(data.nightly_consolidation || [])].slice(0, 10).map((x) =>
      row(x.run_key, `${x.trigger_source || "nightly"} · saved ${x.canonical_saved ?? x.saved ?? 0} · rejected ${x.canonical_rejected ?? x.rejected ?? 0}`,
        `<span class="state ${x.status === "completed" ? "ok" : x.status === "failed" ? "bad" : "wait"}">${esc(x.status)}</span>`)).join("")
      || `<div class="empty">no memory automation runs yet</div>`;
  }

  function bar(label, score) {
    const n = Number(score || 0), cls = n >= 85 ? "good" : n >= 70 ? "warn" : "bad";
    return `<div class="pbar ${cls}"><div class="t"><span>${esc(label)}</span><b>${n.toFixed(1)}%</b></div>
      <div class="meter"><i style="width:${Math.max(0, Math.min(100, n))}%"></i></div></div>`;
  }

  function renderProof(data) {
    const score = q("proofScore"), label = q("proofLabel"), bars = q("proofBars");
    if (!score || !label || !bars) return;
    score.textContent = `${Number(data.overall?.score || 0).toFixed(1)}%`;
    label.textContent = data.overall?.label || "proof boundary";
    bars.innerHTML = [
      bar("Deterministic", data.deterministic?.score),
      bar("Browser live", data.browser?.summary?.live_score),
      bar("Demo evidence", data.demos?.passed ? 100 : 0),
    ].join("");
    q("demoRows").innerHTML = (data.demos?.items || []).map((d) =>
      row(d.name, d.log || "latest demo log", `<span class="state ${state(d.passed)}">${d.passed ? "pass" : "fail"}</span>`)).join("")
      || `<div class="empty">no demo evidence</div>`;
    q("liveRows").innerHTML = (data.live?.items || []).slice(0, 10).map((x) =>
      row(x.title || x.id, x.evidence || x.notes || "live proof item",
        `<span class="state ${x.status === "passed" ? "ok" : x.status === "failed" ? "bad" : "wait"}">${esc(x.status)}</span>`)).join("")
      || `<div class="empty">no live proof rows</div>`;
    q("riskRows").innerHTML = (data.recent_failures || []).map((x) =>
      row(x.name, `${x.source} · ${x.detail}`, `<span class="state wait">watch</span>`)).join("")
      || `<div class="empty">no recent risks in latest proof logs</div>`;
  }

  async function bootExtra() {
    try {
      const [audit, detail, auto, proof] = await Promise.all([
        api("/api/memory/audit?limit=35"), api("/api/artifacts/detail?limit=20"),
        api("/api/automations"), api("/api/proof"),
      ]);
      renderMemoryAudit(audit); renderArtifactDetail(detail); renderAutomations(auto); renderProof(proof);
    } catch {
      ["memoryAudit", "artifactSessions", "artifactReviews", "routineRows", "weeklyRows", "riskRows"]
        .forEach((id) => { const el = q(id); if (el) el.innerHTML = `<div class="empty">surface unavailable</div>`; });
    }
  }

  bootExtra();
  setInterval(bootExtra, 45000);
})();
