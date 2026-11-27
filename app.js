const settingSelect = document.querySelector("#setting-select");
const themeSelect = document.querySelector("#theme-select");
const generateButton = document.querySelector("#generate-button");
const headlineList = document.querySelector("#headline-list");
const resultCount = document.querySelector("#result-count");
const headlineInput = document.querySelector("#headline-input");
const charCount = document.querySelector("#char-count");
const analyzeButton = document.querySelector("#analyze-button");
const analysisResult = document.querySelector("#analysis-result");
const classifyButton = document.querySelector("#classify-button");
const classificationResult = document.querySelector("#classification-result");
const statusText = document.querySelector("#status-text");
const generatorBadge = document.querySelector("#generator-badge");
const generatorModelState = document.querySelector("#generator-model-state");
const factCheckBadge = document.querySelector("#fact-check-badge");
const factCheckModelState = document.querySelector("#fact-check-model-state");
const classifierBadge = document.querySelector("#classifier-badge");

async function requestApi(path, body) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || "The local model service returned an error.");
  return result;
}

function setModelState(badge, stateElement, name, loaded, dependenciesInstalled, failed) {
  let state = "NOT LOADED";
  let detail = "Loads on first use";
  if (loaded) {
    state = "READY";
    detail = "Loaded in memory";
  } else if (failed) {
    state = "LOAD ERROR";
    detail = "Could not load model";
  } else if (!dependenciesInstalled) {
    state = "SETUP REQUIRED";
    detail = "Install model dependencies";
  }
  badge.textContent = `${name} · ${state}`;
  stateElement.lastChild.textContent = ` ${detail}`;
  stateElement.dataset.state = loaded ? "ready" : failed ? "error" : "pending";
}

async function checkModelStatus() {
  try {
    const result = await requestApi("/api/status");
    setModelState(generatorBadge, generatorModelState, "GPT-2", result.generator.loaded, result.dependencies_installed, result.generator.error);
    classifierBadge.textContent = result.classifier.loaded
      ? "ROBERTA · READY"
      : result.classifier.error
        ? "ROBERTA · LOAD ERROR"
        : "ROBERTA · LOADS ON USE";
    const sourceConfigured = result.fact_check_search.configured;
    factCheckBadge.textContent = sourceConfigured ? "GOOGLE · API READY" : "GOOGLE · EXPLORER FALLBACK";
    factCheckModelState.lastChild.textContent = sourceConfigured ? " API key configured" : " Public search link available";
    factCheckModelState.dataset.state = sourceConfigured ? "ready" : "pending";
    statusText.textContent = sourceConfigured ? "FACT-CHECK API READY" : "PUBLIC EXPLORER FALLBACK";
  } catch {
    statusText.textContent = "START LOCAL SERVER";
    generatorBadge.textContent = "GPT-2 · SERVER REQUIRED";
    factCheckBadge.textContent = "GOOGLE · SERVER REQUIRED";
    classifierBadge.textContent = "ROBERTA · SERVER REQUIRED";
    generatorModelState.lastChild.textContent = " Start the local Python server";
    factCheckModelState.lastChild.textContent = " Start the local Python server";
  }
}

function updateCharacterCount() {
  charCount.textContent = `${headlineInput.value.length} / 240`;
}

function showRequestError(container, message) {
  container.replaceChildren();
  const box = document.createElement("div");
  box.className = "result-placeholder request-error";
  const rule = document.createElement("span");
  rule.className = "placeholder-rule";
  const text = document.createElement("p");
  text.textContent = message;
  box.append(rule, text);
  container.append(box);
}

function renderHeadlines(headlines) {
  headlineList.replaceChildren();
  headlines.forEach((headline, index) => {
    const card = document.createElement("article");
    card.className = "headline-card";

    const number = document.createElement("span");
    number.className = "headline-number";
    number.textContent = String(index + 1).padStart(2, "0");

    const copy = document.createElement("div");
    const title = document.createElement("div");
    title.className = "headline-copy";
    title.textContent = headline;
    const label = document.createElement("span");
    label.className = "fiction-label";
    label.textContent = "GPT-2 · FICTIONAL";
    copy.append(title, label);

    const inspect = document.createElement("button");
    inspect.className = "inspect-button";
    inspect.type = "button";
    inspect.setAttribute("aria-label", `Search fact-checks for headline ${index + 1}`);
    inspect.title = "Search existing fact-checks";
    inspect.textContent = "+";
    inspect.addEventListener("click", () => {
      headlineInput.value = headline;
      updateCharacterCount();
      analyzeHeadline();
      document.querySelector("#analyzer").scrollIntoView({ behavior: "smooth", block: "start" });
    });

    card.append(number, copy, inspect);
    headlineList.append(card);
  });
  resultCount.textContent = `${headlines.length} ITEMS`;
}

async function generateHeadlines() {
  const buttonLabel = generateButton.querySelector("span");
  const originalLabel = buttonLabel.textContent;
  generateButton.disabled = true;
  buttonLabel.textContent = "Loading GPT-2...";
  try {
    const result = await requestApi("/api/generate", {
      setting: settingSelect.value,
      theme: themeSelect.value
    });
    renderHeadlines(result.headlines);
    generatorBadge.textContent = "GPT-2 · READY";
    generatorModelState.lastChild.textContent = " Loaded in memory";
    generatorModelState.dataset.state = "ready";
    statusText.textContent = "LOCAL MODELS ACTIVE";
  } catch (error) {
    showRequestError(headlineList, error.message);
    resultCount.textContent = "0 ITEMS";
  } finally {
    generateButton.disabled = false;
    buttonLabel.textContent = originalLabel;
  }
}

function renderFactChecks(result) {
  analysisResult.replaceChildren();

  const summary = document.createElement("div");
  summary.className = "fact-check-summary";
  const label = document.createElement("span");
  label.className = "fact-check-summary-label";
  label.textContent = result.fallback
    ? "Continue search in public Fact Check Explorer"
    : result.result_count
    ? `${result.result_count} existing ${result.result_count === 1 ? "review" : "reviews"} found`
    : "No matching reviews found";
  const score = document.createElement("span");
  score.className = "prediction-score";
  score.textContent = "SOURCE SEARCH";
  summary.append(label, score);

  analysisResult.append(summary);
  if (result.fallback) {
    const card = document.createElement("article");
    card.className = "fact-check-card";
    const explanation = document.createElement("p");
    explanation.className = "fact-check-claim";
    explanation.textContent = `Search query: ${result.query}`;
    const link = document.createElement("a");
    link.className = "fact-check-external-link";
    link.href = result.search_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Open public Fact Check Explorer ↗";
    card.append(explanation, link);
    analysisResult.append(card);
  }
  result.results.forEach((review) => {
    const card = document.createElement("article");
    card.className = "fact-check-card";

    const publisher = document.createElement("div");
    publisher.className = "fact-check-publisher";
    publisher.textContent = review.publisher_site
      ? `${review.publisher} · ${review.publisher_site}`
      : review.publisher;

    const title = document.createElement("h3");
    title.className = "fact-check-title";
    title.textContent = review.title;

    const claim = document.createElement("p");
    claim.className = "fact-check-claim";
    claim.textContent = review.claim;

    const rating = document.createElement("p");
    rating.className = "fact-check-rating";
    rating.textContent = `Publisher rating: ${review.rating}`;

    const footer = document.createElement("div");
    footer.className = "fact-check-footer";
    const date = document.createElement("span");
    date.textContent = review.review_date ? `Reviewed ${review.review_date}` : "Review date not provided";
    const link = document.createElement("a");
    link.href = review.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Read publisher review ↗";
    footer.append(date, link);
    card.append(publisher, title, claim, rating, footer);
    analysisResult.append(card);
  });

  const disclaimer = document.createElement("p");
  disclaimer.className = "analysis-disclaimer";
  disclaimer.textContent = result.disclaimer;
  analysisResult.append(disclaimer);

  factCheckBadge.textContent = result.fallback ? "GOOGLE · EXPLORER LINK" : "GOOGLE · SEARCHED";
  factCheckModelState.lastChild.textContent = result.fallback ? " Public search opened" : " Fact-check search complete";
  factCheckModelState.dataset.state = result.fallback ? "pending" : "ready";
  statusText.textContent = result.fallback ? "PUBLIC EXPLORER FALLBACK" : "FACT-CHECK SEARCH COMPLETE";
}

function renderClassifierResult(result) {
  classificationResult.replaceChildren();

  const summary = document.createElement("div");
  summary.className = "prediction-summary";
  const label = document.createElement("span");
  label.className = "prediction-label";
  label.textContent = result.label;
  const score = document.createElement("span");
  score.className = "prediction-score";
  score.textContent = `${Math.round(result.score * 100)}% raw score`;
  summary.append(label, score);

  const model = document.createElement("p");
  model.className = "prediction-model";
  model.textContent = result.model;
  const warning = document.createElement("p");
  warning.className = "analysis-disclaimer";
  warning.textContent = result.warning;
  classificationResult.append(summary, model, warning);
  classifierBadge.textContent = "ROBERTA · READY";
}

async function analyzeHeadline() {
  const text = headlineInput.value.trim();
  if (!text) {
    headlineInput.focus();
    showRequestError(analysisResult, "Enter a headline to classify.");
    return;
  }
  if (text.length < 8) {
    showRequestError(analysisResult, "Enter at least 8 characters so the classifier can process the text.");
    return;
  }

  const buttonLabel = analyzeButton.querySelector("span");
  const originalLabel = buttonLabel.textContent;
  analyzeButton.disabled = true;
  buttonLabel.textContent = "Searching fact-checks...";
  try {
    const result = await requestApi("/api/fact-check", { text });
    renderFactChecks(result);
  } catch (error) {
    showRequestError(analysisResult, error.message);
  } finally {
    analyzeButton.disabled = false;
    buttonLabel.textContent = originalLabel;
  }
}

async function classifyHeadline() {
  const text = headlineInput.value.trim();
  if (!text) {
    headlineInput.focus();
    showRequestError(classificationResult, "Enter a headline before running the experimental model.");
    return;
  }
  if (text.length < 8) {
    showRequestError(classificationResult, "Enter at least 8 characters so the model can process the text.");
    return;
  }

  const buttonLabel = classifyButton.querySelector("span");
  const originalLabel = buttonLabel.textContent;
  classifyButton.disabled = true;
  buttonLabel.textContent = "Loading RoBERTa...";
  try {
    const result = await requestApi("/api/classify", { text });
    renderClassifierResult(result);
  } catch (error) {
    showRequestError(classificationResult, error.message);
  } finally {
    classifyButton.disabled = false;
    buttonLabel.textContent = originalLabel;
  }
}

generateButton.addEventListener("click", generateHeadlines);
headlineInput.addEventListener("input", updateCharacterCount);
analyzeButton.addEventListener("click", analyzeHeadline);
classifyButton.addEventListener("click", classifyHeadline);
headlineInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") analyzeHeadline();
});

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("is-active"));
    link.classList.add("is-active");
  });
});

checkModelStatus();