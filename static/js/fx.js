const SOUND_KEY = "bunutan.sound";
const GOLD = ["#f8d779", "#fff0b9", "#bb263b", "#1f754e"];
let audioContext;

export function prefersReducedMotion() {
  return document.documentElement.classList.contains("motion-reduced") ||
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function isSoundEnabled() {
  try { return localStorage.getItem(SOUND_KEY) === "on"; } catch { return false; }
}

export function setSoundEnabled(enabled) {
  try { localStorage.setItem(SOUND_KEY, enabled ? "on" : "off"); } catch { /* storage may be unavailable */ }
  return Boolean(enabled);
}

export function celebrate(preset = "trio", small = false) {
  if (prefersReducedMotion()) return;
  const fire = window.confetti;
  if (typeof fire !== "function") return;
  const count = small ? 35 : 48;
  const shared = { particleCount: count, spread: small ? 54 : 68, startVelocity: small ? 30 : 40, ticks: 145, colors: GOLD, disableForReducedMotion: true, zIndex: 80 };
  if (preset === "gold") {
    fire({ ...shared, particleCount: Math.min(150, count * 2), colors: ["#f6d16d", "#ffe9a4", "#fff8dc"] });
    return;
  }
  const palette = preset === "red" ? ["#be243b", "#f46b5e", "#ffe49a"] : preset === "green" ? ["#1c704c", "#5ec18b", "#ffe49a"] : GOLD;
  const sideCount = small ? 18 : 46;
  fire({ ...shared, particleCount: sideCount, angle: 60, origin: { x: 0, y: .75 }, colors: palette });
  fire({ ...shared, particleCount: sideCount, angle: 120, origin: { x: 1, y: .75 }, colors: palette });
  if (!small) fire({ ...shared, particleCount: 42, angle: 90, origin: { x: .5, y: .68 }, colors: palette });
}

export function playSound(kind = "blip") {
  if (!isSoundEnabled()) return;
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return;
  try {
    audioContext ||= new AudioContextClass();
    if (audioContext.state === "suspended") audioContext.resume();
    const notes = kind === "jingle" ? [660, 830, 990] : kind === "shuffle" ? [230, 310] : [540];
    const start = audioContext.currentTime;
    notes.forEach((frequency, index) => {
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      const when = start + index * (kind === "jingle" ? .11 : .07);
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(frequency, when);
      gain.gain.setValueAtTime(.0001, when);
      gain.gain.exponentialRampToValueAtTime(.055, when + .018);
      gain.gain.exponentialRampToValueAtTime(.0001, when + .14);
      oscillator.connect(gain).connect(audioContext.destination);
      oscillator.start(when);
      oscillator.stop(when + .15);
    });
  } catch { /* audio is optional */ }
}

export function showToast(message, duration = 2600) {
  const stack = document.getElementById("toast-stack");
  if (!stack || !message) return;
  const item = document.createElement("div");
  item.className = "toast";
  item.textContent = message;
  stack.append(item);
  window.setTimeout(() => item.remove(), duration);
}

export function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
