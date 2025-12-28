const STORAGE_KEY = "dinq_gateway_playground_v1";

const apiBaseInput = document.getElementById("apiBase");
const tokenInput = document.getElementById("token");
const includeTokenInCurlInput = document.getElementById("includeTokenInCurl");
const debugModeInput = document.getElementById("debugMode");
const saveSettingsButton = document.getElementById("saveSettings");
const clearSettingsButton = document.getElementById("clearSettings");

const contentInput = document.getElementById("content");
const cardsInput = document.getElementById("cards");
const omitCardsInput = document.getElementById("omitCards");
const modeSelect = document.getElementById("mode");
const freeformInput = document.getElementById("freeform");
const forceRefreshInput = document.getElementById("forceRefresh");
const idempotencyKeyInput = document.getElementById("idempotencyKey");
const genIdempotencyKeyButton = document.getElementById("genIdempotencyKey");
const createButton = document.getElementById("create");
const createAndStreamButton = document.getElementById("createAndStream");
const copyCurlButton = document.getElementById("copyCurl");
const saveScreenshotButton = document.getElementById("saveScreenshot");
const loadMockButton = document.getElementById("loadMock");

const candidatesPanel = document.getElementById("candidatesPanel");
const candidatesMessageEl = document.getElementById("candidatesMessage");
const candidatesEl = document.getElementById("candidates");

const jobIdInput = document.getElementById("jobId");
const afterSeqInput = document.getElementById("afterSeq");
const fetchStatusButton = document.getElementById("fetchStatus");
const streamLastButton = document.getElementById("streamLast");
const streamFromStartButton = document.getElementById("streamFromStart");
const streamAtSeqButton = document.getElementById("streamAtSeq");
const stopButton = document.getElementById("stop");
const clearLogButton = document.getElementById("clearLog");

const logEl = document.getElementById("log");
const cardsContainer = document.getElementById("cardsContainer");
const jobStatusEl = document.getElementById("jobStatus");
const lastEventEl = document.getElementById("lastEvent");
const lastSeqEl = document.getElementById("lastSeq");
const nextAfterEl = document.getElementById("nextAfter");
const tabButtons = Array.from(document.querySelectorAll(".tab"));
const recentJobsEl = document.getElementById("recentJobs");

let abortController = null;
let currentJobId = "";
let lastSeq = 0;
let currentSource = "scholar";
let eventsHistory = [];
const cardState = new Map();
let recentJobs = [];

const defaultCardsBySource = {
  scholar: "profile,metrics,papers,citations,coauthors,role_model,news,level,summary",
  github: "profile,activity,repos,role_model,roast,summary",
  linkedin: "profile,skills,career,role_model,money,roast,summary",
};
const cardsBySource = { ...defaultCardsBySource };

const MAX_EVENT_HISTORY = 500;

const defaultContentBySource = {
  scholar: "Christopher D Manning",
  github: "torvalds",
  linkedin: "Chris Dixon",
};

const MOCK_DATA = {
  github: {
    profile: {
      name: "The Octocat",
      login: "octocat",
      bio: "A great octopus masquerading as a cat",
      company: "GitHub",
      location: "San Francisco",
      followers: 8000,
      following: 9,
      public_repos: 50,
      public_gists: 2,
      blog: "https://github.blog",
      created_at: "2011-01-25",
    },
    activity: {
      overview: {
        work_experience: 10,
        stars: 8000,
        issues: 150,
        pull_requests: 300,
        repositories: 50,
        additions: 50000,
        deletions: 20000,
        active_days: 240,
      },
      activity: [
        { type: "PullRequest", repo: "octocat/Hello-World", title: "Improve README", created_at: "2024-05-02" },
        { type: "IssueComment", repo: "octocat/Spoon-Knife", title: "Review feedback", created_at: "2024-04-21" },
      ],
      code_contribution: {
        total: 70000,
        languages: { Python: 55, Go: 30, JavaScript: 15 },
      },
    },
    repos: {
      feature_project: {
        name: "Hello-World",
        description: "My first repository on GitHub!",
        language: "Python",
        stargazers_count: 8000,
        forks_count: 1200,
      },
      top_projects: [
        { name: "Hello-World", stargazers_count: 8000 },
        { name: "Spoon-Knife", stargazers_count: 3400 },
        { name: "linguist", stargazers_count: 1200 },
      ],
      most_valuable_pull_request: {
        title: "Optimize parser performance",
        repository: "owner/repo",
        merged_at: "2024-03-10",
      },
    },
    role_model: {
      name: "Linus Torvalds",
      institution: "Linux Foundation",
      similarity_reason: "Strong open-source leadership with high-impact systems work.",
    },
    roast: { roast: "With 8000 stars, even your cat meme repos are legendary." },
    summary: {
      valuation_and_level: { level: "L5", salary_range: "$150k - $220k", total_compensation: "$200k - $350k" },
      description: "Strong open-source contributor with high-impact repos.",
    },
  },
  linkedin: {
    profile: {
      name: "Chris Dixon",
      headline: "Partner at a16z",
      location: "San Francisco Bay Area",
      about: "Investor focused on crypto, marketplaces, and developer platforms.",
      personal_tags: ["Investor", "Web3", "Product"],
      skills: ["Product Strategy", "Investing", "Platform Growth", "Web3"],
      work_experience: [
        { title: "Partner", company: "a16z", dates: "2013 - Present" },
        { title: "Co-founder", company: "SiteAdvisor", dates: "2005 - 2006" },
      ],
      education: [
        { school: "Harvard University", degree: "BA", field: "Philosophy" },
      ],
    },
    skills: {
      industry_knowledge: ["Marketplaces", "Crypto", "Developer Platforms"],
      tools_technologies: ["Product Strategy", "Network Effects", "Platform Growth"],
      interpersonal_skills: ["Executive Communication", "Mentorship"],
      language: ["English"],
      original_skills: [{ title: "Investing" }, { title: "Product Management" }],
    },
    career: {
      work_experience: [
        { title: "Partner", company: "a16z", dates: "2013 - Present" },
        { title: "Co-founder", company: "SiteAdvisor", dates: "2005 - 2006" },
      ],
      education: [
        { school: "Harvard University", degree: "BA", field: "Philosophy" },
      ],
      work_experience_summary: "20+ years in product and investing across tech and crypto.",
    },
    money: {
      salary_range: "$350k - $500k",
      market_level: "Executive",
      confidence: "medium",
      currency: "USD",
    },
    role_model: {
      name: "Marc Andreessen",
      institution: "a16z",
      similarity_reason: "Visionary investor and product builder with platform focus.",
    },
    roast: { roast: "Your portfolio is so bullish it needs a seatbelt." },
    summary: {
      about: "Investor focused on crypto, marketplaces, and developer platforms.",
      personal_tags: ["Investor", "Web3", "Product"],
    },
  },
};

function appendLog(line) {
  logEl.textContent += `${line}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function clearLog() {
  logEl.textContent = "";
  eventsHistory = [];
}

function resetCards() {
  cardsContainer.innerHTML = "";
  cardState.clear();
}

function resetRunState() {
  if (abortController) {
    try {
      abortController.abort();
    } catch {
      // ignore
    }
  }
  hideCandidates();
  clearLog();
  resetCards();
  abortController = null;
  currentJobId = "";
  lastSeq = 0;
  jobIdInput.value = "";
  jobStatusEl.textContent = "idle";
  lastEventEl.textContent = "-";
  lastSeqEl.textContent = "0";
  nextAfterEl.textContent = "0";
  afterSeqInput.value = "";
  stopButton.disabled = true;
}

function normalizeBaseUrl(raw) {
  const trimmed = String(raw || "").trim();
  if (!trimmed) return "http://127.0.0.1:8001";
  return trimmed.replace(/\/+$/, "");
}

function normalizeBearerToken(raw) {
  const trimmed = String(raw || "").trim();
  if (!trimmed) return "";
  if (/^bearer\s+/i.test(trimmed)) return trimmed;
  return `Bearer ${trimmed}`;
}

function joinUrl(base, path) {
  const b = normalizeBaseUrl(base);
  return `${b}${path}`;
}

function setActiveSource(source) {
  currentSource = source;
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.source === source);
  });

  if (cardsBySource[source]) {
    cardsInput.value = cardsBySource[source];
  }

  // Update placeholder/preset for content (only if empty).
  const placeholder = defaultContentBySource[source] || "";
  contentInput.placeholder = placeholder
    ? `e.g. ${placeholder}`
    : "input.content";
  if (!contentInput.value.trim() && placeholder) {
    contentInput.value = placeholder;
  }

  persistSettings();
}

function setOmitCardsUI() {
  const omit = !!omitCardsInput.checked;
  cardsInput.disabled = omit;
  cardsInput.classList.toggle("disabled", omit);
  persistSettings();
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed.apiBase) apiBaseInput.value = String(parsed.apiBase);
    if (parsed.token) tokenInput.value = String(parsed.token);
    if (parsed.includeTokenInCurl !== undefined) includeTokenInCurlInput.checked = !!parsed.includeTokenInCurl;
    if (parsed.debugMode !== undefined && debugModeInput) debugModeInput.checked = !!parsed.debugMode;
    if (parsed.cardsBySource && typeof parsed.cardsBySource === "object") {
      Object.assign(cardsBySource, parsed.cardsBySource);
    }
    if (parsed.currentSource) currentSource = String(parsed.currentSource);
    if (parsed.omitCards !== undefined) omitCardsInput.checked = !!parsed.omitCards;
    if (Array.isArray(parsed.recentJobs)) recentJobs = parsed.recentJobs.slice(0, 15);
  } catch (err) {
    // ignore
  }
}

function persistSettings() {
  try {
    const payload = {
      apiBase: normalizeBaseUrl(apiBaseInput.value),
      token: tokenInput.value.trim(),
      includeTokenInCurl: !!includeTokenInCurlInput.checked,
      debugMode: !!(debugModeInput && debugModeInput.checked),
      cardsBySource: { ...cardsBySource },
      currentSource,
      omitCards: !!omitCardsInput.checked,
      recentJobs: Array.isArray(recentJobs) ? recentJobs.slice(0, 15) : [],
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (err) {
    // ignore
  }
}

function clearSettings() {
  localStorage.removeItem(STORAGE_KEY);
  apiBaseInput.value = "http://127.0.0.1:8001";
  tokenInput.value = "";
  includeTokenInCurlInput.checked = false;
  if (debugModeInput) debugModeInput.checked = false;
  Object.assign(cardsBySource, defaultCardsBySource);
  omitCardsInput.checked = true;
  recentJobs = [];
  persistSettings();
  setOmitCardsUI();
  setActiveSource("scholar");
}

function applyDebugMode() {
  const enabled = !!(debugModeInput && debugModeInput.checked);
  document.body.classList.toggle("debug", enabled);
}

function renderRecentJobs() {
  if (!recentJobsEl) return;
  recentJobsEl.innerHTML = "";
  if (!Array.isArray(recentJobs) || recentJobs.length === 0) {
    recentJobsEl.appendChild(createElement("div", "empty", "No recent jobs yet."));
    return;
  }

  recentJobs.forEach((item) => {
    const row = createElement("div", "recent-job");
    const left = createElement("div", "recent-job-left");
    left.appendChild(createElement("div", "recent-job-id", item.job_id));
    left.appendChild(createElement("div", "recent-job-meta", `${item.source || "-"} · ${item.input || "-"}`));
    row.appendChild(left);

    const actions = createElement("div", "recent-job-actions");
    const loadBtn = createElement("button", "secondary", "Load");
    loadBtn.addEventListener("click", async () => {
      if (item.source) setActiveSource(item.source);
      if (item.input) contentInput.value = item.input;
      jobIdInput.value = item.job_id;
      currentJobId = item.job_id;
      await fetchJobStatus();
    });
    const streamBtn = createElement("button", "", "Stream");
    streamBtn.addEventListener("click", async () => {
      if (item.source) setActiveSource(item.source);
      jobIdInput.value = item.job_id;
      currentJobId = item.job_id;
      await startStream(0);
    });
    actions.appendChild(loadBtn);
    actions.appendChild(streamBtn);
    row.appendChild(actions);
    recentJobsEl.appendChild(row);
  });
}

function rememberJob(jobId, { source, input } = {}) {
  const id = String(jobId || "").trim();
  if (!id) return;
  const entry = {
    job_id: id,
    source: String(source || currentSource || "").trim() || null,
    input: String(input || "").trim() || null,
    ts: Date.now(),
  };
  recentJobs = [entry, ...(Array.isArray(recentJobs) ? recentJobs.filter((j) => j.job_id !== id) : [])].slice(0, 15);
  renderRecentJobs();
  persistSettings();
}

function createElement(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function getOrCreateCard(cardType) {
  if (cardState.has(cardType)) return cardState.get(cardType);

  const card = createElement("div", "card");
  const header = createElement("div", "card-header");
  const title = createElement("h3", "title", cardType);
  const status = createElement("span", "status-pill", "pending");

  header.appendChild(title);
  header.appendChild(status);

  const meta = createElement("div", "meta", "pending");
  const progressBlock = createElement("div", "progress-block");
  const progressLabel = createElement("div", "progress-label", "progress");
  const progressText = createElement("div", "progress-text", "-");
  progressBlock.appendChild(progressLabel);
  progressBlock.appendChild(progressText);
  const content = createElement("div", "content");

  const streamBlock = createElement("div", "stream-block");
  const streamLabel = createElement("div", "stream-label", "stream delta");
  const streamPre = createElement("pre", "stream");
  streamBlock.appendChild(streamLabel);
  streamBlock.appendChild(streamPre);

  const details = document.createElement("details");
  details.className = "raw";
  const summary = document.createElement("summary");
  summary.textContent = "Raw JSON";
  const finalPre = createElement("pre", "final");
  details.appendChild(summary);
  details.appendChild(finalPre);

  card.appendChild(header);
  card.appendChild(meta);
  card.appendChild(progressBlock);
  card.appendChild(content);
  card.appendChild(streamBlock);
  card.appendChild(details);

  cardsContainer.appendChild(card);

  const state = {
    card,
    meta,
    status,
    content,
    progressText,
    streamPre,
    finalPre,
    output: { data: null, stream: {} },
    streamSpec: null,
    cacheMeta: null,
    currentStatus: "pending",
    data: null,
    lastProgress: "",
  };
  cardState.set(cardType, state);
  return state;
}

function updateCardStatus(cardType, status) {
  const state = getOrCreateCard(cardType);
  state.currentStatus = String(status || "unknown");
  renderCardMeta(cardType);
  state.status.textContent = status;
  state.status.dataset.state = status;
}

function renderCardMeta(cardType) {
  const state = getOrCreateCard(cardType);
  const parts = [];
  const status = String(state.currentStatus || state.meta.textContent || "").trim();
  if (status) parts.push(status);
  const cache = state.cacheMeta && typeof state.cacheMeta === "object" ? state.cacheMeta : null;
  if (cache && cache.hit) {
    const stale = cache.stale ? "stale" : "fresh";
    const asOf = cache.as_of ? `as_of=${cache.as_of}` : null;
    parts.push(["cache", stale, asOf].filter(Boolean).join(" · "));
  }
  state.meta.textContent = parts.join(" · ") || "-";
}

function setProgress(cardType, step, message) {
  const state = getOrCreateCard(cardType);
  const cleanStep = String(step || "").trim();
  const cleanMsg = String(message || "").trim();
  if (!cleanStep && !cleanMsg) return;
  const ts = new Date().toLocaleTimeString();
  const line = cleanStep ? `${cleanStep}: ${cleanMsg}` : cleanMsg;
  const rendered = `[${ts}] ${line}`;
  state.lastProgress = rendered;
  state.progressText.textContent = rendered;
}

function setFinal(cardType, payload) {
  const state = getOrCreateCard(cardType);
  const normalized = normalizeOutputEnvelope(payload);
  const output = normalized || wrapAsOutputEnvelope(payload);
  if (!normalized) {
    appendLog(`warn: invalid output envelope for card=${cardType}; wrapped as data`);
  }
  // Never lose accumulated stream deltas (snapshot may be behind SSE, or vice versa).
  const prev = state.output || wrapAsOutputEnvelope(null);
  output.stream = mergeStreams(prev.stream, output.stream);
  if ((output.data === null || output.data === undefined) && prev.data !== null && prev.data !== undefined) {
    output.data = prev.data;
  }
  state.output = output;
  state.data = output.data;
  renderCardContent(cardType, output, state.content, state.streamSpec);
  renderStream(cardType);
  state.finalPre.textContent = JSON.stringify(output, null, 2);
}

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function isEmptyObject(value) {
  return isPlainObject(value) && Object.keys(value).length === 0;
}

function wrapAsOutputEnvelope(data) {
  return { data: data === undefined ? null : data, stream: {} };
}

function normalizeOutputEnvelope(value) {
  if (!isPlainObject(value)) return null;
  if (!("data" in value) && !("stream" in value)) return null;
  const stream = isPlainObject(value.stream) ? value.stream : {};
  return { data: value.data, stream };
}

function isInternalCard(cardType, internalFlag) {
  if (internalFlag === true) return true;
  const ct = String(cardType || "");
  return ct === "full_report" || ct.startsWith("resource.");
}

function mergeStreams(existing, incoming) {
  const base = isPlainObject(existing) ? existing : {};
  const next = isPlainObject(incoming) ? incoming : {};
  const out = { ...base };
  Object.entries(next).forEach(([field, entry]) => {
    if (!isPlainObject(entry)) return;
    const prevEntry = isPlainObject(out[field]) ? out[field] : {};
    const prevSections = isPlainObject(prevEntry.sections) ? prevEntry.sections : {};
    const nextSections = isPlainObject(entry.sections) ? entry.sections : {};
    out[field] = {
      ...prevEntry,
      ...entry,
      sections: { ...prevSections, ...nextSections },
    };
  });
  return out;
}

function applyCardDelta(cardType, deltaPayload) {
  const state = getOrCreateCard(cardType);
  if (!state.output) state.output = { data: null, stream: {} };

  const field = String(deltaPayload?.field || "content");
  const section = String(deltaPayload?.section || "main");
  const format = String(deltaPayload?.format || "markdown");
  const delta = String(deltaPayload?.delta || "");
  if (!delta) return;

  const stream = isPlainObject(state.output.stream) ? state.output.stream : {};
  const entry = isPlainObject(stream[field]) ? stream[field] : {};
  const sections = isPlainObject(entry.sections) ? entry.sections : {};
  const prev = String(sections[section] || "");
  sections[section] = prev + delta;
  stream[field] = { ...entry, format: entry.format || format, sections };
  state.output.stream = stream;
  renderStream(cardType);
  // For sectioned cards (e.g., summary), re-render content from stream.
  renderCardContent(cardType, state.output, state.content, state.streamSpec);
}

function renderStream(cardType) {
  const state = cardState.get(cardType);
  if (!state) return;
  const output = state.output || { data: null, stream: {} };
  const stream = isPlainObject(output.stream) ? output.stream : {};
  const spec = state.streamSpec || null;

  const lines = [];
  const fields = Object.keys(stream);
  if (!fields.length) {
    state.streamPre.textContent = "";
    return;
  }

  fields.forEach((field) => {
    const entry = stream[field];
    if (!isPlainObject(entry)) return;
    const fmt = entry.format ? ` (${entry.format})` : "";
    lines.push(`${field}${fmt}`);
    const sections = isPlainObject(entry.sections) ? entry.sections : {};
    const order = Array.isArray(spec?.sections) && spec?.field === field ? spec.sections : Object.keys(sections);
    order.forEach((name) => {
      lines.push(`\n[${name}]`);
      lines.push(String(sections[name] || ""));
    });
    lines.push("\n");
  });

  state.streamPre.textContent = lines.join("\n").trim() + "\n";
}

function isTerminalJobStatus(status) {
  const s = String(status || "").toLowerCase();
  return s === "completed" || s === "partial" || s === "failed" || s === "cancelled";
}

function refreshSyntheticFullReport({ terminal } = {}) {
  const state = cardState.get("full_report");
  if (!state) return;

  // Only synthesize when server did not provide a full_report payload (it's intentionally empty in dinq).
  if (!(state.data === null || state.data === undefined || isEmptyObject(state.data) || state.data?.schema === "synthetic_full_report_v1")) {
    return;
  }

  const report = buildSyntheticFullReport();
  const hasAnyCards = report?.by_card && Object.keys(report.by_card).length > 0;
  if (!terminal && !hasAnyCards) return;

  setFinal("full_report", wrapAsOutputEnvelope(report));
}

function addRow(container, label, value) {
  const row = createElement("div", "row");
  const key = createElement("div", "key", label);
  const val = createElement("div", "value");
  val.textContent = value === undefined || value === null || value === "" ? "-" : String(value);
  row.appendChild(key);
  row.appendChild(val);
  container.appendChild(row);
}

function summarizeList(items, key, limit = 5) {
  if (!Array.isArray(items)) return "-";
  const sliced = items.slice(0, limit);
  const values = sliced.map((item) => (key ? item?.[key] : item)).filter(Boolean);
  return values.length ? values.join(", ") : "-";
}

function renderKeyValueList(container, payload, keys) {
  let added = 0;
  keys.forEach((key) => {
    if (payload && payload[key] !== undefined) {
      addRow(container, key, payload[key]);
      added += 1;
    }
  });
  return added;
}

function renderListBlock(container, title, items) {
  if (!Array.isArray(items) || items.length === 0) return;
  const block = createElement("div", "list-block");
  block.appendChild(createElement("div", "list-title", title));
  const list = createElement("ul", "list");
  items.forEach((item) => {
    const li = createElement("li", "list-item", item);
    list.appendChild(li);
  });
  block.appendChild(list);
  container.appendChild(block);
}

function stripSectionMarkers(text) {
  return String(text || "").replace(/<!--\\s*section:[^>]*-->/gi, "").trim();
}

function renderSectionBlocks(container, title, sections, order) {
  const block = createElement("div", "sectioned");
  block.appendChild(createElement("div", "sectioned-title", title));
  const list = createElement("div", "sectioned-body");
  const keys = Array.isArray(order) && order.length ? order : Object.keys(sections || {});
  keys.forEach((key) => {
    const sec = createElement("div", "section");
    sec.appendChild(createElement("div", "section-title", key));
    sec.appendChild(createElement("pre", "section-text", String(sections?.[key] || "").trim()));
    list.appendChild(sec);
  });
  block.appendChild(list);
  container.appendChild(block);
}

function renderCardContent(cardType, output, container, streamSpec) {
  container.innerHTML = "";

  const payload = output?.data;
  const stream = isPlainObject(output?.stream) ? output.stream : {};
  const specField = typeof streamSpec?.field === "string" && streamSpec.field.trim() ? streamSpec.field.trim() : null;
  const specOrder = Array.isArray(streamSpec?.sections) ? streamSpec.sections : null;

  // Prefer streaming text (even before card.completed sets output.data).
  if (specField) {
    const entry = stream[specField];
    const sections = isPlainObject(entry?.sections) ? entry.sections : null;
    if (sections) {
      const keys = Object.keys(sections);
      const order = specOrder && specOrder.length ? specOrder : keys;
      if (order.length > 1) {
        renderSectionBlocks(container, specField, sections, order);
      } else {
        const only = order[0] || keys[0] || "main";
        container.appendChild(createElement("div", "summary-text", String(sections[only] || "").trim() || "-"));
      }
      return;
    }
  }

  // Snapshot fallback: if we have stream content but no spec, render the first available field.
  const streamFields = Object.keys(stream || {});
  if (streamFields.length) {
    const fallbackField = streamFields[0];
    const entry = stream[fallbackField];
    const sections = isPlainObject(entry?.sections) ? entry.sections : null;
    if (sections) {
      const order = Object.keys(sections);
      if (order.length > 1) {
        renderSectionBlocks(container, fallbackField, sections, order);
      } else {
        const only = order[0] || "main";
        container.appendChild(createElement("div", "summary-text", String(sections[only] || "").trim() || "-"));
      }
      return;
    }
  }

  if (cardType === "summary") {
    if (payload?.critical_evaluation) {
      container.appendChild(createElement("div", "summary-text", stripSectionMarkers(payload.critical_evaluation) || "-"));
      return;
    }
    if (payload?.description || payload?.valuation_and_level) {
      if (payload.valuation_and_level && typeof payload.valuation_and_level === "object") {
        addRow(container, "level", payload.valuation_and_level.level);
        addRow(container, "salary_range", payload.valuation_and_level.salary_range);
        addRow(container, "total_compensation", payload.valuation_and_level.total_compensation);
      } else {
        addRow(container, "valuation_and_level", payload.valuation_and_level || "-");
      }
      addRow(container, "description", payload.description || "-");
      return;
    }
    if (payload?.about || payload?.personal_tags) {
      addRow(container, "about", payload.about || "-");
      addRow(container, "personal_tags", Array.isArray(payload.personal_tags) ? payload.personal_tags.join(", ") : payload.personal_tags);
      return;
    }
  }

  if (!payload || (isPlainObject(payload) && Object.keys(payload).length === 0)) {
    container.appendChild(createElement("div", "empty", "No data"));
    return;
  }

  if (cardType === "roast") {
    container.appendChild(createElement("div", "summary-text", payload.roast || "-"));
    return;
  }

  if (cardType === "news") {
    addRow(container, "title", payload.news || "-");
    addRow(container, "date", payload.date || "-");
    addRow(container, "description", payload.description || "-");
    addRow(container, "url", payload.url || "-");
    return;
  }

  if (cardType === "profile") {
    // Scholar profile
    addRow(container, "name", payload.name || payload.full_name);
    addRow(container, "headline", payload.headline);
    addRow(container, "affiliation", payload.affiliation || payload.institution || payload.company);
    addRow(container, "location", payload.location);
    addRow(container, "email", payload.email);
    addRow(container, "scholar_id", payload.scholar_id);
    addRow(container, "research_fields", (payload.research_fields || payload.fields || []).join(", "));
    addRow(container, "h_index", payload.h_index);
    addRow(container, "total_citations", payload.total_citations);

    // GitHub profile
    addRow(container, "login", payload.login || payload.username);
    addRow(container, "bio", payload.bio);
    addRow(container, "blog", payload.blog);
    addRow(container, "followers", payload.followers);
    addRow(container, "following", payload.following);
    addRow(container, "public_repos", payload.public_repos);
    addRow(container, "public_gists", payload.public_gists);
    addRow(container, "created_at", payload.created_at);
    addRow(container, "about", payload.about);
    addRow(container, "personal_tags", Array.isArray(payload.personal_tags) ? payload.personal_tags.join(", ") : payload.personal_tags);
    addRow(container, "linkedin_url", payload.linkedin_url);
    return;
  }

  if (cardType === "metrics") {
    addRow(container, "total_papers", payload.total_papers);
    addRow(container, "first_author_papers", payload.first_author_papers);
    addRow(container, "first_author_citations", payload.first_author_citations);
    addRow(container, "top_tier_papers", payload.top_tier_papers);
    addRow(container, "last_author_papers", payload.last_author_papers);
    if (payload.citation_stats) {
      addRow(container, "avg_citations", payload.citation_stats.avg_citations);
      addRow(container, "median_citations", payload.citation_stats.median_citations);
    }
    return;
  }

  if (cardType === "papers") {
    addRow(container, "most_cited", payload.most_cited_paper?.title || "-");
    addRow(container, "most_cited_citations", payload.most_cited_paper?.citations || "-");
    addRow(container, "paper_of_year", payload.paper_of_year?.title || "-");
    addRow(container, "top_tier_count", payload.top_tier_publications?.conferences?.length || 0);
    return;
  }

  if (cardType === "citations") {
    addRow(container, "total_citations", payload.total_citations);
    addRow(container, "citations_5y", payload.citations_5y);
    addRow(container, "h_index", payload.h_index);
    addRow(container, "h_index_5y", payload.h_index_5y);
    return;
  }

  if (cardType === "activity" || cardType === "stats") {
    const overview = payload.overview || {};
    if (typeof overview === "string") {
      addRow(container, "overview", overview);
    } else {
      renderKeyValueList(container, overview, [
        "work_experience",
        "total_prs",
        "total_issues",
        "total_reviews",
        "total_contributions",
        "stars",
        "issues",
        "pull_requests",
        "repositories",
        "additions",
        "deletions",
        "active_days",
      ]);
    }
    addRow(container, "activity_count", Array.isArray(payload.activity) ? payload.activity.length : "-");
    addRow(container, "code_contribution_total", payload.code_contribution?.total);
    if (payload.code_contribution?.languages && typeof payload.code_contribution.languages === "object") {
      const entries = Object.entries(payload.code_contribution.languages).sort((a, b) => b[1] - a[1]);
      renderListBlock(
        container,
        "Top languages",
        entries.slice(0, 5).map(([lang, pct]) => `${lang} ${pct}%`)
      );
    }
    renderListBlock(
      container,
      "Recent activity",
      Array.isArray(payload.activity)
        ? payload.activity.slice(0, 5).map((item) => item?.title || item?.repo || item?.type || JSON.stringify(item))
        : []
    );
    return;
  }

  if (cardType === "repos") {
    const feature = payload.feature_project || {};
    addRow(container, "feature_project", feature.name || feature.title || "-");
    addRow(container, "feature_desc", feature.description);
    addRow(container, "feature_language", feature.language);
    addRow(container, "feature_stars", feature.stargazers_count || feature.stars || feature.stargazerCount);
    addRow(container, "feature_forks", feature.forks_count || feature.forks);
    addRow(container, "feature_tags", Array.isArray(feature.tags) ? feature.tags.join(", ") : feature.tags);

    addRow(container, "top_projects_count", Array.isArray(payload.top_projects) ? payload.top_projects.length : "-");
    renderListBlock(
      container,
      "Top projects",
      Array.isArray(payload.top_projects)
        ? payload.top_projects.slice(0, 6).map((repo) => {
            const repoObj = repo?.repository || repo;
            const name = repoObj?.name || repoObj?.full_name || repoObj?.nameWithOwner || "-";
            const stars = repoObj?.stargazers_count || repoObj?.stars || repoObj?.stargazerCount;
            const language = repoObj?.language || repoObj?.primaryLanguage?.name || "";
            const prCount = repo?.pull_requests || repo?.pullRequests;
            const suffix = [language ? `${language}` : null, stars ? `★${stars}` : null].filter(Boolean).join(" ");
            const prSuffix = prCount ? `PRs:${prCount}` : null;
            const tail = [suffix || null, prSuffix].filter(Boolean).join(" · ");
            return tail ? `${name} · ${tail}` : name;
          })
        : []
    );

    const pr = payload.most_valuable_pull_request || {};
    addRow(container, "best_pr", pr.title || pr.name || "-");
    addRow(container, "best_pr_repo", pr.repo || pr.repository);
    addRow(container, "best_pr_merged", pr.merged_at);
    addRow(container, "best_pr_impact", pr.impact || pr.reason);
    addRow(container, "best_pr_url", pr.url);
    return;
  }

  if (cardType === "skills") {
    if (Array.isArray(payload)) {
      addRow(container, "skills", payload.slice(0, 12).join(", "));
      return;
    }
    if (payload && typeof payload === "object") {
      renderListBlock(container, "Industry knowledge", payload.industry_knowledge || []);
      renderListBlock(container, "Tools & technologies", payload.tools_technologies || []);
      renderListBlock(container, "Interpersonal skills", payload.interpersonal_skills || []);
      renderListBlock(container, "Languages", payload.language || []);

      if (Array.isArray(payload.original_skills)) {
        renderListBlock(
          container,
          "Original skills",
          payload.original_skills.slice(0, 10).map((skill) => skill?.title || skill?.name || JSON.stringify(skill))
        );
      }
      if (Array.isArray(payload.original_languages)) {
        renderListBlock(
          container,
          "Original languages",
          payload.original_languages.slice(0, 8).map((lang) => lang?.title || lang?.name || JSON.stringify(lang))
        );
      }

      const added = renderKeyValueList(container, payload, ["summary", "strengths", "gaps"]);
      if (added) return;
    }
    addRow(container, "skills", summarizeList(payload?.skills || payload?.items, "name"));
    return;
  }

  if (cardType === "career") {
    addRow(container, "work_experience_count", Array.isArray(payload.work_experience) ? payload.work_experience.length : "-");
    addRow(container, "education_count", Array.isArray(payload.education) ? payload.education.length : "-");
    addRow(container, "career", payload.career || "-");
    addRow(container, "work_experience_summary", payload.work_experience_summary || "-");
    addRow(container, "education_summary", payload.education_summary || "-");
    renderListBlock(
      container,
      "Work experience",
      Array.isArray(payload.work_experience)
        ? payload.work_experience.slice(0, 5).map((job) => {
            const title = job?.title || job?.position || job?.role || "-";
            const company = job?.company || job?.organization || job?.companyName || "-";
            const dates = job?.dates || job?.duration || job?.dateRange || "";
            return dates ? `${title} @ ${company} (${dates})` : `${title} @ ${company}`;
          })
        : []
    );
    renderListBlock(
      container,
      "Education",
      Array.isArray(payload.education)
        ? payload.education.slice(0, 4).map((edu) => {
            const school = edu?.school || edu?.institution || "-";
            const degree = edu?.degree || edu?.level || "";
            const field = edu?.field || edu?.major || "";
            const parts = [school, degree, field].filter(Boolean);
            return parts.join(" · ");
          })
        : []
    );
    return;
  }

  if (cardType === "money") {
    const count = renderKeyValueList(container, payload, ["salary_range", "compensation", "market_level", "total_compensation", "confidence", "currency"]);
    if (!count) {
      addRow(container, "analysis", payload.analysis || "-");
    }
    return;
  }

  if (cardType === "coauthors") {
    addRow(container, "total_coauthors", payload.total_coauthors);
    const names = (payload.top_coauthors || []).map((c) => c.name).slice(0, 5).join(", ");
    addRow(container, "top_coauthors", names || "-");
    return;
  }

  if (cardType === "role_model") {
    addRow(container, "name", payload.name);
    addRow(container, "institution", payload.institution);
    addRow(container, "achievement", payload.achievement);
    addRow(container, "reason", payload.similarity_reason);
    addRow(container, "photo_url", payload.photo_url);
    return;
  }

  if (cardType === "level") {
    addRow(container, "level_us", payload.level_us);
    addRow(container, "level_cn", payload.level_cn);
    addRow(container, "earnings", payload.earnings);
    addRow(container, "years", payload.years_of_experience?.years);
    return;
  }

  const added = renderKeyValueList(container, payload, ["name", "title", "headline", "location", "company", "login", "followers", "public_repos"]);
  if (!added) {
    const fallback = createElement("div", "summary-text", "See raw JSON below.");
    container.appendChild(fallback);
  }
}

function updateSeq(seq) {
  if (!seq) return;
  const next = Number(seq);
  if (Number.isNaN(next)) return;
  if (next > lastSeq) {
    lastSeq = next;
    lastSeqEl.textContent = String(lastSeq);
    nextAfterEl.textContent = String(lastSeq);
  }
}

function handleEvent(eventObj) {
  const eventType = eventObj.event_type || "";
  lastEventEl.textContent = eventType;
  updateSeq(eventObj.payload?.seq);

  if (eventType === "job.started") {
    const jobId = eventObj.payload?.job_id || "";
    if (jobId) {
      currentJobId = jobId;
      if (!jobIdInput.value) jobIdInput.value = jobId;
    }
    jobStatusEl.textContent = "running";
  }

  if (eventType === "job.completed") {
    jobStatusEl.textContent = eventObj.payload?.status || "completed";
  }

  if (eventType === "job.failed") {
    jobStatusEl.textContent = eventObj.payload?.status || "failed";
  }

  if (eventType === "card.started") {
    const cardType = eventObj.payload?.card || "unknown";
    if (isInternalCard(cardType, eventObj.payload?.internal)) return;
    updateCardStatus(cardType, "running");
    const state = getOrCreateCard(cardType);
    if (eventObj.payload?.stream && typeof eventObj.payload.stream === "object") {
      state.streamSpec = eventObj.payload.stream;
    }
    if (!state.lastProgress) setProgress(cardType, "started", "running");
  }

  if (eventType === "card.progress") {
    const cardType = eventObj.payload?.card || "unknown";
    if (isInternalCard(cardType, eventObj.payload?.internal)) return;
    setProgress(cardType, eventObj.payload?.step, eventObj.payload?.message);
  }

  if (eventType === "card.prefill") {
    const cardType = eventObj.payload?.card || "unknown";
    if (isInternalCard(cardType, eventObj.payload?.internal)) return;
    updateCardStatus(cardType, "prefill");
    const state = getOrCreateCard(cardType);
    if (eventObj.payload?.cache) state.cacheMeta = eventObj.payload.cache;
    renderCardMeta(cardType);
    setFinal(cardType, eventObj.payload?.payload || {});
  }

  if (eventType === "card.delta") {
    const cardType = eventObj.payload?.card || "unknown";
    if (isInternalCard(cardType, eventObj.payload?.internal)) return;
    applyCardDelta(cardType, eventObj.payload);
  }

  if (eventType === "card.completed") {
    const cardType = eventObj.payload?.card || "unknown";
    if (isInternalCard(cardType, eventObj.payload?.internal)) return;
    updateCardStatus(cardType, "completed");
    const state = getOrCreateCard(cardType);
    if (eventObj.payload?.cache) state.cacheMeta = eventObj.payload.cache;
    renderCardMeta(cardType);
    let payload = eventObj.payload?.payload || {};
    setFinal(cardType, payload);
  }

  if (eventType === "card.failed") {
    const cardType = eventObj.payload?.card || "unknown";
    if (isInternalCard(cardType, eventObj.payload?.internal)) return;
    updateCardStatus(cardType, "failed");
    setFinal(cardType, wrapAsOutputEnvelope({ error: eventObj.payload?.error || "unknown error" }));
  }
}

function buildSyntheticFullReport() {
  const byCard = {};
  for (const [type, state] of cardState.entries()) {
    if (!state || state.data === null || state.data === undefined) continue;
    if (type === "full_report") continue;
    if (String(type).startsWith("resource.")) continue;
    byCard[type] = state.data;
  }

  const merged = {};
  if (currentSource === "scholar") {
    merged.researcher = byCard.profile || {};
    merged.publication_stats = byCard.metrics || {};
    merged.coauthor_stats = byCard.coauthors || {};
    merged.role_model = byCard.role_model || {};
    merged.paper_news = byCard.news || {};
    merged.level_info = byCard.level || {};
    merged.critical_evaluation = byCard.summary?.critical_evaluation ?? null;
  } else if (currentSource === "github") {
    merged.user = byCard.profile || {};
    merged.overview = byCard.activity?.overview ?? null;
    merged.activity = byCard.activity?.activity ?? null;
    merged.code_contribution = byCard.activity?.code_contribution ?? null;
    merged.feature_project = byCard.repos?.feature_project ?? null;
    merged.top_projects = byCard.repos?.top_projects ?? null;
    merged.most_valuable_pull_request = byCard.repos?.most_valuable_pull_request ?? null;
    merged.role_model = byCard.role_model || {};
    merged.roast = byCard.roast?.roast ?? null;
    merged.valuation_and_level = byCard.summary?.valuation_and_level ?? null;
    merged.description = byCard.summary?.description ?? null;
  } else if (currentSource === "linkedin") {
    merged.profile_data = { ...(byCard.profile || {}) };
    if (byCard.skills) merged.profile_data.skills = byCard.skills;
    if (byCard.career) {
      merged.profile_data.career = byCard.career.career;
      merged.profile_data.work_experience = byCard.career.work_experience;
      merged.profile_data.education = byCard.career.education;
      merged.profile_data.work_experience_summary = byCard.career.work_experience_summary;
      merged.profile_data.education_summary = byCard.career.education_summary;
    }
    if (byCard.role_model) merged.profile_data.role_model = byCard.role_model;
    if (byCard.money) merged.profile_data.money_analysis = byCard.money;
    if (byCard.roast?.roast) merged.profile_data.roast = byCard.roast.roast;
    if (byCard.summary) {
      merged.profile_data.about = byCard.summary.about;
      merged.profile_data.personal_tags = byCard.summary.personal_tags;
    }
  }

  return {
    schema: "synthetic_full_report_v1",
    source: currentSource,
    job_id: currentJobId || String(jobIdInput.value || "").trim() || null,
    generated_at: new Date().toISOString(),
    by_card: byCard,
    merged,
  };
}

function parseSseChunk(chunk, buffer) {
  buffer += chunk;
  while (true) {
    const sepIndex = buffer.indexOf("\n\n");
    if (sepIndex === -1) break;

    const raw = buffer.slice(0, sepIndex);
    buffer = buffer.slice(sepIndex + 2);

    const lines = raw.split(/\r?\n/);
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith("data:")) {
        dataLines.push(line.replace(/^data:\s?/, ""));
      }
    }
    if (!dataLines.length) continue;

    const data = dataLines.join("\n").trim();
    if (!data || data === "[DONE]") continue;

    try {
      const obj = JSON.parse(data);
      eventsHistory.push(obj);
      while (eventsHistory.length > MAX_EVENT_HISTORY) eventsHistory.shift();
      appendLog(`${obj.event_type || "event"} ${obj.payload?.card ? `[${obj.payload.card}]` : ""}`.trim());
      handleEvent(obj);
    } catch (err) {
      appendLog(`parse error: ${String(err)} · ${data.slice(0, 200)}`);
    }
  }
  return buffer;
}

async function streamResponse(response) {
  if (!response.body) {
    appendLog("stream: missing response.body");
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer = parseSseChunk(decoder.decode(value, { stream: true }), buffer);
  }
}

function startStreamState() {
  createButton.disabled = true;
  createAndStreamButton.disabled = true;
  fetchStatusButton.disabled = true;
  streamLastButton.disabled = true;
  streamFromStartButton.disabled = true;
  streamAtSeqButton.disabled = true;
  stopButton.disabled = false;
}

function stopStreamState() {
  createButton.disabled = false;
  createAndStreamButton.disabled = false;
  fetchStatusButton.disabled = false;
  streamLastButton.disabled = false;
  streamFromStartButton.disabled = false;
  streamAtSeqButton.disabled = false;
  stopButton.disabled = true;
}

function getAuthHeaders() {
  const token = normalizeBearerToken(tokenInput.value);
  if (!token) return null;
  return { Authorization: token };
}

function ensureAuthOrWarn() {
  const headers = getAuthHeaders();
  if (!headers) {
    alert("Missing JWT token. Paste a valid gateway JWT in Connection section.");
    return null;
  }
  return headers;
}

function hideCandidates() {
  candidatesPanel.hidden = true;
  candidatesEl.innerHTML = "";
  candidatesMessageEl.textContent = "";
}

function showCandidates(responseJson) {
  const candidates = Array.isArray(responseJson?.candidates) ? responseJson.candidates : [];
  const message = String(responseJson?.message || "").trim() || "Input is ambiguous. Choose a candidate.";

  candidatesMessageEl.textContent = message;
  candidatesEl.innerHTML = "";
  candidatesPanel.hidden = false;

  if (!candidates.length) {
    const empty = createElement("div", "candidate empty", "No candidates. Provide a more specific URL/ID.");
    candidatesEl.appendChild(empty);
    return;
  }

  candidates.forEach((cand) => {
    const label = String(cand?.label || "").trim() || "(candidate)";
    const content = String(cand?.input?.content || "").trim();
    const meta = cand?.meta && typeof cand.meta === "object" ? cand.meta : {};

    const card = createElement("div", "candidate");
    const head = createElement("div", "candidate-title", label);
    const sub = createElement("div", "candidate-sub", content);
    card.appendChild(head);
    card.appendChild(sub);

    const metaLines = [];
    if (meta.url) metaLines.push(`url: ${meta.url}`);
    if (meta.profile_url) metaLines.push(`profile_url: ${meta.profile_url}`);
    if (meta.affiliation) metaLines.push(`affiliation: ${meta.affiliation}`);
    if (meta.login) metaLines.push(`login: ${meta.login}`);
    if (meta.score !== undefined) metaLines.push(`score: ${meta.score}`);
    if (metaLines.length) {
      card.appendChild(createElement("div", "candidate-meta", metaLines.join(" · ")));
    }

    const actions = createElement("div", "candidate-actions");
    const btn = createElement("button", "secondary", "Use & Analyze");
    btn.addEventListener("click", async () => {
      contentInput.value = content;
      freeformInput.checked = false;
      hideCandidates();
      await createJob({ autoStream: true });
    });
    actions.appendChild(btn);
    card.appendChild(actions);

    candidatesEl.appendChild(card);
  });
}

function buildCreatePayload() {
  const source = currentSource;
  const mode = String(modeSelect.value || "async").trim().toLowerCase();
  const content = String(contentInput.value || "").trim();

  const payload = {
    source,
    mode,
    input: { content },
  };

  const options = {};
  if (freeformInput.checked) options.freeform = true;
  if (forceRefreshInput.checked) options.force_refresh = true;
  if (Object.keys(options).length) payload.options = options;

  if (!omitCardsInput.checked) {
    const cards = String(cardsInput.value || "")
      .split(",")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cards.length) payload.cards = cards;
  }

  return payload;
}

function expectedCardsForRun() {
  const source = currentSource;
  let raw = "";
  if (!omitCardsInput.checked) {
    raw = String(cardsInput.value || "");
  } else {
    raw = String(cardsBySource[source] || defaultCardsBySource[source] || "");
  }
  const cards = raw
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);
  // UI cards only.
  return cards.filter((c) => c !== "full_report" && !String(c).startsWith("resource."));
}

function initCardsPlaceholders() {
  const cards = expectedCardsForRun();
  if (!cards.length) return;
  cards.forEach((ct) => {
    getOrCreateCard(ct);
    updateCardStatus(ct, "pending");
  });
}

function setJobId(jobId) {
  const id = String(jobId || "").trim();
  if (!id) return;
  currentJobId = id;
  jobIdInput.value = id;
}

async function createJob({ autoStream }) {
  hideCandidates();

  const auth = ensureAuthOrWarn();
  if (!auth) return;

  const base = normalizeBaseUrl(apiBaseInput.value);
  const payload = buildCreatePayload();
  if (!payload.input.content) {
    alert("Missing input.content");
    return;
  }

  resetRunState();
  cardsBySource[currentSource] = String(cardsInput.value || "").trim() || defaultCardsBySource[currentSource];
  persistSettings();

  const headers = {
    "Content-Type": "application/json",
    ...auth,
  };

  const idem = String(idempotencyKeyInput.value || "").trim();
  if (idem) headers["Idempotency-Key"] = idem;

  const url = joinUrl(base, "/api/v1/analyze");

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });

    const text = await resp.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text };
    }

    if (!resp.ok) {
      appendLog(`create: HTTP ${resp.status}`);
      appendLog(typeof data === "object" ? JSON.stringify(data, null, 2) : String(data));
      jobStatusEl.textContent = "failed";
      return;
    }

    if (data?.needs_confirmation) {
      jobStatusEl.textContent = "needs_confirmation";
      showCandidates(data);
      return;
    }

    if (!data?.job_id) {
      appendLog("create: missing job_id");
      appendLog(JSON.stringify(data, null, 2));
      jobStatusEl.textContent = "failed";
      return;
    }

    setJobId(data.job_id);
    rememberJob(data.job_id, { source: payload.source, input: payload.input?.content });
    initCardsPlaceholders();
    jobStatusEl.textContent = data.status || (payload.mode === "sync" ? "completed" : "queued");
    appendLog(
      `create: job_id=${data.job_id} status=${data.status || "-"} cache_hit=${data.cache_hit ? "true" : "false"} idempotent_replay=${
        data.idempotent_replay ? "true" : "false"
      }`
    );

    if (payload.mode === "sync") {
      // Sync mode returns cards directly.
      const cards = data.cards && typeof data.cards === "object" ? data.cards : {};
      Object.entries(cards).forEach(([cardType, cardPayload]) => {
        updateCardStatus(cardType, "completed");
        setFinal(cardType, cardPayload);
      });
      await fetchJobStatus(); // update last_seq/next_after
      return;
    }

    // Async: optionally auto-stream; otherwise user can stream/status manually.
    if (autoStream) {
      await startStream(0);
    } else if (data.status === "completed") {
      // Cache-hit fast path: fetch snapshot so UI shows cards quickly.
      await fetchJobStatus();
    }
  } catch (err) {
    appendLog(`create error: ${String(err)}`);
    jobStatusEl.textContent = "failed";
  }
}

async function fetchJobStatus() {
  const auth = ensureAuthOrWarn();
  if (!auth) return;

  const base = normalizeBaseUrl(apiBaseInput.value);
  const jobId = String(jobIdInput.value || "").trim() || currentJobId;
  if (!jobId) {
    alert("Missing job id");
    return;
  }

  const url = joinUrl(base, `/api/v1/analyze/jobs/${encodeURIComponent(jobId)}`);
  try {
    const resp = await fetch(url, { headers: { ...auth } });
    const data = await resp.json();
    if (!resp.ok || !data?.success) {
      appendLog(`status: HTTP ${resp.status}`);
      appendLog(JSON.stringify(data, null, 2));
      return;
    }

    const job = data.job || {};
    if (job.source && job.source !== currentSource && defaultCardsBySource[String(job.source)]) {
      setActiveSource(String(job.source));
    }
    setJobId(job.job_id);
    rememberJob(job.job_id, { source: job.source });
    jobStatusEl.textContent = job.status || "unknown";
    initCardsPlaceholders();

    const jobLastSeq = Number(job.last_seq || 0);
    if (!Number.isNaN(jobLastSeq) && jobLastSeq >= 0) {
      lastSeq = Math.max(lastSeq, jobLastSeq);
      lastSeqEl.textContent = String(lastSeq);
      nextAfterEl.textContent = String(job.next_after || jobLastSeq || 0);
    }

    const cards = job.cards && typeof job.cards === "object" ? job.cards : {};
    const entries = Object.entries(cards);

    entries.forEach(([cardType, card]) => {
      const status = card?.status || "unknown";
      if (isInternalCard(cardType, card?.internal)) return;
      updateCardStatus(cardType, status);

      const env = normalizeOutputEnvelope(card?.output);
      if (!env) {
        appendLog(`warn: snapshot card has invalid output envelope: card=${cardType}`);
        return;
      }
      const state = getOrCreateCard(cardType);
      if (card?.stream_spec && typeof card.stream_spec === "object") {
        state.streamSpec = card.stream_spec;
      }

      // Snapshot should include accumulated deltas while running.
      state.output.stream = mergeStreams(state.output?.stream, env.stream);
      renderStream(cardType);
      renderCardContent(cardType, state.output, state.content, state.streamSpec);

      if (status === "completed" || status === "failed") {
        setFinal(cardType, env);
      }
    });

    appendLog(`status: ${job.status || "-"} last_seq=${job.last_seq || 0}`);
  } catch (err) {
    appendLog(`status error: ${String(err)}`);
  }
}

async function startStream(after) {
  const auth = ensureAuthOrWarn();
  if (!auth) return;

  const base = normalizeBaseUrl(apiBaseInput.value);
  const jobId = String(jobIdInput.value || "").trim() || currentJobId;
  if (!jobId) {
    alert("Missing job id");
    return;
  }

  const afterSeq = Number(after || 0);
  const safeAfter = Number.isNaN(afterSeq) ? 0 : Math.max(0, afterSeq);

  if (abortController) abortController.abort();
  abortController = new AbortController();
  startStreamState();
  jobStatusEl.textContent = "streaming";

  const url = joinUrl(base, `/api/v1/analyze/jobs/${encodeURIComponent(jobId)}/stream?after=${safeAfter}`);

  try {
    const resp = await fetch(url, { headers: { ...auth }, signal: abortController.signal });
    if (!resp.ok) {
      appendLog(`stream: HTTP ${resp.status}`);
      try {
        const errBody = await resp.json();
        appendLog(JSON.stringify(errBody, null, 2));
      } catch {
        appendLog(await resp.text());
      }
      jobStatusEl.textContent = "failed";
      return;
    }

    await streamResponse(resp);
    // Refresh snapshot at the end (ensures cards/status are aligned even if stream was interrupted).
    await fetchJobStatus();
  } catch (err) {
    appendLog(`stream error: ${String(err)}`);
    if (String(err).includes("AbortError")) {
      jobStatusEl.textContent = "stopped";
    } else {
      jobStatusEl.textContent = "failed";
    }
  } finally {
    stopStreamState();
  }
}

async function saveScreenshot() {
  const target = cardsContainer;
  if (!target) return;

  if (typeof html2canvas !== "function") {
    appendLog("html2canvas not available; cannot capture screenshot.");
    alert("html2canvas not loaded. Check network or CDN access.");
    return;
  }

  try {
    const canvas = await html2canvas(target, { backgroundColor: "#f6f5f2", scale: 2 });
    const dataUrl = canvas.toDataURL("image/png");
    const link = document.createElement("a");
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    link.href = dataUrl;
    link.download = `dinq-cards-${timestamp}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } catch (err) {
    appendLog(`screenshot error: ${err}`);
  }
}

function loadMockData() {
  resetRunState();
  const mock = MOCK_DATA[currentSource];
  if (!mock) {
    appendLog("No mock data for current source.");
    return;
  }

  Object.entries(mock).forEach(([cardType, payload]) => {
    updateCardStatus(cardType, "completed");
    setFinal(cardType, wrapAsOutputEnvelope(payload));
  });

  jobStatusEl.textContent = "mocked";
  appendLog("Loaded mock data for " + currentSource);
}

function stopAnalyze() {
  if (abortController) {
    abortController.abort();
  }
  jobStatusEl.textContent = "stopped";
  stopStreamState();
}

function generateIdempotencyKey() {
  const bytes = new Uint8Array(16);
  if (window.crypto && typeof window.crypto.getRandomValues === "function") {
    window.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function copyCurl() {
  const base = normalizeBaseUrl(apiBaseInput.value);
  const payload = buildCreatePayload();

  const idem = String(idempotencyKeyInput.value || "").trim();
  const includeToken = !!includeTokenInCurlInput.checked;
  const rawToken = tokenInput.value.trim();
  const token = includeToken ? normalizeBearerToken(rawToken) : "Bearer <JWT>";

  const lines = [];
  lines.push(`curl -X POST '${joinUrl(base, "/api/v1/analyze")}' \\\n`);
  lines.push(`  -H 'Content-Type: application/json' \\\n`);
  lines.push(`  -H 'Authorization: ${token || "Bearer <JWT>"}' \\\n`);
  if (idem) lines.push(`  -H 'Idempotency-Key: ${idem}' \\\n`);
  lines.push(`  -d '${JSON.stringify(payload).replace(/'/g, "'\\''")}'`);

  const curl = lines.join("");
  try {
    await navigator.clipboard.writeText(curl);
    appendLog("copied curl to clipboard");
  } catch (err) {
    appendLog(`copy curl failed: ${String(err)}`);
    alert(curl);
  }
}

createButton.addEventListener("click", () => createJob({ autoStream: false }));
createAndStreamButton.addEventListener("click", async () => {
  const mode = String(modeSelect.value || "async").trim().toLowerCase();
  await createJob({ autoStream: mode === "async" });
});
stopButton.addEventListener("click", stopAnalyze);
fetchStatusButton.addEventListener("click", fetchJobStatus);
streamFromStartButton.addEventListener("click", () => startStream(0));
streamLastButton.addEventListener("click", () => startStream(lastSeq));
streamAtSeqButton.addEventListener("click", () => {
  const n = Number(afterSeqInput.value);
  startStream(Number.isNaN(n) ? 0 : n);
});
clearLogButton.addEventListener("click", clearLog);
copyCurlButton.addEventListener("click", copyCurl);
saveScreenshotButton.addEventListener("click", saveScreenshot);
loadMockButton.addEventListener("click", loadMockData);
genIdempotencyKeyButton.addEventListener("click", () => {
  idempotencyKeyInput.value = generateIdempotencyKey();
});

omitCardsInput.addEventListener("change", setOmitCardsUI);
cardsInput.addEventListener("input", () => {
  cardsBySource[currentSource] = cardsInput.value;
  persistSettings();
});
apiBaseInput.addEventListener("input", persistSettings);
tokenInput.addEventListener("input", persistSettings);
includeTokenInCurlInput.addEventListener("change", persistSettings);
if (debugModeInput) debugModeInput.addEventListener("change", () => { applyDebugMode(); persistSettings(); });

saveSettingsButton.addEventListener("click", () => {
  persistSettings();
  appendLog("settings saved");
});
clearSettingsButton.addEventListener("click", () => {
  clearSettings();
  appendLog("settings cleared");
});

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    setActiveSource(btn.dataset.source);
  });
});

loadSettings();
setOmitCardsUI();
applyDebugMode();
renderRecentJobs();
setActiveSource(currentSource);
