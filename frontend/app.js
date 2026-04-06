/* ── Smart Photo Filter – client-side logic ────────────────────────────────
   Базовые фильтры применяются через OpenCV.js на клиенте.
   Умные операции отправляются на Flask-сервер (/api/process).
   ───────────────────────────────────────────────────────────────────────── */

const API_BASE = "http://localhost:5000";

// DOM refs
const fileInput      = document.getElementById("fileInput");
const dropzone       = document.getElementById("dropzone");
const canvasSection  = document.getElementById("canvasSection");
const originalCanvas = document.getElementById("originalCanvas");
const resultCanvas   = document.getElementById("resultCanvas");
const spinner        = document.getElementById("spinner");
const downloadBtn    = document.getElementById("downloadBtn");
const resetBtn       = document.getElementById("resetBtn");

// State
let originalFile  = null;   // File object kept for server requests
let cvReady       = false;  // OpenCV.js loaded flag

// ── OpenCV ready callback (called by onload in <script>) ──────────────────
function onOpenCvReady() {
  cvReady = true;
  console.log("OpenCV.js ready");
}

// ── File handling ─────────────────────────────────────────────────────────
fileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) loadImage(file);
});

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag-over");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) loadImage(file);
});
dropzone.addEventListener("click", (e) => {
  if (e.target.tagName !== "LABEL") fileInput.click();
});

function loadImage(file) {
  originalFile = file;
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.onload = () => {
    // Draw original
    drawToCanvas(img, originalCanvas);
    // Mirror to result
    drawToCanvas(img, resultCanvas);
    // Show UI
    canvasSection.hidden = false;
    downloadBtn.disabled = false;
    URL.revokeObjectURL(url);
  };
  img.src = url;
}

function drawToCanvas(imgEl, canvas) {
  const maxW = canvas.parentElement.clientWidth || 600;
  const ratio = imgEl.naturalHeight / imgEl.naturalWidth;
  canvas.width  = Math.min(imgEl.naturalWidth,  maxW);
  canvas.height = Math.round(canvas.width * ratio);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(imgEl, 0, 0, canvas.width, canvas.height);
}

// ── Basic filters (client-side via OpenCV.js) ─────────────────────────────
document.querySelectorAll(".btn-basic").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (!cvReady) { alert("OpenCV.js ещё загружается, подождите секунду."); return; }
    if (!originalFile) return;
    applyClientFilter(btn.dataset.filter);
  });
});

function applyClientFilter(filter) {
  const src = cv.imread(originalCanvas);
  let dst = new cv.Mat();

  try {
    switch (filter) {
      case "grayscale":
        cv.cvtColor(src, dst, cv.COLOR_RGBA2GRAY);
        cv.cvtColor(dst, dst, cv.COLOR_GRAY2RGBA);
        break;

      case "invert":
        dst = src.clone();
        // Invert only RGB channels, keep alpha
        for (let i = 0; i < dst.rows; i++) {
          for (let j = 0; j < dst.cols; j++) {
            const px = dst.ucharPtr(i, j);
            px[0] = 255 - px[0];
            px[1] = 255 - px[1];
            px[2] = 255 - px[2];
          }
        }
        break;

      case "blur":
        cv.GaussianBlur(src, dst, new cv.Size(21, 21), 0, 0, cv.BORDER_DEFAULT);
        break;

      default:
        src.copyTo(dst);
    }

    // Resize result canvas to match original canvas
    resultCanvas.width  = originalCanvas.width;
    resultCanvas.height = originalCanvas.height;
    cv.imshow(resultCanvas, dst);
    downloadBtn.disabled = false;
  } finally {
    src.delete();
    dst.delete();
  }
}

// ── Smart operations (server-side) ────────────────────────────────────────
document.querySelectorAll(".btn-smart").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (!originalFile) return;
    sendToServer(btn.dataset.op);
  });
});

async function sendToServer(operation) {
  setSpinner(true);
  disableAllButtons(true);

  const formData = new FormData();
  formData.append("image", originalFile);
  formData.append("operation", operation);

  try {
    const response = await fetch(`${API_BASE}/api/process`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(err.error || "Server error");
    }

    const blob = await response.blob();
    const url  = URL.createObjectURL(blob);
    const img  = new Image();
    img.onload = () => {
      drawToCanvas(img, resultCanvas);
      URL.revokeObjectURL(url);
      downloadBtn.disabled = false;
    };
    img.src = url;
  } catch (err) {
    alert(`Ошибка: ${err.message}\n\nПроверьте, что сервер запущен на localhost:5000`);
    console.error(err);
  } finally {
    setSpinner(false);
    disableAllButtons(false);
  }
}

// ── Reset ─────────────────────────────────────────────────────────────────
resetBtn.addEventListener("click", () => {
  if (!originalFile) return;
  const img = new Image();
  const url = URL.createObjectURL(originalFile);
  img.onload = () => {
    drawToCanvas(img, resultCanvas);
    URL.revokeObjectURL(url);
  };
  img.src = url;
});

// ── Download ──────────────────────────────────────────────────────────────
downloadBtn.addEventListener("click", () => {
  const link = document.createElement("a");
  link.download = "result.png";
  link.href = resultCanvas.toDataURL("image/png");
  link.click();
});

// ── Helpers ───────────────────────────────────────────────────────────────
function setSpinner(show) {
  spinner.hidden = !show;
}

function disableAllButtons(state) {
  document.querySelectorAll(".btn-basic, .btn-smart, .btn-reset").forEach((b) => {
    b.disabled = state;
  });
}
