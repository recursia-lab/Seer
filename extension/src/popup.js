const dot = document.getElementById("dot");
const label = document.getElementById("status-label");
const detail = document.getElementById("status-detail");
const setupLink = document.getElementById("setup-link");
const rescanBtn = document.getElementById("rescan-btn");

async function checkDaemon() {
  try {
    const res = await fetch("http://127.0.0.1:11435/health", {
      signal: AbortSignal.timeout(2000),
    });
    if (res.ok) {
      const data = await res.json();
      dot.className = "dot ok";
      label.textContent = "Daemon running";
      detail.textContent = data.model || "PaliGemma2";
      setupLink.style.display = "none";
    } else {
      throw new Error("bad");
    }
  } catch {
    dot.className = "dot err";
    label.textContent = "Daemon not running";
    detail.textContent = "Start it to enable image descriptions";
    setupLink.style.display = "block";
  }
}

rescanBtn.addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.scripting.executeScript({
        target: { tabId: tabs[0].id },
        func: () => {
          // Re-trigger scan by removing processed markers
          document.querySelectorAll("img[data-seer-done]").forEach(img => {
            img.removeAttribute("data-seer-done");
          });
          // Dispatch custom event that content.js can listen to
          window.dispatchEvent(new CustomEvent("seer-rescan"));
        },
      });
    }
  });
  window.close();
});

checkDaemon();
