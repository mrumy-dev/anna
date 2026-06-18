// ANNA Web-UI: fragt /api/state ab und zeichnet die Parkareale.
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

const els = {
  areas: document.getElementById("areas"),
  totalFree: document.getElementById("total-free"),
  modeBadge: document.getElementById("mode-badge"),
  simHint: document.getElementById("sim-hint"),
  simRandom: document.getElementById("sim-random"),
};

// --- Filter ----------------------------------------------------------------
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("is-active"));
    chip.classList.add("is-active");
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

// --- Rendern ---------------------------------------------------------------
function render(state) {
  simMode = state.mode === "simulated";
  els.modeBadge.hidden = !simMode;
  els.simHint.hidden = !simMode;
  els.totalFree.textContent = state.free;

  els.areas.innerHTML = "";
  for (const area of state.areas) {
    els.areas.appendChild(renderArea(area));
  }
  applyFilter();
}

function renderArea(area) {
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
  banner.textContent = "Areal voll – bitte anderes Areal waehlen.";
  card.appendChild(banner);

  const grid = document.createElement("div");
  grid.className = "grid";
  for (const space of area.spaces) {
    grid.appendChild(renderSpace(space));
  }
  card.appendChild(grid);
  return card;
}

function renderSpace(space) {
  const el = document.createElement(simMode ? "button" : "div");
  el.className = "space" + (space.occupied ? " occupied" : "");
  el.dataset.type = space.type;
  el.dataset.id = space.id;
  if (simMode) {
    el.dataset.clickable = "1";
    el.type = "button";
    el.addEventListener("click", () => toggleSpace(space.id));
  }
  el.innerHTML = `
    <span class="space-id">${escapeHtml(space.id)}</span>
    <span class="space-state">${space.occupied ? "Belegt" : "Frei"}</span>
    <span class="space-type">${TYPE_LABELS[space.type] || space.type}</span>`;
  return el;
}

// --- Datenfluss ------------------------------------------------------------
async function refresh() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (res.ok) render(await res.json());
  } catch (err) {
    // Netzwerkfehler still ignorieren; naechster Poll versucht es erneut.
  }
}

async function toggleSpace(id) {
  try {
    const res = await fetch(`/api/sim/toggle/${id}`, { method: "POST" });
    if (res.ok) render(await res.json());
  } catch (err) {
    /* ignore */
  }
}

if (els.simRandom) {
  els.simRandom.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/sim/randomize", { method: "POST" });
      if (res.ok) render(await res.json());
    } catch (err) {
      /* ignore */
    }
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// Start
refresh();
setInterval(refresh, POLL_MS);
