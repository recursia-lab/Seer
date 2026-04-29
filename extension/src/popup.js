const dot = document.getElementById("status-dot");
const text = document.getElementById("status-text");

async function checkDaemon() {
  try {
    const res = await fetch("http://127.0.0.1:11435/health", {
      signal: AbortSignal.timeout(2000),
    });
    if (res.ok) {
      const data = await res.json();
      dot.className = "dot ok";
      text.textContent = `Running — ${data.model}`;
    } else {
      throw new Error("bad status");
    }
  } catch {
    dot.className = "dot err";
    text.textContent = "Daemon not running. Start it first.";
  }
}

checkDaemon();
