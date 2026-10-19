"use strict";

const VIEWS = ["applications", "mappings", "test"];
const NEW_JOB = "__new__";
const SECRET_KEY = "webhookSecret";

const STATUS_LABELS = {
  RECEIVED: "Received",
  PROCESSING: "Processing",
  ASSESSMENT_CREATED: "Assessment created",
  EMAIL_SENT: "Email sent",
  FAILED: "Failed",
};

const DEFAULT_EMAIL_BODY = [
  "Hi {{candidate_name}},",
  "",
  "Thank you for applying for the {{job_title}} role.",
  "",
  "Please complete your assessment here:",
  "{{assessment_url}}",
  "",
  "Good luck!",
  "The Recruitment Team",
].join("\n");

const state = {
  applications: [],
  mappings: [],
  jobs: [],
  assessments: [],
};

const $ = (selector) => document.querySelector(selector);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

function describeError(data, status) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = (e.loc || []).filter((part) => part !== "body").join(".");
        return field ? `${field}: ${e.msg}` : e.msg;
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

async function api(path, { method = "GET", body, headers = {} } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Could not reach the server. Check that it is still running.");
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(describeError(data, response.status));
  return data;
}

// The API returns naive UTC timestamps (no offset), so mark them as UTC before parsing.
function formatDate(iso) {
  if (!iso) return "—";
  const hasZone = /(Z|[+-]\d\d:\d\d)$/.test(iso);
  const date = new Date(hasZone ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function statusBadge(status) {
  const tone = status === "EMAIL_SENT" ? "ok" : status === "FAILED" ? "bad" : "";
  return el("span", { class: `status ${tone}`.trim() }, STATUS_LABELS[status] || status);
}

let noticeTimer;

function showNotice(message, isError = false) {
  clearTimeout(noticeTimer);
  $("#notice-text").textContent = message;
  $("#notice").classList.toggle("error", isError);
  $("#notice").hidden = false;
  if (!isError) noticeTimer = setTimeout(hideNotice, 6000);
}

function hideNotice() {
  clearTimeout(noticeTimer);
  $("#notice").hidden = true;
}

async function withBusy(button, task) {
  button.disabled = true;
  try {
    return await task();
  } finally {
    button.disabled = false;
  }
}

function readSecret() {
  try {
    return sessionStorage.getItem(SECRET_KEY) || "";
  } catch {
    return "";
  }
}

function saveSecret(value) {
  try {
    sessionStorage.setItem(SECRET_KEY, value);
  } catch {
    // Storage unavailable (e.g. private mode) – the field just won't be remembered.
  }
}

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

async function loadAll() {
  const [applications, mappings, jobs, assessments] = await Promise.all([
    api("/applications"),
    api("/mappings"),
    api("/jobs"),
    api("/assessments"),
  ]);
  Object.assign(state, { applications, mappings, jobs, assessments });
  renderApplications();
  renderMappings();
  renderJobOptions();
}

async function reload() {
  try {
    await loadAll();
  } catch (error) {
    showNotice(error.message, true);
  }
}

// ---------------------------------------------------------------------------
// Applications
// ---------------------------------------------------------------------------

function renderApplications() {
  const filter = $("#status-filter").value;
  const rows = filter
    ? state.applications.filter((a) => a.status === filter)
    : state.applications;

  $("#applications-body").replaceChildren(
    ...rows.map((application) =>
      el(
        "tr",
        {},
        el("td", { class: "numeric" }, String(application.id)),
        el("td", {}, application.candidate, el("span", { class: "sub" }, application.email)),
        el("td", {}, application.job),
        el(
          "td",
          {},
          statusBadge(application.status),
          application.error_message &&
            el("span", { class: "sub error-text" }, application.error_message),
        ),
        el("td", { class: "nowrap" }, formatDate(application.created_at)),
        el("td", { class: "nowrap" }, formatDate(application.processed_at)),
        el(
          "td",
          { class: "actions" },
          application.status === "FAILED" &&
            el(
              "button",
              {
                type: "button",
                class: "button small",
                onclick: (event) => retryApplication(application, event.currentTarget),
              },
              "Retry",
            ),
        ),
      ),
    ),
  );

  const empty = $("#applications-empty");
  empty.hidden = rows.length > 0;
  if (state.applications.length === 0) {
    empty.replaceChildren(
      "No applications yet. ",
      el("a", { href: "#test" }, "Send a test application"),
      " to see one here.",
    );
  } else {
    empty.replaceChildren("No applications with this status.");
  }

  const total = state.applications.length;
  $("#applications-count").textContent =
    total === 0 ? "" : filter ? `Showing ${rows.length} of ${total}` : `${total} total`;
}

async function retryApplication(application, button) {
  await withBusy(button, async () => {
    try {
      await api(`/applications/${application.id}/retry`, { method: "POST" });
      showNotice(`Assessment email sent to ${application.candidate}.`);
    } catch (error) {
      showNotice(`Retry failed for application ${application.id}: ${error.message}`, true);
    }
  });
  await reload();
}

// ---------------------------------------------------------------------------
// Mappings
// ---------------------------------------------------------------------------

function renderMappings() {
  const jobsById = new Map(state.jobs.map((job) => [job.id, job]));
  const assessmentsById = new Map(state.assessments.map((a) => [a.id, a]));

  $("#mappings-body").replaceChildren(
    ...state.mappings.map((mapping) => {
      const job = jobsById.get(mapping.job_id);
      const assessment = assessmentsById.get(mapping.assessment_id);
      return el(
        "tr",
        {},
        el(
          "td",
          {},
          job ? job.title : `Job ${mapping.job_id}`,
          job && el("span", { class: "sub" }, job.external_id),
        ),
        el("td", {}, assessment ? assessment.name : `Assessment ${mapping.assessment_id}`),
        el(
          "td",
          {},
          mapping.email_subject,
          el("details", {}, el("summary", {}, "Email body"), el("pre", {}, mapping.email_body)),
        ),
        el(
          "td",
          { class: "actions" },
          el(
            "button",
            {
              type: "button",
              class: "button small",
              onclick: (event) => deactivateMapping(mapping, job, event.currentTarget),
            },
            "Deactivate",
          ),
        ),
      );
    }),
  );
  $("#mappings-empty").hidden = state.mappings.length > 0;
}

function fillSelect(select, options, placeholder) {
  const previous = select.value;
  select.replaceChildren(
    el("option", { value: "" }, placeholder),
    ...options.map(([value, label]) => el("option", { value: String(value) }, label)),
  );
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function renderJobOptions() {
  fillSelect(
    $("#mapping-job"),
    state.jobs.map((job) => [job.id, `${job.title} (${job.external_id})`]),
    "Select a job",
  );
  fillSelect(
    $("#mapping-assessment"),
    state.assessments.map((a) => [a.id, a.name]),
    "Select an assessment",
  );
  fillSelect(
    $("#test-job"),
    [
      ...state.jobs.map((job) => [job.external_id, `${job.title} (${job.external_id})`]),
      [NEW_JOB, "A job that isn't listed…"],
    ],
    "Select a job",
  );
  updateMappingWarning();
  updateNewJobFields();
}

function updateMappingWarning() {
  const jobId = Number($("#mapping-job").value);
  $("#mapping-job-warning").hidden = !state.mappings.some((m) => m.job_id === jobId);
}

async function deactivateMapping(mapping, job, button) {
  const name = job ? job.title : `job ${mapping.job_id}`;
  const confirmed = window.confirm(
    `Deactivate the mapping for ${name}? New applications for this job will fail until another mapping is added.`,
  );
  if (!confirmed) return;

  await withBusy(button, async () => {
    try {
      await api(`/mappings/${mapping.id}`, { method: "DELETE" });
      showNotice(`Mapping for ${name} deactivated.`);
    } catch (error) {
      showNotice(error.message, true);
    }
  });
  await reload();
}

async function submitMapping(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type=submit]");

  await withBusy(button, async () => {
    try {
      await api("/mappings", {
        method: "POST",
        body: {
          job_id: Number($("#mapping-job").value),
          assessment_id: Number($("#mapping-assessment").value),
          email_subject: $("#mapping-subject").value.trim(),
          email_body: $("#mapping-body").value,
        },
      });
      form.reset();
      $("#mapping-body").value = DEFAULT_EMAIL_BODY;
      showNotice("Mapping added.");
      await reload();
    } catch (error) {
      showNotice(error.message, true);
    }
  });
}

// ---------------------------------------------------------------------------
// Test application
// ---------------------------------------------------------------------------

function updateNewJobFields() {
  const isNew = $("#test-job").value === NEW_JOB;
  $("#test-new-job").hidden = !isNew;
  $("#test-job-id").required = isNew;
  $("#test-job-title").required = isNew;
}

function selectedTestJob() {
  const value = $("#test-job").value;
  if (value === NEW_JOB) {
    return { id: $("#test-job-id").value.trim(), title: $("#test-job-title").value.trim() };
  }
  const job = state.jobs.find((j) => j.external_id === value);
  return job ? { id: job.external_id, title: job.title } : null;
}

function showTestResult(result, wasDuplicate) {
  const application = state.applications.find((a) => a.id === result.application_id);
  const box = $("#test-result");
  let message;

  if (wasDuplicate) {
    message = "This candidate had already applied to this job, so nothing new was sent.";
  } else if (result.status === "EMAIL_SENT") {
    message = "The application was recorded and the assessment email was sent.";
  } else if (result.status === "FAILED") {
    message = "The application was recorded, but processing failed.";
  } else {
    message = "The application was recorded.";
  }

  box.replaceChildren(
    el("div", {}, statusBadge(result.status), ` Application ${result.application_id}`),
    el("p", {}, message),
    application && application.error_message
      ? el("p", { class: "sub error-text" }, application.error_message)
      : null,
    el("p", {}, el("a", { href: "#applications" }, "View applications")),
  );
  box.hidden = false;
}

async function submitTest(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  const job = selectedTestJob();
  if (!job) {
    showNotice("Select a job for the application.", true);
    return;
  }

  const secret = $("#test-secret").value;
  saveSecret(secret);
  $("#test-result").hidden = true;

  await withBusy(button, async () => {
    try {
      const knownIds = new Set(state.applications.map((a) => a.id));
      const result = await api("/webhooks/handshake", {
        method: "POST",
        headers: { "X-Webhook-Secret": secret },
        body: {
          candidate_id: $("#test-candidate-id").value.trim(),
          candidate_name: $("#test-name").value.trim(),
          candidate_email: $("#test-email").value.trim(),
          job_id: job.id,
          job_title: job.title,
        },
      });
      hideNotice();
      await reload();
      showTestResult(result, knownIds.has(result.application_id));
    } catch (error) {
      showNotice(error.message, true);
    }
  });
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function showView() {
  const requested = location.hash.slice(1);
  const view = VIEWS.includes(requested) ? requested : VIEWS[0];
  for (const name of VIEWS) {
    $(`#view-${name}`).hidden = name !== view;
  }
  for (const link of document.querySelectorAll(".nav a")) {
    if (link.dataset.view === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------

window.addEventListener("hashchange", showView);
$("#notice-close").addEventListener("click", hideNotice);
$("#refresh").addEventListener("click", (event) => withBusy(event.currentTarget, reload));
$("#status-filter").addEventListener("change", renderApplications);
$("#mapping-job").addEventListener("change", updateMappingWarning);
$("#mapping-form").addEventListener("submit", submitMapping);
$("#test-job").addEventListener("change", updateNewJobFields);
$("#test-form").addEventListener("submit", submitTest);

$("#mapping-body").value = DEFAULT_EMAIL_BODY;
$("#test-secret").value = readSecret();

showView();
reload();
