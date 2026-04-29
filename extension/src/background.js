/**
 * Seer background service worker
 * Handles extension lifecycle and settings.
 */

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({
    enabled: true,
    daemonPort: 11435,
    minImageSize: 80,
  });
});
