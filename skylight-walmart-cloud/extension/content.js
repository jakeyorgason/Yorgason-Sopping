const PANEL_ID = "skylight-walmart-review-panel";
const STOP_WORDS = new Set([
  "a", "an", "and", "the", "of", "for", "with", "to", "in", "on",
  "fresh", "grocery", "walmart", "item", "items", "pack", "package"
]);

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokens(value) {
  return normalizeText(value)
    .split(" ")
    .filter(token => token.length > 1 && !STOP_WORDS.has(token) && !/^\d+$/.test(token));
}

function titleScore(query, title) {
  const wanted = [...new Set(tokens(query))];
  const actual = new Set(tokens(title));
  if (wanted.length === 0) return 0;
  const matches = wanted.filter(token => actual.has(token)).length;
  return matches / wanted.length;
}

function parsePrice(text) {
  const matches = String(text || "").match(/\$\s*(\d+(?:\.\d{1,2})?)/g) || [];
  const values = matches
    .map(match => Number(match.replace(/[^0-9.]/g, "")))
    .filter(value => Number.isFinite(value) && value > 0);
  return values.length ? Math.min(...values) : Number.POSITIVE_INFINITY;
}

function findTitle(card) {
  const selectors = [
    "[data-automation-id='product-title']",
    "[data-testid='product-title']",
    "span[itemprop='name']",
    "a[link-identifier='linkText'] span",
    "a[href*='/ip/'] span",
    "a[href*='/ip/']"
  ];
  for (const selector of selectors) {
    const node = card.querySelector(selector);
    const text = node && node.textContent ? node.textContent.trim() : "";
    if (text.length >= 3) return text;
  }
  return "";
}

function findAddButton(card) {
  const buttons = [...card.querySelectorAll("button")];
  return buttons.find(button => {
    const label = `${button.getAttribute("aria-label") || ""} ${button.textContent || ""}`.trim();
    return /(^|\s)add(\s|$)|add to cart/i.test(label) && !button.disabled;
  }) || null;
}

function cardCandidates() {
  const selectors = [
    "[data-item-id]",
    "[data-testid='item-stack'] > div",
    "article"
  ];
  const nodes = new Set();
  selectors.forEach(selector => document.querySelectorAll(selector).forEach(node => nodes.add(node)));

  const results = [];
  nodes.forEach(card => {
    const title = findTitle(card);
    const button = findAddButton(card);
    if (!title || !button) return;

    const text = card.textContent || "";
    const priceNode = card.querySelector("[itemprop='price']");
    const attrPrice = priceNode ? Number(priceNode.getAttribute("content")) : Number.NaN;
    const price = Number.isFinite(attrPrice) && attrPrice > 0 ? attrPrice : parsePrice(text);
    if (!Number.isFinite(price)) return;

    const outOfStock = /out of stock|not available/i.test(text);
    const pickup = /pickup|curbside/i.test(text) && !/pickup unavailable/i.test(text);
    results.push({ card, title, button, price, pickup, outOfStock });
  });

  return results;
}

function rankCandidates(item) {
  const query = item.search_query || item.name;
  return cardCandidates()
    .filter(candidate => !candidate.outOfStock)
    .map(candidate => ({
      ...candidate,
      score: titleScore(query, candidate.title)
    }))
    .filter(candidate => candidate.score >= 0.34)
    .sort((a, b) => {
      if (a.pickup !== b.pickup) return a.pickup ? -1 : 1;
      if (Math.abs(a.score - b.score) >= 0.15) return b.score - a.score;
      return a.price - b.price;
    });
}

function panelBase(item, index, total) {
  const old = document.getElementById(PANEL_ID);
  if (old) old.remove();

  const panel = document.createElement("section");
  panel.id = PANEL_ID;
  panel.style.cssText = [
    "position:fixed",
    "right:18px",
    "top:90px",
    "z-index:2147483647",
    "width:390px",
    "max-height:78vh",
    "overflow:auto",
    "background:#fff",
    "border:2px solid #0071dc",
    "border-radius:14px",
    "box-shadow:0 18px 50px rgba(0,0,0,.25)",
    "padding:16px",
    "font-family:Arial,Helvetica,sans-serif",
    "color:#111827"
  ].join(";");

  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
      <div>
        <div style="font-size:12px;color:#64748b;font-weight:700">ITEM ${index + 1} OF ${total}</div>
        <h2 style="font-size:18px;margin:4px 0 4px">${escapeHtml(item.name)}</h2>
        <div style="font-size:13px;color:#475569">Need: ${escapeHtml(item.quantity)} ${escapeHtml(item.unit)} · Add ${escapeHtml(item.packages || 1)} package(s)</div>
        ${item.notes ? `<div style="font-size:12px;color:#7c2d12;margin-top:4px">Preference: ${escapeHtml(item.notes)}</div>` : ""}
      </div>
      <button id="sw-stop" style="border:0;background:#f1f5f9;border-radius:8px;padding:7px 9px;cursor:pointer">Pause</button>
    </div>
    <div id="sw-body" style="margin-top:12px"></div>
    <div style="display:flex;gap:8px;margin-top:12px">
      <button id="sw-retry" style="flex:1;padding:9px;border:1px solid #cbd5e1;border-radius:8px;background:white;cursor:pointer">Rescan</button>
      <button id="sw-skip" style="flex:1;padding:9px;border:1px solid #cbd5e1;border-radius:8px;background:#fff7ed;cursor:pointer">Skip item</button>
    </div>
  `;

  document.body.appendChild(panel);
  panel.querySelector("#sw-stop").addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "STOP_RUN" });
    panel.remove();
  });
  panel.querySelector("#sw-retry").addEventListener("click", () => processCurrentPage(true));
  panel.querySelector("#sw-skip").addEventListener("click", () => advance(item, null, "skipped"));
  return panel;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function clickPackageQuantity(candidate, packages) {
  candidate.card.scrollIntoView({ behavior: "smooth", block: "center" });
  await sleep(350);
  candidate.button.click();

  const desired = Math.max(1, Number(packages) || 1);
  for (let count = 1; count < desired; count += 1) {
    await sleep(900);
    const plusSelectors = [
      "button[aria-label*='Add one more']",
      "button[aria-label*='Increase quantity']",
      "button[aria-label*='increment']",
      "button[data-automation-id='increment']"
    ];
    let plus = null;
    for (const selector of plusSelectors) {
      plus = candidate.card.querySelector(selector) || document.querySelector(selector);
      if (plus) break;
    }
    if (!plus || plus.disabled) break;
    plus.click();
  }
}

async function addAndAdvance(item, candidate) {
  const panel = document.getElementById(PANEL_ID);
  if (panel) {
    const body = panel.querySelector("#sw-body");
    body.innerHTML = "<div style='padding:10px;background:#eff6ff;border-radius:8px'>Adding product…</div>";
  }

  try {
    await clickPackageQuantity(candidate, item.packages || 1);
    await sleep(1300);
    await advance(item, candidate, "added");
  } catch (error) {
    if (panel) {
      const body = panel.querySelector("#sw-body");
      body.innerHTML = `<div style='padding:10px;background:#fef2f2;border-radius:8px'>Could not add automatically: ${escapeHtml(error.message)}. Add it manually, then choose Skip item.</div>`;
    }
  }
}

async function advance(item, candidate, status) {
  const record = {
    item_id: item.id,
    requested: item.name,
    status,
    selected_title: candidate ? candidate.title : "",
    selected_price: candidate ? candidate.price : null,
    selected_pickup: candidate ? candidate.pickup : false,
    timestamp: new Date().toISOString()
  };
  await chrome.runtime.sendMessage({ type: "ADVANCE_ITEM", record });
}

function renderCandidates(panel, item, candidates) {
  const body = panel.querySelector("#sw-body");
  if (!candidates.length) {
    body.innerHTML = `
      <div style="padding:11px;background:#fef2f2;border-radius:8px;font-size:13px">
        No confident addable product cards were found. Try changing the Walmart search, add an item manually, then choose Skip item.
      </div>`;
    return;
  }

  body.innerHTML = "";
  candidates.slice(0, 5).forEach((candidate, index) => {
    const row = document.createElement("div");
    row.style.cssText = "border:1px solid #e2e8f0;border-radius:10px;padding:10px;margin-bottom:8px";
    row.innerHTML = `
      <div style="font-size:13px;font-weight:700;line-height:1.3">${escapeHtml(candidate.title)}</div>
      <div style="font-size:12px;color:#475569;margin:5px 0">
        $${candidate.price.toFixed(2)} · Match ${Math.round(candidate.score * 100)}% · ${candidate.pickup ? "Pickup shown" : "Pickup not confirmed"}
      </div>
      <button data-choice="${index}" style="width:100%;padding:8px;border:0;border-radius:8px;background:#0071dc;color:white;font-weight:700;cursor:pointer">Add this product</button>
    `;
    row.querySelector("button").addEventListener("click", () => addAndAdvance(item, candidate));
    body.appendChild(row);
  });
}

async function processCurrentPage(force = false) {
  const state = await chrome.storage.local.get(["plan", "mode", "currentIndex", "running"]);
  if (!state.running || !state.plan || !Array.isArray(state.plan.items)) return;
  const index = state.currentIndex || 0;
  const item = state.plan.items[index];
  if (!item) return;

  if (!location.pathname.includes("/search")) return;

  if (!force) await sleep(1800);
  let candidates = rankCandidates(item);
  if (!candidates.length) {
    await sleep(1800);
    candidates = rankCandidates(item);
  }

  const mode = state.mode || state.plan.mode || "assisted";
  const strongCandidate = candidates.find(candidate => candidate.score >= 0.72 && candidate.pickup);
  if (mode === "auto" && strongCandidate) {
    const panel = panelBase(item, index, state.plan.items.length);
    panel.querySelector("#sw-body").innerHTML = `<div style='padding:10px;background:#ecfdf5;border-radius:8px'>Auto-selected: ${escapeHtml(strongCandidate.title)} for $${strongCandidate.price.toFixed(2)}</div>`;
    await addAndAdvance(item, strongCandidate);
    return;
  }

  const panel = panelBase(item, index, state.plan.items.length);
  renderCandidates(panel, item, candidates);
}

processCurrentPage();
