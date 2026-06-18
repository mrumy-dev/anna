// ANNA Web-UI: zeigt die Parkareale live an.
// Datenquelle: /api/state (Polling) bzw. /api/stream (Server-Sent-Events),
// dazu /api/reservations + /api/reserve fuer Reservierungen und /api/stats
// fuer die Auslastung. Reines Vanilla-JS, laeuft ohne Build-Kette direkt vom Pi.
"use strict";

const POLL_MS = parseInt(document.body.dataset.poll || "1500", 10);
const TYPE_LABELS = {
  normal: "Normal",
  family: "Familie",
  women: "Frauen",
  disabled: "Behinderte",
};

let currentFilter = "all";
let simMode = false;
let lastState = null;
let reservedSet = new Set();
let sse = null;
let pollTimer = null;

const els = {
  areas: document.getElementById("areas"),
  totalFree: document.getElementById("total-free"),
  modeBadge: document.getElementById("mode-badge"),
  simHint: document.getElementById("sim-hint"),
  simRandom: document.getElementById("sim-random"),
  liveDot: document.getElementById("live-dot"),
  offline: document.getElementById("offline"),
  stats: document.getElementById("stats"),
  statsBody: document.getElementById("stats-body"),
};

// --- Filter ----------------------------------------------------------------
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((c) => {
      c.classList.remove("is-active");
      c.setAttribute("aria-pressed", "false");
    });
    chip.classList.add("is-active");
    chip.setAttribute("aria-pressed", "true");
    currentFilter = chip.dataset.filter;
    applyFilter();
  });
});

function applyFilter() {
  document.querySelectorAll(".space").forEach((space) => {
    const match = currentFilter === "all" || space.dataset.type === currentFilter;
    space.classList.toggle("dim", !match);
  });
}

// --- Verbindungsanzeige ----------------------------------------------------
function setConn(status) {
  // status: "live" | "down"
  els.liveDot.className = "live-dot " + (status === "live" ? "live" : "down");
  els.offline.hidden = status !== "down";
}

// --- Rendern ---------------------------------------------------------------
function render(state) {
  lastState = state;
  simMode = state.mode === "simulated";
  els.modeBadge.hidden = !simMode;
  els.simHint.hidden = !simMode;
  els.totalFree.textContent = state.free;

  els.areas.innerHTML = "";
  for (const area of state.areas) {
    els.areas.appendChild(renderArea(area, state.areas));
  }
  applyFilter();
}

function renderArea(area, allAreas) {
  const card = document.createElement("section");
  card.className = "area" + (area.is_full ? " full" : "");

  const head = document.createElement("div");
  head.className = "area-head";
  head.innerHTML = `
    <div>
      <h2 class="area-name">${escapeHtml(area.name)}</h2>
      <p class="area-free"><strong>${area.free}</strong> von ${area.total} frei</p>
    </div>`;
  if (area.maps_url) {
    const route = document.createElement("a");
    route.className = "route-btn";
    route.href = area.maps_url;
    route.target = "_blank";
    route.rel = "noopener";
    route.textContent = "Route";
    head.appendChild(route);
  }
  card.appendChild(head);

  const banner = document.createElement("p");
  banner.className = "full-banner";
  banner.textContent = fullBannerText(area, allAreas);
  card.appendChild(banner);

  const grid = document.createElement("div");
  grid.className = "grid";
  for (const space of area.spaces) {
    grid.appendChild(renderSpace(space));
  }
  card.appendChild(grid);
  return card;
}

function fullBannerText(area, allAreas) {
  const alt = allAreas.find((a) => a.id !== area.id && a.free > 0);
  if (alt) {
    return `Areal voll – ${alt.name} hat noch ${alt.free} frei.`;
  }
  return "Areal voll – zurzeit kein anderes Areal frei.";
}

function renderSpace(space) {
  const reserved = reservedSet.has(space.id) && !space.occupied;
  const el = document.createElement("div");
  el.className = "space"
    + (space.occupied ? " occupied" : "")
    + (reserved ? " reserved" : "");
  el.dataset.type = space.type;
  el.dataset.id = space.id;

  // Im Simulationsmodus schaltet ein Klick auf die Kachel belegt/frei.
  if (simMode) {
    el.dataset.clickable = "1";
    el.setAttribute("role", "button");
    el.tabIndex = 0;
    el.addEventListener("click", () => toggleSpace(space.id));
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleSpace(space.id);
      }
    });
  }

  const stateLabel = space.occupied ? "Belegt" : reserved ? "Reserviert" : "Frei";
  el.innerHTML = `
    <span class="space-id">${escapeHtml(space.id)}</span>
    <span class="space-state">${stateLabel}</span>
    <span class="space-type">${TYPE_LABELS[space.type] || space.type}</span>`;

  // Reservierungs-Steuerung: freie Felder reservieren, reservierte freigeben.
  if (!space.occupied) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "resv-btn" + (reserved ? " cancel" : "");
    btn.textContent = reserved ? "✕" : "+";
    btn.title = reserved ? "Reservierung aufheben" : "Feld reservieren";
    btn.setAttribute("aria-label", btn.title);
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      reserved ? cancelReserve(space.id) : reserve(space.id);
    });
    el.appendChild(btn);
  }
  return el;
}

// --- Live-Datenfluss: SSE mit Polling-Fallback -----------------------------
function startLive() {
  if (!("EventSource" in window)) {
    startPolling();
    return;
  }
  try {
    sse = new EventSource("/api/stream");
    sse.onmessage = (e) => {
      setConn("live");
      try { render(JSON.parse(e.data)); } catch (err) { /* ignore */ }
    };
    sse.onerror = () => {
      if (sse) { sse.close(); sse = null; }
      setConn("down");
      startPolling();
    };
  } catch (err) {
    startPolling();
  }
}

function startPolling() {
  if (pollTimer) return;
  refreshState();
  pollTimer = setInterval(refreshState, POLL_MS);
}

async function refreshState() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (res.ok) { setConn("live"); render(await res.json()); }
    else setConn("down");
  } catch (err) {
    setConn("down");
  }
}

// --- Simulationssteuerung --------------------------------------------------
async function toggleSpace(id) {
  try {
    const res = await fetch(`/api/sim/toggle/${id}`, { method: "POST" });
    if (res.ok) render(await res.json());
  } catch (err) { /* ignore */ }
}

if (els.simRandom) {
  els.simRandom.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/sim/randomize", { method: "POST" });
      if (res.ok) render(await res.json());
    } catch (err) { /* ignore */ }
  });
}

// --- Reservierung ----------------------------------------------------------
async function refreshReservations() {
  try {
    const res = await fetch("/api/reservations", { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      reservedSet = new Set((data.reservations || []).map((r) => r.id));
      if (lastState) render(lastState);
    }
  } catch (err) { /* ignore */ }
}

async function reserve(id) {
  try {
    const res = await fetch(`/api/reserve/${id}`, { method: "POST" });
    if (res.ok) applyReservationResponse(await res.json());
  } catch (err) { /* ignore */ }
}

async function cancelReserve(id) {
  try {
    const res = await fetch(`/api/reserve/${id}`, { method: "DELETE" });
    if (res.ok) applyReservationResponse(await res.json());
  } catch (err) { /* ignore */ }
}

function applyReservationResponse(data) {
  reservedSet = new Set((data.reservations || []).map((r) => r.id));
  if (lastState) render(lastState);
}

// --- Auslastung ------------------------------------------------------------
async function refreshStats() {
  try {
    const res = await fetch("/api/stats", { cache: "no-store" });
    if (res.ok) renderStats(await res.json());
  } catch (err) { /* ignore */ }
}

function renderStats(s) {
  els.stats.hidden = false;
  const totalSpaces = lastState ? lastState.total : null;
  let html = statCard("Gesamt", s.avg_occupied, s.peak_occupied, totalSpaces);
  for (const a of s.areas) {
    html += statCard(a.name, a.avg_occupied, a.peak_occupied, a.total);
  }
  els.statsBody.innerHTML = html;
}

function statCard(name, avg, peak, total) {
  const peakText = total != null ? `${peak} / ${total}` : `${peak}`;
  return `<div class="stat">
    <div class="stat-name">${escapeHtml(name)}</div>
    <div class="stat-row">
      <span>Schnitt belegt: <b>${avg}</b></span>
      <span>Spitze: <b>${peakText}</b></span>
    </div>
  </div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// --- Start -----------------------------------------------------------------
refreshReservations();
startLive();
refreshStats();
setInterval(refreshReservations, 4000);
setInterval(refreshStats, 4000);
