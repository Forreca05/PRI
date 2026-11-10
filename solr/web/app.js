const $ = selector => document.querySelector(selector);
const form = $("#search-form");
const input = $("#query");
const typeSelect = $("#type");
const systemSelect = $("#system");
const fromInput = $("#from");
const toInput = $("#to");
const compareBox = $("#compare");
const message = $("#message");
const resultsElement = $("#results");
const heading = $("#results-heading");
const typeCounts = $("#type-counts");
const pagination = $("#pagination");
const previous = $("#previous");
const next = $("#next");
const pageLabel = $("#page-label");
const examples = $("#examples");
const correction = $("#correction");
let exact = false;  // true after "search instead for …": the typed words are searched as they are

const TYPE_LABELS = { race: "Races", driver: "Drivers", team: "Teams", circuit: "Circuits" };
const SYSTEM_LABELS = { simple: "Baseline", boosted: "Boosted" };
let currentPage = 1;

function addText(parent, tag, text, className) {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

// Highlighted words arrive wrapped in two private-use characters; build <mark> nodes from them
// so that no text from the documents is ever inserted as HTML.
function addHighlighted(parent, text, [pre, post]) {
  const paragraph = document.createElement("p");
  paragraph.className = "snippet";
  text.split(pre).forEach((part, index) => {
    if (index === 0) return paragraph.append(part);
    const [marked, rest = ""] = part.split(post);
    addText(paragraph, "mark", marked);
    paragraph.append(rest);
  });
  parent.append(paragraph);
}

function metadataOf(doc) {
  const span = doc.first_season && doc.last_season
    ? (doc.first_season === doc.last_season ? String(doc.first_season) : `${doc.first_season}–${doc.last_season}`)
    : null;
  const items = {
    race: [(doc.date || "").slice(0, 10) || doc.season, doc.circuit, doc.country,
           doc.winner && `Winner: ${doc.winner.join(", ")}`,
           doc.winning_team && doc.winning_team.join(", ")],
    driver: [doc.nationality, span, doc.wins !== undefined && `${doc.wins} wins`,
             doc.championships ? `${doc.championships} titles` : null],
    team: [doc.nationality, span, doc.wins !== undefined && `${doc.wins} wins`,
           doc.championships ? `${doc.championships} titles` : null],
    circuit: [doc.locality, doc.country, span],
  }[doc.type] || [];
  return items.filter(Boolean).map(String);
}

function renderResult(doc, { marks, rank, shared }) {
  const card = document.createElement("article");
  card.className = "result-card" + (shared ? " shared" : "");
  const top = document.createElement("div");
  top.className = "result-top";
  if (rank) addText(top, "span", String(rank).padStart(2, "0"), "rank");
  addText(top, "span", doc.type, "badge");
  if (shared) addText(top, "span", "IN BOTH", "badge both");
  if (doc.score !== undefined) addText(top, "span", `SCORE ${Number(doc.score).toFixed(2)}`, "score");
  card.append(top);

  const title = document.createElement("h2");
  const link = document.createElement("a");
  link.textContent = doc.title || doc.id;
  // Older Jolpica records store the link with http://; open every one over https.
  if (doc.wikipedia_url && /^https?:\/\/en\.wikipedia\.org\//.test(doc.wikipedia_url)) {
    link.href = doc.wikipedia_url.replace(/^http:/, "https:");
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  }
  title.append(link);
  card.append(title);

  const metadata = metadataOf(doc);
  if (metadata.length) {
    const row = document.createElement("div");
    row.className = "metadata";
    metadata.forEach(item => addText(row, "span", item));
    card.append(row);
  }
  if (doc.snippet) addHighlighted(card, doc.snippet, marks);
  else if (doc.summary) addText(card, "p", doc.summary.slice(0, 320) + (doc.summary.length > 320 ? "…" : ""), "snippet");
  return card;
}

function currentState() {
  return {
    q: input.value.trim(),
    type: typeSelect.value,
    system: systemSelect.value,
    from: fromInput.value.trim(),
    to: toInput.value.trim(),
    compare: compareBox.checked,
    exact,
  };
}

function applyState(state) {
  input.value = state.q || "";
  typeSelect.value = TYPE_LABELS[state.type] ? state.type : "all";
  systemSelect.value = SYSTEM_LABELS[state.system] ? state.system : "boosted";
  fromInput.value = state.from || "";
  toInput.value = state.to || "";
  compareBox.checked = Boolean(state.compare);
  exact = state.exact === "1";
  systemSelect.disabled = compareBox.checked;
}

function updateUrl(state, page, push) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.type !== "all") params.set("type", state.type);
  if (state.system !== "boosted") params.set("system", state.system);
  if (state.from) params.set("from", state.from);
  if (state.to) params.set("to", state.to);
  if (state.compare) params.set("compare", "1");
  if (state.exact) params.set("exact", "1");
  if (page > 1) params.set("page", String(page));
  const url = params.toString() ? `?${params}` : location.pathname;
  history[push ? "pushState" : "replaceState"](null, "", url);
}

async function fetchResults(state, system, page) {
  const params = new URLSearchParams({ q: state.q, type: state.type, system, page: String(page) });
  if (state.from) params.set("from", state.from);
  if (state.to) params.set("to", state.to);
  if (state.exact) params.set("exact", "1");
  const response = await fetch(`/api/search?${params}`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Search failed.");
  return data;
}

function renderTypeCounts(types, active) {
  typeCounts.replaceChildren();
  const total = Object.values(types).reduce((sum, n) => sum + n, 0);
  [["all", "All", total], ...Object.keys(TYPE_LABELS).map(t => [t, TYPE_LABELS[t], types[t] || 0])]
    .forEach(([value, label, count]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "type-chip" + (value === active ? " active" : "");
      button.disabled = count === 0 && value !== active;
      addText(button, "span", label);
      addText(button, "span", count.toLocaleString(), "count");
      button.addEventListener("click", () => {
        typeSelect.value = value;
        search(1);
      });
      typeCounts.append(button);
    });
  typeCounts.hidden = false;
}

function renderCorrection(corrected, original) {
  correction.replaceChildren();
  correction.hidden = !corrected;
  if (!corrected) return;
  correction.append("Showing results for ");
  addText(correction, "strong", corrected);
  correction.append(". Search instead for ");
  const link = addText(correction, "button", original, "link");
  link.type = "button";
  link.addEventListener("click", () => {
    exact = true;
    search(1);
  });
  correction.append(".");
}

function renderHeading(data, page) {
  heading.replaceChildren();
  if (!data.total) return;
  const start = (page - 1) * 10 + 1;
  const end = Math.min(page * 10, data.total);
  addText(heading, "strong", `${start}–${end}`);
  heading.append(" of ");
  addText(heading, "strong", data.total.toLocaleString());
  heading.append(" results");
}

function renderSingle(data, page) {
  renderHeading(data, page);
  resultsElement.className = "results";
  data.results.forEach((doc, i) =>
    resultsElement.append(renderResult(doc, { marks: data.marks, rank: (page - 1) * 10 + i + 1 })));
  if (data.pages > 1) {
    pagination.hidden = false;
    previous.disabled = page <= 1;
    next.disabled = page >= data.pages;
    pageLabel.textContent = `Page ${page} of ${data.pages.toLocaleString()}`;
  }
}

function renderComparison(runs) {
  const ids = runs.map(({ data }) => new Set(data.results.map(doc => doc.id)));
  const shared = [...ids[0]].filter(id => ids[1].has(id));
  heading.replaceChildren();
  heading.append("Top 10 of each setup · ");
  addText(heading, "strong", String(shared.length));
  heading.append(shared.length === 1 ? " document in both lists" : " documents in both lists");
  resultsElement.className = "results compare";
  runs.forEach(({ system, data }) => {
    const column = document.createElement("div");
    column.className = "compare-column";
    const title = addText(column, "h3", SYSTEM_LABELS[system]);
    addText(title, "span", `${data.total.toLocaleString()} found`, "found");
    if (!data.results.length) addText(column, "p", "No matching documents.", "message");
    data.results.forEach((doc, i) => column.append(renderResult(doc, {
      marks: data.marks, rank: i + 1, shared: shared.includes(doc.id),
    })));
    resultsElement.append(column);
  });
}

async function search(page = 1, { push = true } = {}) {
  const state = currentState();
  if (!state.q) {
    input.focus();
    return;
  }
  currentPage = page;
  updateUrl(state, page, push);
  examples.hidden = true;
  correction.hidden = true;
  resultsElement.replaceChildren();
  heading.replaceChildren();
  pagination.hidden = true;
  message.className = "message";
  message.textContent = "Searching the archive…";

  try {
    if (state.compare) {
      const runs = await Promise.all(["simple", "boosted"].map(async system =>
        ({ system, data: await fetchResults(state, system, 1) })));
      renderCorrection(runs[1].data.corrected, state.q);
      renderTypeCounts(runs[1].data.types, state.type);
      message.textContent = runs.some(r => r.data.total) ? "" : "No matching documents. Try different keywords.";
      if (runs.some(r => r.data.total)) renderComparison(runs);
    } else {
      const data = await fetchResults(state, state.system, page);
      renderCorrection(data.corrected, state.q);
      renderTypeCounts(data.types, state.type);
      message.textContent = data.total ? "" : "No matching documents. Try different keywords or broaden the filters.";
      renderSingle(data, page);
    }
  } catch (error) {
    typeCounts.hidden = true;
    message.className = "message error";
    message.textContent = error.message;
  }
}

async function loadExamples() {
  try {
    const response = await fetch("/api/needs");
    const { needs } = await response.json();
    needs.forEach(need => {
      const button = document.createElement("button");
      button.type = "button";
      button.title = need.q;
      addText(button, "span", need.id, "need-id");
      button.append(" " + need.need);
      button.addEventListener("click", () => {
        input.value = need.q;
        typeSelect.value = need.type;
        exact = false;
        search(1);
      });
      examples.append(button);
    });
    examples.hidden = Boolean(new URLSearchParams(location.search).get("q"));
  } catch {
    examples.hidden = true;
  }
}

function loadFromUrl() {
  const params = new URLSearchParams(location.search);
  applyState(Object.fromEntries(params));
  if (params.get("q")) return search(Number(params.get("page")) || 1, { push: false });
  [resultsElement, heading].forEach(el => el.replaceChildren());
  typeCounts.hidden = pagination.hidden = correction.hidden = true;
  examples.hidden = examples.children.length <= 1;
  message.className = "message";
  message.textContent = "Search the archive to explore more than 2,000 F1 documents.";
}

form.addEventListener("submit", event => {
  event.preventDefault();
  exact = false;
  search(1);
});
input.addEventListener("input", () => { exact = false; });
[typeSelect, systemSelect].forEach(el => el.addEventListener("change", () => input.value.trim() && search(1)));
[fromInput, toInput].forEach(el => el.addEventListener("change", () => input.value.trim() && search(1)));
compareBox.addEventListener("change", () => {
  systemSelect.disabled = compareBox.checked;
  if (input.value.trim()) search(1);
});
previous.addEventListener("click", () => search(currentPage - 1));
next.addEventListener("click", () => search(currentPage + 1));
window.addEventListener("popstate", loadFromUrl);

loadExamples();
loadFromUrl();
