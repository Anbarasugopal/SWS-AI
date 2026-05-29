const thread = document.querySelector("#thread");
const form = document.querySelector("#chat-form");
const textarea = document.querySelector("#question");
const sendButton = document.querySelector("#send-button");
const healthPill = document.querySelector("#health-pill");
const sourceList = document.querySelector("#source-list");
const docCount = document.querySelector("#doc-count");
const uploadForm = document.querySelector("#upload-form");
const uploadInput = document.querySelector("#document-upload");
const uploadButton = document.querySelector("#upload-button");
const uploadLabel = document.querySelector("#upload-label");
const uploadStatus = document.querySelector("#upload-status");

const noInfoText = "I don't have that information in the company documents.";

function initIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function appendMessage(role, content, sources = []) {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const sourceMarkup = sources.length
    ? `<div class="source-strip">${sources
        .map((source) => {
          const page = source.page ? ` p.${source.page}` : "";
          return `<span class="source-chip">${escapeHtml(source.title)}${page}</span>`;
        })
        .join("")}</div>`
    : "";

  article.innerHTML = `
    <div class="bubble">
      <p>${escapeHtml(content).replaceAll("\n", "<br />")}</p>
      ${sourceMarkup}
    </div>
  `;
  thread.appendChild(article);
  thread.scrollTop = thread.scrollHeight;
  return article;
}

function appendLoading() {
  const article = document.createElement("article");
  article.className = "message assistant";
  article.innerHTML = `
    <div class="bubble">
      <div class="typing" aria-label="Assistant is typing">
        <span></span><span></span><span></span>
      </div>
    </div>
  `;
  thread.appendChild(article);
  thread.scrollTop = thread.scrollHeight;
  return article;
}

function setUploadStatus(message, type = "") {
  uploadStatus.textContent = message;
  uploadStatus.className = `upload-status ${type}`.trim();
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const health = await response.json();
    healthPill.textContent = health.chunk_count
      ? `${health.chunk_count} chunks indexed`
      : "Index is empty";
    healthPill.classList.toggle("empty", !health.chunk_count);
  } catch {
    healthPill.textContent = "API unavailable";
    healthPill.classList.add("empty");
  }
}

async function loadSources() {
  try {
    const response = await fetch("/api/sources");
    const sources = await response.json();
    docCount.textContent = `${sources.length} files`;
    sourceList.innerHTML = sources
      .map(
        (source) => `
          <div class="doc-row">
            <div>
              <strong>${escapeHtml(source.title)}</strong>
              <span>${source.pages.length} page${source.pages.length === 1 ? "" : "s"} | ${source.chunks} chunks</span>
            </div>
          </div>
        `
      )
      .join("");
  } catch {
    docCount.textContent = "Unavailable";
    sourceList.innerHTML = "";
  }
}

async function uploadDocument() {
  const file = uploadInput.files?.[0];
  if (!file) {
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  uploadButton.disabled = true;
  setUploadStatus("Uploading and indexing...");

  try {
    const response = await fetch("/api/documents", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Could not upload the PDF.");
    }

    const payload = await response.json();
    setUploadStatus(`Indexed ${payload.document.title}`, "success");
    uploadInput.value = "";
    uploadLabel.textContent = "Choose PDF";
    await Promise.all([loadHealth(), loadSources()]);
  } catch (error) {
    setUploadStatus(error.message || "Could not upload the PDF.", "error");
    uploadButton.disabled = false;
  }
}

async function ask(question) {
  appendMessage("user", question);
  textarea.value = "";
  textarea.style.height = "auto";
  sendButton.disabled = true;
  const loading = appendLoading();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "The assistant could not answer right now.");
    }

    const payload = await response.json();
    loading.remove();
    const sources = payload.answer === noInfoText ? [] : payload.sources;
    appendMessage("assistant", payload.answer, sources);
  } catch (error) {
    loading.remove();
    appendMessage("assistant", error.message || "Something went wrong while answering.");
  } finally {
    sendButton.disabled = false;
    textarea.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = textarea.value.trim();
  if (question) {
    ask(question);
  }
});

uploadInput.addEventListener("change", () => {
  const file = uploadInput.files?.[0];
  uploadButton.disabled = !file;
  uploadLabel.textContent = file ? file.name : "Choose PDF";
  setUploadStatus("");
});

uploadForm.addEventListener("submit", (event) => {
  event.preventDefault();
  uploadDocument();
});

textarea.addEventListener("input", () => {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
});

textarea.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    textarea.value = button.textContent.trim();
    form.requestSubmit();
  });
});

document.addEventListener("DOMContentLoaded", () => {
  initIcons();
  loadHealth();
  loadSources();
});
