// ANNA Sensor-Diagnose: zeigt Rohpegel und Beschaltung je Parkfeld.
//
// Ziel dieser Seite ist eine einzige Frage: Kommt das Sensorsignal ueberhaupt
// am Raspberry Pi an? Deshalb steht der ROHE Pegel gleichberechtigt neben der
// Auswertung "belegt/frei" - und ein Zaehler fuer Pegelwechsel daneben.
"use strict";

const REFRESH_MS = 700;
const canWrite = document.body.dataset.write === "1";

const els = {
  rows: document.getElementById("diag-rows"),
  mode: document.getElementById("mode-badge"),
  simWarning: document.getElementById("sim-warning"),
  layoutFile: document.getElementById("layout-file"),
  numbering: document.getElementById("numbering"),
  writeState: document.getElementById("write-state"),
  updated: document.getElementById("updated"),
  scanBtn: document.getElementById("scan-btn"),
  scanResult: document.getElementById("scan-result"),
};

let spaceIds = [];
let numbering = "bcm";

// --- Laufende Aktualisierung ----------------------------------------------
async function refresh() {
  try {
    const res = await fetch("/api/diagnostics", { cache: "no-store" });
    if (!res.ok) return;
    render(await res.json());
  } catch (err) {
    els.updated.textContent = "keine Verbindung";
  }
}

function render(data) {
  numbering = data.numbering || "bcm";
  spaceIds = data.spaces.map((s) => s.space_id);

  els.mode.textContent = data.mode === "gpio" ? "GPIO (echte Sensoren)" : "Simulation";
  els.simWarning.hidden = data.mode === "gpio";
  els.layoutFile.textContent = data.layout_file;
  els.numbering.textContent = numbering;
  els.writeState.textContent = data.write_enabled ? "frei (ANNA_DIAG=1)" : "gesperrt";
  els.updated.textContent = "aktualisiert " + new Date().toLocaleTimeString("de-CH");

  els.rows.innerHTML = data.spaces.map(rowHtml).join("")
    || '<tr><td colspan="8" class="muted">Keine Parkfelder konfiguriert.</td></tr>';

  if (canWrite) {
    els.rows.querySelectorAll("[data-invert]").forEach((btn) => {
      btn.addEventListener("click", () => assign(btn.dataset.invert, {
        invert: btn.dataset.value === "1",
      }));
    });
  }
}

function rowHtml(s) {
  const pinText = s.pin === null || s.pin === undefined
    ? '<span class="muted">kein Pin</span>'
    : `<span class="mono">GPIO${s.pin}</span>`
      + (s.board_pin ? `<span class="row-note">Header-Pin ${s.board_pin}</span>` : "");

  const raw = s.raw === null || s.raw === undefined
    ? '<span class="muted">–</span>'
    : s.raw === 1
      ? '<span class="chip-state chip-high">HIGH · 3,3 V</span>'
      : '<span class="chip-state chip-low">LOW · GND</span>';

  const verdict = !s.ok
    ? '<span class="chip-state chip-err">Fehler</span>'
    : s.occupied
      ? '<span class="chip-state chip-busy">Belegt</span>'
      : '<span class="chip-state chip-free">Frei</span>';

  const changes = `<span class="changes-num ${s.changes ? "changes-some" : "changes-zero"}">`
    + `${s.changes}</span>`
    + (s.last_change_s !== null && s.last_change_s !== undefined
      ? `<span class="row-note">vor ${s.last_change_s} s</span>`
      : '<span class="row-note">nie</span>');

  const wiring = `<span class="mono">pull_up=${s.pull_up}</span>`
    + `<span class="row-note">invert=${s.invert}</span>`;

  // Hinweise nur zeigen, wenn wirklich etwas verdaechtig ist. Sobald ein Pin
  // nachweislich wechselt, ist die Verdrahtung bewiesen - dann waeren
  // Nummerierungs-Hinweise nur noch Laerm.
  let hint = "";
  if (!s.ok) {
    hint = `<span class="row-hint">${escapeHtml(s.error || "Sensor nicht verfügbar")}</span>`;
  } else if (!s.changes) {
    hint = '<span class="row-warn">Noch kein Pegelwechsel – Auto auf- und abstellen.</span>'
      + (s.hint ? `<span class="row-note">${escapeHtml(s.hint)}</span>` : "");
  }

  const actions = canWrite
    ? `<div class="cell-actions">
         <button class="btn small secondary" type="button"
                 data-invert="${escapeHtml(s.space_id)}" data-value="${s.invert ? 0 : 1}">
           invert ${s.invert ? "aus" : "an"}
         </button>
       </div>`
    : '<span class="muted">gesperrt</span>';

  return `<tr>
    <td class="field-id">${escapeHtml(s.space_id)}${hint}</td>
    <td>${pinText}</td>
    <td>${raw}</td>
    <td>${verdict}</td>
    <td>${changes}</td>
    <td>${ledCell(s)}</td>
    <td>${wiring}</td>
    <td>${actions}</td>
  </tr>`;
}

// Status-LEDs: zeigt an, was das Backend gerade ansteuert - und an welchen
// Pins. Beim Verdrahten laesst sich damit Feld fuer Feld gegenpruefen.
function ledCell(s) {
  if (s.led_green_pin === null && s.led_red_pin === null) {
    return '<span class="muted">–</span>';
  }
  const led = s.led || {};
  const dot = (on, colour) =>
    `<span class="led-dot led-${colour}${on ? " on" : ""}"></span>`;
  const pins = [
    s.led_green_pin === null ? null : `gruen GPIO${s.led_green_pin}`,
    s.led_red_pin === null ? null : `rot GPIO${s.led_red_pin}`,
  ].filter(Boolean).join(" · ");

  return `${dot(led.green, "green")}${dot(led.red, "red")}`
    + `<span class="row-note">${escapeHtml(pins)}</span>`
    + (led.error ? `<span class="row-hint">${escapeHtml(led.error)}</span>` : "");
}

// --- Pin-Suche -------------------------------------------------------------
els.scanBtn.addEventListener("click", async () => {
  els.scanBtn.disabled = true;
  els.scanBtn.textContent = "Suche läuft – jetzt Auto umstellen …";
  els.scanResult.innerHTML = "";
  try {
    const res = await fetch("/api/diag/scan?seconds=6", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      els.scanResult.innerHTML = `<p class="warn">${escapeHtml(data.error || "Fehler")}</p>`;
      return;
    }
    renderScan(data.pins || []);
  } catch (err) {
    els.scanResult.innerHTML = '<p class="warn">Suche fehlgeschlagen.</p>';
  } finally {
    els.scanBtn.disabled = false;
    els.scanBtn.textContent = "Suche starten (6 s)";
  }
});

function renderScan(pins) {
  const moved = pins.filter((p) => p.changes > 0);
  if (!moved.length) {
    els.scanResult.innerHTML = `<p class="scan-empty">
      Kein einziger Pin hat sich bewegt. Das Signal erreicht den Pi nicht:
      Verdrahtung, gemeinsame Masse (GND) oder Sensortyp prüfen.
      Wurde während der Suche wirklich ein Auto umgestellt?</p>`;
    return;
  }

  const options = spaceIds.map((id) =>
    `<option value="${escapeHtml(id)}">${escapeHtml(id)}</option>`).join("");

  els.scanResult.innerHTML = `<div class="table-scroll"><table class="diag-table">
    <thead><tr>
      <th>Pin</th><th>Wechsel</th><th>Von → Nach</th><th>Aktuell zugeordnet</th><th>Aktion</th>
    </tr></thead>
    <tbody>${moved.map((p) => `<tr class="scan-hit">
      <td><span class="mono">GPIO${p.pin}</span>
          <span class="row-note">Header-Pin ${p.board_pin ?? "?"}</span></td>
      <td><span class="changes-num changes-some">${p.changes}</span></td>
      <td class="mono">${p.start ?? "?"} → ${p.end ?? "?"}</td>
      <td>${p.assigned_to ? escapeHtml(p.assigned_to) : '<span class="muted">frei</span>'}</td>
      <td>${canWrite ? `<div class="cell-actions">
            <select class="sel" data-pin="${p.pin}" data-board="${p.board_pin ?? ""}">${options}</select>
            <button class="btn small" type="button" data-assign="${p.pin}">zuweisen</button>
          </div>` : '<span class="muted">gesperrt</span>'}</td>
    </tr>`).join("")}</tbody></table></div>`;

  if (!canWrite) return;
  els.scanResult.querySelectorAll("[data-assign]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = btn.closest("tr");
      const sel = row.querySelector("select");
      // In "board"-Nummerierung muss die physische Nummer gespeichert werden,
      // sonst liest das Backend spaeter einen anderen Pin.
      const value = numbering === "board"
        ? Number(sel.dataset.board)
        : Number(sel.dataset.pin);
      assign(sel.value, { gpio_pin: value });
    });
  });
}

// --- Zuordnung schreiben ---------------------------------------------------
async function assign(spaceId, payload) {
  try {
    const res = await fetch(`/api/diag/assign/${encodeURIComponent(spaceId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      alert("Fehler: " + (data.error || res.status));
      return;
    }
    refresh();
  } catch (err) {
    alert("Speichern fehlgeschlagen.");
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// --- Start -----------------------------------------------------------------
refresh();
setInterval(refresh, REFRESH_MS);
