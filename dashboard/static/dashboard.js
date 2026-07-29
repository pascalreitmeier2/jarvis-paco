"use strict";

// ---- helpers ---------------------------------------------------------------
function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") {
        node.addEventListener(k.slice(2), v);
      } else node.setAttribute(k, v);
    }
  }
  for (const c of children || []) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

const PRIO_LABEL = { high: "Hoch", medium: "Mittel", low: "Niedrig" };

// ---- clock -----------------------------------------------------------------
function tickClock() {
  const now = new Date();
  const opts = { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" };
  document.getElementById("clock").textContent = now.toLocaleString("de-DE", opts);
}
setInterval(tickClock, 1000);
tickClock();

// ---- renderers -------------------------------------------------------------
const RENDERERS = {
  email_priority: renderEmailPriority,
  generic: renderGeneric,
};

function renderGeneric(body, data) {
  body.innerHTML = "";
  body.appendChild(el("pre", { class: "generic-json" }, [JSON.stringify(data, null, 2)]));
}

function renderEmailPriority(body, data, section) {
  body.innerHTML = "";

  if (data.status === "not_configured") {
    body.appendChild(notice(
      "Gmail ist noch nicht verbunden",
      data.message +
      " Trage die Werte in die <code>.env</code> ein und lade neu — beim ersten Abruf öffnet sich einmalig das Google-Login.",
      false
    ));
    return;
  }
  if (data.status === "error") {
    body.appendChild(notice("Fehler", escapeHtml(data.message), true));
    return;
  }

  // Summary bar
  const summary = el("div", { class: "summary" });
  const counts = data.counts || {};
  for (const p of ["high", "medium", "low"]) {
    summary.appendChild(el("span", { class: "pill " + p }, [
      el("span", { class: "num" }, [String(counts[p] || 0)]),
      PRIO_LABEL[p],
    ]));
  }
  summary.appendChild(el("span", { class: "pill" }, [
    el("span", { class: "num" }, [String(data.open_todos || 0)]), "offene To-dos",
  ]));
  const engineLabel = data.engine === "claude" ? "KI-Analyse (Claude)"
    : data.engine === "rules" ? "Heuristik (kein API-Key)" : "—";
  summary.appendChild(el("span", { class: "pill engine" }, [engineLabel]));
  body.appendChild(summary);

  // Two columns: emails + to-dos
  const cols = el("div", { class: "email-widget-cols" });

  const emailCol = el("div", {}, [el("p", { class: "col-title" }, ["Priorisierte Mails"])]);
  if (!data.emails || data.emails.length === 0) {
    emailCol.appendChild(el("div", { class: "empty" }, ["Keine Mails für die aktuelle Suche."]));
  } else {
    for (const m of data.emails) emailCol.appendChild(emailRow(m));
  }

  const todoCol = el("div", {}, [el("p", { class: "col-title" }, ["Abgeleitete To-dos"])]);
  if (!data.todos || data.todos.length === 0) {
    todoCol.appendChild(el("div", { class: "empty" }, ["Noch keine To-dos."]));
  } else {
    for (const t of data.todos) todoCol.appendChild(todoRow(t));
  }

  cols.appendChild(emailCol);
  cols.appendChild(todoCol);
  body.appendChild(cols);

  if (section) {
    const meta = section.querySelector(".widget-meta");
    if (meta) meta.textContent = `${data.total} Mails · ${new Date(data.generated_at).toLocaleTimeString("de-DE")}`;
  }
}

function emailRow(m) {
  const subject = el("div", { class: "email-subject" }, [
    el("a", { href: m.gmail_link, target: "_blank", rel: "noopener" }, [m.subject]),
  ]);
  const row1 = el("div", { class: "email-row1" }, [
    el("span", { class: "email-sender" }, [m.sender_name]),
    el("span", { class: "email-date" }, [m.date_display || ""]),
  ]);
  const main = el("div", { class: "email-main" }, [
    row1,
    subject,
    el("div", { class: "email-snippet" }, [m.snippet || ""]),
    m.reason ? el("div", { class: "email-reason" }, [
      el("span", { class: "score-badge" }, [String(m.score)]), " " + m.reason,
    ]) : null,
  ]);
  return el("div", { class: "email" }, [
    el("div", { class: "prio-bar " + m.priority }),
    main,
  ]);
}

function todoRow(t) {
  const check = el("input", {
    type: "checkbox", class: "todo-check",
    onchange: (e) => toggleTodo(t.id, e.target.checked, e.target.closest(".todo")),
  });
  if (t.done) check.checked = true;
  const body = el("div", { class: "todo-body" }, [
    el("div", { class: "todo-text" }, [t.text]),
    el("div", { class: "todo-sub" }, [
      el("span", { class: "todo-dot " + t.priority }),
      el("a", { href: t.gmail_link, target: "_blank", rel: "noopener" }, [t.email_subject]),
    ]),
  ]);
  return el("div", { class: "todo" + (t.done ? " done" : "") }, [check, body]);
}

function notice(title, htmlMsg, isError) {
  return el("div", { class: "notice" + (isError ? " error" : "") }, [
    el("strong", {}, [title]), " ",
    el("span", { html: htmlMsg }),
  ]);
}

// ---- data flow -------------------------------------------------------------
async function toggleTodo(id, done, rowEl) {
  try {
    await fetch("/api/todos/" + encodeURIComponent(id), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done }),
    });
    if (rowEl) rowEl.classList.toggle("done", done);
  } catch (err) {
    console.error("To-do konnte nicht gespeichert werden", err);
  }
}

async function loadWidget(section) {
  const id = section.dataset.widgetId;
  const type = section.dataset.renderType || "generic";
  const body = section.querySelector(".widget-body");
  const refreshBtn = section.querySelector(".widget-refresh");
  if (refreshBtn) refreshBtn.classList.add("spin");

  try {
    const resp = await fetch(`/api/widgets/${id}/data`);
    const data = await resp.json();
    const renderer = RENDERERS[type] || RENDERERS.generic;
    renderer(body, data, section);
  } catch (err) {
    body.innerHTML = "";
    body.appendChild(notice("Fehler", "Widget konnte nicht geladen werden: " + escapeHtml(String(err)), true));
  } finally {
    if (refreshBtn) refreshBtn.classList.remove("spin");
  }
}

function initWidgets() {
  const sections = document.querySelectorAll(".widget");
  sections.forEach((section) => {
    loadWidget(section);

    const btn = section.querySelector(".widget-refresh");
    if (btn) btn.addEventListener("click", () => loadWidget(section));

    const secs = parseInt(section.dataset.refresh || "0", 10);
    if (secs > 0) setInterval(() => loadWidget(section), secs * 1000);
  });

  const refreshAll = document.getElementById("refresh-all");
  if (refreshAll) {
    refreshAll.addEventListener("click", () => sections.forEach(loadWidget));
  }
}

document.addEventListener("DOMContentLoaded", initWidgets);
