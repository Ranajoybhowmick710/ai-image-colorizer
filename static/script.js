/* ═══════════════════════════════════════════════════════
   Chromify – script.js
   Stable, pointer-events-based compare slider + UI polish
═══════════════════════════════════════════════════════ */

// ── Cursor glow ────────────────────────────────────────
const dot  = document.getElementById("cursor-dot");
const ring = document.getElementById("cursor-ring");

let mouseX = 0, mouseY = 0;
let ringX  = 0, ringY  = 0;

document.addEventListener("mousemove", (e) => {
  mouseX = e.clientX;
  mouseY = e.clientY;

  if (dot) {
    dot.style.left = mouseX + "px";
    dot.style.top  = mouseY + "px";
  }
});

// Smooth ring lag via rAF
function animateRing() {
  ringX += (mouseX - ringX) * 0.12;
  ringY += (mouseY - ringY) * 0.12;

  if (ring) {
    ring.style.left = ringX + "px";
    ring.style.top  = ringY + "px";
  }
  requestAnimationFrame(animateRing);
}
animateRing();

// ── Drag & drop ────────────────────────────────────────
function onDrag(e) {
  e.preventDefault();
  document.getElementById("dropzone").classList.add("drag-over");
}

function onDragLeave(e) {
  document.getElementById("dropzone").classList.remove("drag-over");
}

function onDrop(e) {
  e.preventDefault();
  document.getElementById("dropzone").classList.remove("drag-over");

  const file = e.dataTransfer.files[0];
  if (!file) return;

  const input = document.getElementById("fileInput");
  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;

  previewImage(input);
}

// ── Image preview ──────────────────────────────────────
function previewImage(input) {
  const file = input.files[0];
  if (!file) return;

  const nameEl = document.getElementById("fileName");
  if (nameEl) nameEl.textContent = "✓  " + file.name;

  const url = URL.createObjectURL(file);
  const img = document.getElementById("previewImg");
  const section = document.getElementById("previewSection");

  if (img && section) {
    img.src = url;
    section.style.display = "block";
    section.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Visually activate the drop zone
  const dz = document.getElementById("dropzone");
  if (dz) dz.classList.add("has-file");
}

// ── Loader / progress ──────────────────────────────────
const STAGES = [
  { at:  0, label: "Uploading image…"         },
  { at: 20, label: "Analysing tones…"         },
  { at: 40, label: "Predicting colours…"      },
  { at: 65, label: "Applying AI palette…"     },
  { at: 80, label: "Boosting saturation…"     },
  { at: 92, label: "Finalising result…"       },
];

function handleSubmit(e) {
  const input = document.getElementById("fileInput");
  if (!input || !input.files.length) return false;

  showLoader();
  return true; // let the form submit
}

function showLoader() {
  const loader = document.getElementById("loader");
  const fill   = document.getElementById("progressFill");
  const label  = document.getElementById("loaderLabel");
  const btn    = document.getElementById("colorizeBtn");

  if (loader) loader.style.display = "flex";
  if (btn)    btn.disabled = true;

  let progress  = 0;
  let stageIdx  = 0;

  const interval = setInterval(() => {
    // Slow down near the end so it never reaches 100 before redirect
    const speed = progress < 70 ? (8 + Math.random() * 10) : (1 + Math.random() * 3);
    progress = Math.min(progress + speed, 96);

    if (fill) fill.style.width = progress + "%";

    // Update stage label
    for (let i = STAGES.length - 1; i >= 0; i--) {
      if (progress >= STAGES[i].at) {
        if (stageIdx !== i) {
          stageIdx = i;
          if (label) {
            label.classList.add("fade");
            setTimeout(() => {
              label.textContent = STAGES[i].label;
              label.classList.remove("fade");
            }, 150);
          }
        }
        break;
      }
    }

    if (progress >= 96) clearInterval(interval);
  }, 280);
}

// ── Dark mode ──────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem("chromify-theme");
  if (saved === "dark") {
    document.body.classList.add("dark");
    const icon = document.getElementById("themeIcon");
    if (icon) icon.textContent = "☽";
  }
})();

function toggleDark() {
  const isDark = document.body.classList.toggle("dark");
  localStorage.setItem("chromify-theme", isDark ? "dark" : "light");
  const icon = document.getElementById("themeIcon");
  if (icon) icon.textContent = isDark ? "☽" : "☀";
}

// ── Compare slider ─────────────────────────────────────
// Uses pointer events for solid mouse + touch support
window.addEventListener("load", () => {
  const box     = document.getElementById("compareBox");
  if (!box) return;

  const wrapper = document.getElementById("afterWrapper");
  const handle  = document.getElementById("sliderHandle");

  let isDragging = false;

  function setPosition(clientX) {
    const rect = box.getBoundingClientRect();
    let x = clientX - rect.left;
    x = Math.max(0, Math.min(x, rect.width));
    const pct = (x / rect.width) * 100;

    wrapper.style.width        = pct + "%";
    handle.style.left          = pct + "%";
  }

  // Initialise at 50%
  setPosition(box.getBoundingClientRect().left + box.getBoundingClientRect().width * 0.5);

  // Pointer events (covers mouse + touch + stylus)
  handle.addEventListener("pointerdown", (e) => {
    isDragging = true;
    handle.setPointerCapture(e.pointerId);
    box.classList.add("dragging");
  });

  handle.addEventListener("pointermove", (e) => {
    if (!isDragging) return;
    setPosition(e.clientX);
  });

  handle.addEventListener("pointerup", () => {
    isDragging = false;
    box.classList.remove("dragging");
  });

  // Also allow dragging anywhere in the box (not just the handle)
  box.addEventListener("pointermove", (e) => {
    if (!isDragging) return;
    setPosition(e.clientX);
  });

  box.addEventListener("pointerdown", (e) => {
    // Only activate drag when clicking the box itself (not the handle)
    if (e.target === handle || handle.contains(e.target)) return;
    isDragging = true;
    box.setPointerCapture(e.pointerId);
    setPosition(e.clientX);
  });

  box.addEventListener("pointerup", () => {
    isDragging = false;
    box.classList.remove("dragging");
  });
});