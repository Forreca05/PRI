const form = document.querySelector("#search-form");
const input = document.querySelector("#query");
const typeSelect = document.querySelector("#type");
const systemSelect = document.querySelector("#system");
const message = document.querySelector("#message");
const resultsElement = document.querySelector("#results");
const heading = document.querySelector("#results-heading");
const pagination = document.querySelector("#pagination");
const previous = document.querySelector("#previous");
const next = document.querySelector("#next");
const pageLabel = document.querySelector("#page-label");

let currentPage = 1;
let totalPages = 0;

function addText(parent, tag, text, className) {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  parent.append(element);
  return element;
}

function renderResult(doc) {
  const card = document.createElement("article");
  card.className = "result-card";
  const top = document.createElement("div");
  top.className = "result-top";
  addText(top, "span", doc.type, "badge");
  if (doc.score !== undefined) addText(top, "span", `SCORE ${Number(doc.score).toFixed(2)}`, "score");
  card.append(top);

  const title = document.createElement("h2");
  const titleLink = document.createElement("a");
  titleLink.textContent = doc.title || doc.id;
  if (doc.wikipedia_url && /^https:\/\/en\.wikipedia\.org\//.test(doc.wikipedia_url)) {
    titleLink.href = doc.wikipedia_url;
    titleLink.target = "_blank";
    titleLink.rel = "noopener noreferrer";
  } else {
    titleLink.href = "#";
    titleLink.addEventListener("click", event => event.preventDefault());
  }
  title.append(titleLink);
  card.append(title);

  const metadata = [];
  if (doc.season) metadata.push(String(doc.season));
  if (doc.date) metadata.push(doc.date);
  if (doc.circuit) metadata.push(doc.circuit);
  if (doc.country) metadata.push(doc.country);
  if (doc.nationality) metadata.push(doc.nationality);
  if (doc.wins !== undefined) metadata.push(`${doc.wins} wins`);
  if (doc.championships !== undefined) metadata.push(`${doc.championships} championships`);
  if (metadata.length) addText(card, "div", metadata.join("  ·  "), "metadata");
  if (doc.summary) addText(card, "p", doc.summary.slice(0, 420) + (doc.summary.length > 420 ? "…" : ""));
  return card;
}

async function search(page = 1) {
  const query = input.value.trim();
  if (!query) {
    input.focus();
    return;
  }
  currentPage = page;
  resultsElement.replaceChildren();
  heading.replaceChildren();
  pagination.hidden = true;
  message.className = "message";
  message.textContent = "Searching the archive…";

  const params = new URLSearchParams({
    q: query,
    type: typeSelect.value,
    system: systemSelect.value,
    page: String(page),
  });
  try {
    const response = await fetch(`/api/search?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Search failed.");
    totalPages = data.pages;
    message.textContent = data.total
      ? ""
      : "No matching documents. Try different keywords or broaden the document type.";
    if (data.total) {
      const start = (page - 1) * 10 + 1;
      const end = Math.min(page * 10, data.total);
      addText(heading, "strong", `${start}–${end}`);
      heading.append(" of ");
      addText(heading, "strong", data.total.toLocaleString());
      heading.append(" results");
      data.results.forEach(doc => resultsElement.append(renderResult(doc)));
    }
    if (totalPages > 1) {
      pagination.hidden = false;
      previous.disabled = page <= 1;
      next.disabled = page >= totalPages;
      pageLabel.textContent = `Page ${page} of ${totalPages}`;
    }
  } catch (error) {
    message.className = "message error";
    message.textContent = error.message;
  }
}

form.addEventListener("submit", event => {
  event.preventDefault();
  search(1);
});
previous.addEventListener("click", () => search(currentPage - 1));
next.addEventListener("click", () => search(currentPage + 1));
document.querySelectorAll("[data-query]").forEach(button => {
  button.addEventListener("click", () => {
    input.value = button.dataset.query;
    search(1);
  });
});
