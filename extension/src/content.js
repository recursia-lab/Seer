/**
 * Seer content script
 * Scans the page for images without alt text and requests descriptions from local daemon.
 * Uses aria-live region to announce descriptions to screen readers.
 */

const SEER_DAEMON = "http://127.0.0.1:11435";
const MIN_SIZE_PX = 80;       // ignore icons smaller than 80x80
const PROCESSED_ATTR = "data-seer-done";

// Create hidden aria-live region for screen reader announcements
function ensureLiveRegion() {
  let region = document.getElementById("seer-live-region");
  if (!region) {
    region = document.createElement("div");
    region.id = "seer-live-region";
    region.setAttribute("role", "status");
    region.setAttribute("aria-live", "polite");
    region.setAttribute("aria-atomic", "true");
    region.style.cssText = "position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden";
    document.body.appendChild(region);
  }
  return region;
}

// Announce description via screen reader
function announce(text) {
  const region = ensureLiveRegion();
  region.textContent = "";
  // Must clear first, then set — otherwise screen readers may not re-announce
  setTimeout(() => { region.textContent = text; }, 100);
}

// Convert image URL to base64
async function imageToBase64(imgEl) {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement("canvas");
    const MAX = 512; // resize large images to save bandwidth to daemon
    let w = imgEl.naturalWidth || imgEl.width || 224;
    let h = imgEl.naturalHeight || imgEl.height || 224;
    if (w > MAX || h > MAX) {
      const scale = MAX / Math.max(w, h);
      w = Math.round(w * scale);
      h = Math.round(h * scale);
    }
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    try {
      ctx.drawImage(imgEl, 0, 0, w, h);
      const b64 = canvas.toDataURL("image/jpeg", 0.85).split(",")[1];
      resolve(b64);
    } catch (e) {
      reject(e); // cross-origin image — fall back to URL
    }
  });
}

// Request description from Seer daemon
async function getDescription(imgEl) {
  let payload = { task: "caption" };

  try {
    payload.image_b64 = await imageToBase64(imgEl);
  } catch {
    // Cross-origin image — send URL instead
    if (!imgEl.src || imgEl.src.startsWith("data:")) return null;
    payload.image_url = imgEl.src;
  }

  const resp = await fetch(`${SEER_DAEMON}/describe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) return null;
  const data = await resp.json();
  return data.description || null;
}

// Check if an image needs a description
function needsDescription(img) {
  if (img.hasAttribute(PROCESSED_ATTR)) return false;
  if (!img.src && !img.srcset) return false;
  if (img.src.startsWith("data:image/")) return false; // inline tiny icons

  const alt = (img.getAttribute("alt") || "").trim();
  if (alt.length > 0) return false; // already has alt text

  const role = img.getAttribute("role");
  if (role === "presentation" || role === "none") return false;

  // Size filter: skip tiny icons
  const w = img.offsetWidth || img.naturalWidth;
  const h = img.offsetHeight || img.naturalHeight;
  if (w > 0 && h > 0 && (w < MIN_SIZE_PX || h < MIN_SIZE_PX)) return false;

  return true;
}

// Process a single image
async function processImage(img) {
  if (!needsDescription(img)) return;
  img.setAttribute(PROCESSED_ATTR, "pending");

  try {
    const desc = await getDescription(img);
    if (desc) {
      img.setAttribute("alt", desc);
      img.setAttribute(PROCESSED_ATTR, "done");
      announce(`Image: ${desc}`);
    } else {
      img.setAttribute(PROCESSED_ATTR, "failed");
    }
  } catch {
    img.setAttribute(PROCESSED_ATTR, "failed");
  }
}

// Scan entire page on load
async function scanPage() {
  // Check daemon is alive first
  try {
    const health = await fetch(`${SEER_DAEMON}/health`, { signal: AbortSignal.timeout(2000) });
    if (!health.ok) return;
  } catch {
    return; // Daemon not running — silent fail
  }

  const images = Array.from(document.querySelectorAll("img"));
  for (const img of images) {
    if (needsDescription(img)) {
      // Process sequentially to avoid hammering the daemon
      processImage(img);
    }
  }
}

// Watch for dynamically added images
const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    for (const node of mutation.addedNodes) {
      if (node.nodeType !== 1) continue;
      if (node.tagName === "IMG") processImage(node);
      node.querySelectorAll?.("img").forEach(processImage);
    }
  }
});

// Start
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    scanPage();
    observer.observe(document.body, { childList: true, subtree: true });
  });
} else {
  scanPage();
  observer.observe(document.body, { childList: true, subtree: true });
}
