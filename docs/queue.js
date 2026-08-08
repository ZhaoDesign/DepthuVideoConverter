const repo = window.__QUEUE_REPO__ || "ZhaoDesign/DepthuVideoConverter";
const templateUrl = `https://github.com/${repo}/issues/new?template=video-convert.md`;
const openTemplate = document.getElementById("open-template");
const copyBlock = document.getElementById("copy-block");
const queueStatus = document.getElementById("queue-status");
const queueList = document.getElementById("queue-list");
const queueBlock = document.getElementById("queue-block");

openTemplate.href = templateUrl;

copyBlock.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(queueBlock.textContent.trim());
    copyBlock.textContent = "Copied";
    setTimeout(() => {
      copyBlock.textContent = "Copy queue block";
    }, 1200);
  } catch {
    copyBlock.textContent = "Copy failed";
  }
});

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderItems(items) {
  if (!items.length) {
    queueList.innerHTML = '<div class="queue-item"><div class="queue-title">No open jobs</div><div class="queue-meta status-ok">Queue is empty</div></div>';
    return;
  }

  queueList.innerHTML = items.slice(0, 8).map((item) => {
    const title = item.title || `Issue #${item.number}`;
    const state = item.state === "open" ? "waiting" : item.state;
    return `
      <div class="queue-item">
        <div>
          <div class="queue-title">#${item.number} ${escapeHtml(title)}</div>
          <div class="queue-meta">${escapeHtml(item.user?.login || "unknown")} | ${escapeHtml(state)}</div>
        </div>
        <div class="queue-meta">
          <a href="${item.html_url}" target="_blank" rel="noreferrer">Open issue</a>
        </div>
      </div>
    `;
  }).join("");
}

async function loadQueue() {
  const url = `https://api.github.com/repos/${repo}/issues?state=open&labels=queue-video&per_page=100&sort=created&direction=asc`;
  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    });

    if (!response.ok) {
      throw new Error(`GitHub API returned ${response.status}`);
    }

    const items = await response.json();
    queueStatus.textContent = `${items.length} open queue issue${items.length === 1 ? "" : "s"}. GitHub Actions processes them one at a time.`;
    renderItems(items);
  } catch (error) {
    queueStatus.textContent = "Queue status unavailable from GitHub right now.";
    queueList.innerHTML = `<div class="queue-item"><div class="queue-title">API error</div><div class="queue-meta">${escapeHtml(error.message)}</div></div>`;
  }
}

loadQueue();
setInterval(loadQueue, 60000);
