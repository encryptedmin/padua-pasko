import { isSoundEnabled, setSoundEnabled } from "./fx.js";

const MOTION_KEY = "bunutan.motion";
const root = document.documentElement;
const motionButton = document.getElementById("motion-toggle");
const soundButton = document.getElementById("sound-toggle");
const systemReduced = window.matchMedia?.("(prefers-reduced-motion: reduce)");

function motionSetting() {
  try { return localStorage.getItem(MOTION_KEY); } catch { return null; }
}

function updateMotionLabel() {
  const saved = motionSetting();
  const reduced = saved === "reduced" || (saved !== "full" && Boolean(systemReduced?.matches));
  root.classList.toggle("motion-reduced", reduced);
  if (motionButton) {
    motionButton.setAttribute("aria-pressed", String(reduced));
    motionButton.textContent = saved ? (reduced ? "Motion: less" : "Motion: full") : "Motion: auto";
    motionButton.setAttribute("aria-label", reduced ? "Reduced motion enabled" : "Use reduced motion");
  }
  if (window.gsap?.globalTimeline) window.gsap.globalTimeline.paused(document.hidden || reduced);
}

function updateSoundLabel() {
  const enabled = isSoundEnabled();
  if (!soundButton) return;
  soundButton.textContent = enabled ? "🔊" : "🔇";
  soundButton.title = enabled ? "Sound on" : "Sound off";
  soundButton.setAttribute("aria-pressed", String(enabled));
  soundButton.setAttribute("aria-label", enabled ? "Turn sound effects off" : "Turn sound effects on");
}

motionButton?.addEventListener("click", () => {
  const reduced = root.classList.contains("motion-reduced");
  try { localStorage.setItem(MOTION_KEY, reduced ? "full" : "reduced"); } catch { /* preference is optional */ }
  updateMotionLabel();
});
soundButton?.addEventListener("click", () => {
  setSoundEnabled(!isSoundEnabled());
  updateSoundLabel();
});
systemReduced?.addEventListener?.("change", () => { if (!motionSetting()) updateMotionLabel(); });
document.addEventListener("visibilitychange", () => {
  document.body.classList.toggle("tab-hidden", document.hidden);
  if (window.gsap?.globalTimeline) window.gsap.globalTimeline.paused(document.hidden || root.classList.contains("motion-reduced"));
});
updateMotionLabel();
updateSoundLabel();
