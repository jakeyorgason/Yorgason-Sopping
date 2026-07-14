const fileInput = document.getElementById("cartFile");
const modeSelect = document.getElementById("mode");
const summary = document.getElementById("summary");
const status = document.getElementById("status");
const startButton = document.getElementById("start");
const resetButton = document.getElementById("reset");
const openCartButton = document.getElementById("openCart");

function isValidPlan(plan) {
  return plan && plan.version === 1 && Array.isArray(plan.items) && plan.items.length > 0;
}

function renderState(state) {
  if (!state.plan) {
    summary.textContent = "No cart file imported.";
    startButton.disabled = true;
    return;
  }

  const count = state.plan.items.length;
  const current = Number.isInteger(state.currentIndex) ? state.currentIndex : 0;
  const mode = state.mode || state.plan.mode || "assisted";
  modeSelect.value = mode;
  summary.textContent = `${count} item(s) loaded. Progress: ${Math.min(current, count)} / ${count}.`;
  startButton.disabled = false;
  startButton.textContent = state.running ? "Resume current run" : "Start on Walmart";

  if (state.lastMessage) {
    status.textContent = state.lastMessage;
  } else if (state.running) {
    status.textContent = "Run active. Follow the review panel on the Walmart page.";
  } else {
    status.textContent = "Ready.";
  }
}

async function loadState() {
  const state = await chrome.storage.local.get([
    "plan",
    "mode",
    "currentIndex",
    "running",
    "lastMessage"
  ]);
  renderState(state);
}

fileInput.addEventListener("change", async () => {
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;

  try {
    const raw = await file.text();
    const plan = JSON.parse(raw);
    if (!isValidPlan(plan)) {
      throw new Error("This is not a valid version 1 cart file.");
    }

    const selectedMode = plan.mode === "auto" ? "auto" : "assisted";
    await chrome.storage.local.set({
      plan,
      mode: selectedMode,
      currentIndex: 0,
      running: false,
      history: [],
      lastMessage: `Imported ${plan.items.length} item(s).`
    });
    await loadState();
  } catch (error) {
    status.textContent = `Import failed: ${error.message}`;
  }
});

modeSelect.addEventListener("change", async () => {
  await chrome.storage.local.set({ mode: modeSelect.value });
  await loadState();
});

startButton.addEventListener("click", async () => {
  const state = await chrome.storage.local.get(["plan", "currentIndex"]);
  if (!isValidPlan(state.plan)) return;

  if ((state.currentIndex || 0) >= state.plan.items.length) {
    await chrome.storage.local.set({ currentIndex: 0, history: [] });
  }
  await chrome.storage.local.set({
    running: true,
    mode: modeSelect.value,
    lastMessage: "Opening the first Walmart search…"
  });
  await chrome.runtime.sendMessage({ type: "NAVIGATE_CURRENT" });
  window.close();
});

resetButton.addEventListener("click", async () => {
  await chrome.storage.local.clear();
  fileInput.value = "";
  await loadState();
});

openCartButton.addEventListener("click", async () => {
  await chrome.tabs.create({ url: "https://www.walmart.com/cart" });
});

chrome.storage.onChanged.addListener(() => loadState());
loadState();
