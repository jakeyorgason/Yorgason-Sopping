async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

async function navigateCurrent() {
  const state = await chrome.storage.local.get(["plan", "currentIndex", "running"]);
  const plan = state.plan;
  const index = state.currentIndex || 0;

  if (!state.running || !plan || !Array.isArray(plan.items)) return;

  if (index >= plan.items.length) {
    await chrome.storage.local.set({
      running: false,
      lastMessage: "Finished. Review your Walmart cart before checkout."
    });
    const tab = await getActiveTab();
    if (tab && tab.id) {
      await chrome.tabs.update(tab.id, { url: "https://www.walmart.com/cart" });
    } else {
      await chrome.tabs.create({ url: "https://www.walmart.com/cart" });
    }
    return;
  }

  const item = plan.items[index];
  const query = item.search_query || item.name;
  const url = `https://www.walmart.com/search?q=${encodeURIComponent(query)}`;
  const tab = await getActiveTab();

  await chrome.storage.local.set({
    lastMessage: `Searching ${index + 1} of ${plan.items.length}: ${item.name}`
  });

  if (tab && tab.id) {
    await chrome.tabs.update(tab.id, { url });
  } else {
    await chrome.tabs.create({ url });
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "NAVIGATE_CURRENT") {
    navigateCurrent().then(() => sendResponse({ ok: true }));
    return true;
  }

  if (message.type === "ADVANCE_ITEM") {
    (async () => {
      const state = await chrome.storage.local.get(["currentIndex", "history"]);
      const nextIndex = (state.currentIndex || 0) + 1;
      const history = Array.isArray(state.history) ? state.history : [];
      if (message.record) history.push(message.record);
      await chrome.storage.local.set({ currentIndex: nextIndex, history });
      await navigateCurrent();
      sendResponse({ ok: true });
    })();
    return true;
  }

  if (message.type === "STOP_RUN") {
    chrome.storage.local.set({ running: false, lastMessage: "Run paused." })
      .then(() => sendResponse({ ok: true }));
    return true;
  }

  return false;
});
