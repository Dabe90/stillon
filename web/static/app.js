const $ = (sel) => document.querySelector(sel);

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

function setStatus(text) {
  $("#status").textContent = text;
}

function counts(board) {
  const c = board.counts;
  $("#counts").innerHTML = [
    ["Caseload", c.caseload],
    ["Quiet", c.quiet],
    ["Needs you", c.needs_you, "needs"],
    ["Ready", c.ready, "ready"],
    ["Dropped", c.dropped],
  ]
    .map(
      ([label, n, cls]) =>
        `<div class="count ${cls || ""}"><span>${label}</span><b>${n}</b></div>`
    )
    .join("");
}

function renderNeeds(board) {
  const root = $("#needs-you");
  if (!board.needs_you.length) {
    root.innerHTML = `<p class="empty">Nobody needs you. That is the point.</p>`;
    return;
  }
  root.innerHTML = board.needs_you
    .map((item) => {
      const buttons = (item.options || [])
        .map(
          (opt) =>
            `<button class="choice" data-hh="${item.household_id}" data-choice="${opt.id}">${opt.label}</button>`
        )
        .join("");
      return `<article class="card urgent">
        <p class="kicker">${item.program} · ${item.days_until_drop} days · ${item.drop_on}</p>
        <h3>${item.display_name}</h3>
        <p>${item.question}</p>
        <p class="why">${item.why_human}</p>
        <div>${buttons}</div>
      </article>`;
    })
    .join("");
}

function renderReady(board) {
  const root = $("#ready");
  if (!board.ready.length) {
    root.innerHTML = `<p class="empty">No silent packets yet. Run last night.</p>`;
    return;
  }
  root.innerHTML = board.ready
    .map(
      (p) => `<article class="card">
        <p class="kicker">${p.program} · drafted</p>
        <h3>${p.display_name || p.household_id}</h3>
        <p>Packet assembled overnight. No decision required.</p>
        <p><a href="${p.path}" target="_blank" rel="noreferrer">Open PDF</a></p>
      </article>`
    )
    .join("");
}

function renderTable(board) {
  const body = $("#caseload tbody");
  body.innerHTML = board.caseload
    .map((row) => {
      let overnight = "quiet";
      if (row.pending) overnight = "needs you";
      else if (row.packet) overnight = row.packet.status;
      return `<tr>
        <td>${row.display_name}</td>
        <td>${row.program}</td>
        <td>${row.drop_on}</td>
        <td>${row.days_until_drop}</td>
        <td class="band ${row.band}">${row.band.replace("_", " ")}</td>
        <td>${overnight}</td>
      </tr>`;
    })
    .join("");
}

function paint(board) {
  $("#desk-date").textContent = board.desk_date;
  $("#model-name").textContent = board.model_name;
  counts(board);
  renderNeeds(board);
  renderReady(board);
  renderTable(board);
}

async function load() {
  const board = await api("/api/board");
  paint(board);
}

$("#run-night").addEventListener("click", async () => {
  $("#run-night").disabled = true;
  setStatus("Night desk is working the caseload…");
  try {
    const data = await api("/api/night", { method: "POST" });
    paint(data.board);
    setStatus(
      `Night run ${data.run.run_id}: ${data.run.needs_you} need you, ${data.run.ready} packets ready, ${data.run.quiet} left asleep.`
    );
  } catch (err) {
    setStatus(err.message);
  } finally {
    $("#run-night").disabled = false;
  }
});

$("#reset").addEventListener("click", async () => {
  const board = await api("/api/reset", { method: "POST" });
  paint(board);
  setStatus("Caseload reset to Wednesday morning, 9 September 2026.");
});

document.body.addEventListener("click", async (event) => {
  const btn = event.target.closest("button.choice");
  if (!btn) return;
  btn.disabled = true;
  setStatus("Resuming the paused Strands agent…");
  try {
    const data = await api(`/api/decide/${btn.dataset.hh}`, {
      method: "POST",
      body: JSON.stringify({ choice: btn.dataset.choice }),
    });
    paint(data.board);
    setStatus("Decision recorded. The agent finished the packet where it was safe to.");
  } catch (err) {
    setStatus(err.message);
  }
});

load().catch((err) => setStatus(err.message));
