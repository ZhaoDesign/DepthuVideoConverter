const repo = window.__QUEUE_REPO__ || "ZhaoDesign/DepthuVideoConverter";
const issueBaseUrl = `https://github.com/${repo}/issues/new`;
const actionRunsUrl = `https://github.com/${repo}/actions`;
const maxAttachmentBytes = 10 * 1024 * 1024;

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const fileCard = document.getElementById("file-card");
const fileName = document.getElementById("file-name");
const fileMeta = document.getElementById("file-meta");
const clearFile = document.getElementById("clear-file");
const sourceUrl = document.getElementById("source-url");
const sourceNotice = document.getElementById("source-notice");
const model = document.getElementById("model");
const resolution = document.getElementById("resolution");
const smoothing = document.getElementById("smoothing");
const smoothingValue = document.getElementById("smoothing-value");
const preserveAudio = document.getElementById("preserve-audio");
const invert = document.getElementById("invert");
const startJob = document.getElementById("start-job");
const copyBlock = document.getElementById("copy-block");
const queueStatus = document.getElementById("queue-status");
const queueList = document.getElementById("queue-list");
const queueBlock = document.getElementById("queue-block");
const issueHint = document.getElementById("issue-hint");

let selectedFile = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function isVideoFile(file) {
  const suffix = file.name.toLowerCase().split(".").pop();
  return file.type.startsWith("video/") || ["mp4", "mov", "m4v", "webm", "mkv"].includes(suffix);
}

function setNotice(message, state = "warn") {
  sourceNotice.textContent = message;
  sourceNotice.classList.toggle("is-error", state === "error");
  sourceNotice.classList.toggle("is-ok", state === "ok");
}

function sourceValue() {
  const pastedUrl = sourceUrl.value.trim();
  return pastedUrl || "attachment";
}

function buildQueueBlock() {
  return [
    "```queue",
    `source=${sourceValue()}`,
    `model=${model.value}`,
    `resolution=${resolution.value}`,
    `invert=${invert.checked}`,
    `smoothing=${smoothing.value}`,
    `preserve_audio=${preserveAudio.checked}`,
    "```",
  ].join("\n");
}

function buildIssueBody() {
  const lines = [
    "Queue job generated from the GitHub Pages upload screen.",
    "",
    buildQueueBlock(),
    "",
  ];

  if (sourceValue() === "attachment") {
    lines.push("Attach the selected video file to this issue body before submitting.");
  } else {
    lines.push("The worker will download the public HTTPS video URL from the queue block.");
  }

  return lines.join("\n");
}

function updateQueueBlock() {
  queueBlock.textContent = buildQueueBlock();

  if (sourceValue() !== "attachment") {
    issueHint.textContent = "The issue will be prefilled with this public URL.";
    setNotice("Public URL mode is ready. Start the job and submit the GitHub issue.", "ok");
    return;
  }

  if (!selectedFile) {
    issueHint.textContent = "Drop a file or paste a public URL.";
    setNotice("Choose a small local file, or use a public HTTPS video URL for larger files.");
    return;
  }

  if (selectedFile.size > maxAttachmentBytes) {
    issueHint.textContent = "This file is too large for GitHub issue upload.";
    setNotice("This file is over 10 MB. Use a public HTTPS video URL instead.", "error");
    return;
  }

  issueHint.textContent = "GitHub will open with the queue block filled in.";
  setNotice("File selected. Start the job, then drag this file into the GitHub issue editor before submitting.", "ok");
}

function showFile(file) {
  selectedFile = file;
  fileName.textContent = file.name;
  fileMeta.textContent = `${formatBytes(file.size)} | ${file.type || "video file"}`;
  fileCard.hidden = false;
  dropzone.classList.toggle("is-invalid", file.size > maxAttachmentBytes || !isVideoFile(file));

  if (!isVideoFile(file)) {
    setNotice("This does not look like a supported video file.", "error");
  } else if (file.size > maxAttachmentBytes) {
    setNotice("This file is over 10 MB. Use a public HTTPS video URL instead.", "error");
  } else {
    sourceUrl.value = "";
  }

  updateQueueBlock();
}

function clearSelectedFile() {
  selectedFile = null;
  fileInput.value = "";
  fileCard.hidden = true;
  dropzone.classList.remove("is-invalid");
  updateQueueBlock();
}

function issueTitle() {
  if (selectedFile) {
    return `[queue] ${selectedFile.name}`;
  }
  return "[queue] video conversion";
}

function openIssue() {
  if (sourceValue() === "attachment") {
    if (!selectedFile) {
      fileInput.click();
      return;
    }

    if (!isVideoFile(selectedFile)) {
      setNotice("Use an MP4, MOV, M4V, or WEBM file.", "error");
      return;
    }

    if (selectedFile.size > maxAttachmentBytes) {
      setNotice("This file is over 10 MB. Paste a public HTTPS video URL instead.", "error");
      return;
    }
  }

  const params = new URLSearchParams({
    title: issueTitle(),
    body: buildIssueBody(),
  });

  window.open(`${issueBaseUrl}?${params.toString()}`, "_blank", "noopener,noreferrer");
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

dropzone.addEventListener("dragenter", (event) => {
  event.preventDefault();
  dropzone.classList.add("is-dragging");
});

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("is-dragging");
});

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("is-dragging");
  const file = event.dataTransfer.files?.[0];
  if (file) {
    showFile(file);
  }
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  if (file) {
    showFile(file);
  }
});

clearFile.addEventListener("click", clearSelectedFile);

sourceUrl.addEventListener("input", () => {
  if (sourceUrl.value.trim()) {
    clearSelectedFile();
  }
  updateQueueBlock();
});

[model, resolution, smoothing, preserveAudio, invert].forEach((control) => {
  control.addEventListener("input", () => {
    smoothingValue.textContent = smoothing.value;
    updateQueueBlock();
  });
});

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

startJob.addEventListener("click", openIssue);

document.querySelector('[href$="/actions"]').href = actionRunsUrl;
updateQueueBlock();
loadQueue();
setInterval(loadQueue, 60000);
