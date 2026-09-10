const $ = (sel) => document.querySelector(sel);

let currentBoard = null;

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

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
        `<div class="count ${cls || ""}"><span>${esc(label)}</span><b>${esc(n)}</b></div>`
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
            `<button class="choice" data-hh="${esc(item.household_id)}" data-choice="${esc(opt.id)}">${esc(opt.label)}</button>`
        )
        .join("");
      return `<article class="card urgent">
        <p class="kicker">${esc(item.program)} · ${esc(item.days_until_drop)} days · ${esc(item.drop_on)}</p>
        <h3>${esc(item.display_name)}</h3>
        <p>${esc(item.question)}</p>
        <p class="why">${esc(item.why_human)}</p>
        <div>${buttons}</div>
      </article>`;
    })
    .join("");
}

function packetCard(p, filed) {
  return `<article class="card ${filed ? "filed" : ""}">
        <p class="kicker">${esc(p.program)} · ${filed ? "filed" : "drafted"}</p>
        <h3>${esc(p.display_name || p.household_id)}</h3>
        <p>${filed ? "Caseworker chose to file. Packet is marked submitted." : "Packet assembled overnight. No decision required."}</p>
        <p><a href="${esc(p.path)}" target="_blank" rel="noreferrer">Open PDF</a></p>
      </article>`;
}

function renderReady(board) {
  const root = $("#ready");
  if (!board.ready.length) {
    root.innerHTML = `<p class="empty">No silent packets yet. Run last night.</p>`;
    return;
  }
  root.innerHTML = board.ready.map((p) => packetCard(p, false)).join("");
}

function renderSubmitted(board) {
  const root = $("#submitted");
  const rows = board.submitted || [];
  if (!rows.length) {
    root.innerHTML = `<p class="empty">Nothing filed yet. Filing is a human act.</p>`;
    return;
  }
  root.innerHTML = rows.map((p) => packetCard(p, true)).join("");
}

function renderTable(board) {
  const body = $("#caseload tbody");
  body.innerHTML = board.caseload
    .map((row) => {
      let overnight = "quiet";
      if (row.pending) overnight = "needs you";
      else if (row.packet) overnight = row.packet.status;
      return `<tr>
        <td>${esc(row.display_name)}</td>
        <td>${esc(row.program)}</td>
        <td>${esc(row.drop_on)}</td>
        <td>${esc(row.days_until_drop)}</td>
        <td class="band ${esc(row.band)}">${esc(row.band.replace("_", " "))}</td>
        <td>${esc(overnight)}</td>
      </tr>`;
    })
    .join("");
}

function renderProof(board) {
  const proof = board.proof;
  const root = $("#proof");
  if (!proof) {
    root.hidden = true;
    return;
  }
  root.hidden = false;
  $("#proof-headline").textContent = proof.headline;
  $("#proof-detail").textContent = proof.detail;
  const bits = [];
  if (proof.days_until_drop != null) bits.push(`${proof.days_until_drop} days until drop`);
  if (proof.source) bits.push(proof.source);
  if (proof.quiet_count != null) bits.push(`${proof.quiet_count} quiet files`);
  if (board.runtime_source) bits.push(board.runtime_source);
  $("#proof-meta").textContent = bits.join(" · ");
}

function paint(board) {
  currentBoard = board;
  $("#desk-date").textContent = board.desk_date;
  $("#model-name").textContent = board.model_name;
  const run = board.last_run;
  $("#last-run").textContent = run && run.run_id ? run.run_id : "not run";
  renderProof(board);
  counts(board);
  renderNeeds(board);
  renderReady(board);
  renderSubmitted(board);
  renderTable(board);
}

let autoNightStarted = false;

async function load() {
  const board = await api("/api/board");
  paint(board);
  const ran = board.last_run && board.last_run.run_id;
  if (ran) {
    setStatus(
      `Night already ran. ${board.counts.needs_you} need you, ${board.counts.quiet} stayed quiet.`
    );
    return;
  }
  if (autoNightStarted) return;
  autoNightStarted = true;
  $("#run-night").disabled = true;
  setStatus("Fraser is already quiet. Catching up last night on AgentCore…");
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
}

$("#run-night").addEventListener("click", async () => {
  if (currentBoard && currentBoard.last_run) {
    const ok = window.confirm(
      "Run last night again? This resets the caseload and spends Bedrock tokens if Nova is on."
    );
    if (!ok) return;
  }
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
