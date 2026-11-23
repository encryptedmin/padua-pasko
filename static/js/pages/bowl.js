import { apiGet, apiPost } from "../api.js";
import { celebrate, playSound, prefersReducedMotion, wait } from "../fx.js";
import { bindHoldReveal } from "../reveal.js";
import { copyText, readIdentity, saveIdentity } from "../storage.js";

export function init() {
  const stage = document.getElementById("bowl-stage");
  const waiting = document.getElementById("waiting-state");
  const scene = document.getElementById("bowl-scene");
  const field = document.getElementById("slip-field");
  const drawButton = document.getElementById("draw-button");
  const shakeButton = document.getElementById("shake-button");
  const drawError = document.getElementById("draw-error");
  const drawCard = document.getElementById("draw-card");
  const countdown = document.getElementById("countdown");
  const flipCard = document.getElementById("flip-card");
  const holdButton = document.getElementById("hold-reveal");
  const toggleButton = document.getElementById("accessibility-reveal-toggle");
  const hideButton = document.getElementById("hide-result-button");
  const resultElement = document.getElementById("draw-result");
  const recoveryBox = document.getElementById("recovery-key-box");
  const recoveryOutput = document.getElementById("recovery-key");
  const participantId = Number(document.getElementById("participant-id")?.value) || null;
  const remainingCount = document.getElementById("remaining-count");
  const budget = document.getElementById("bowl-budget")?.textContent || "";
  const keyStatus = document.getElementById("copy-key-status");
  let secretName = "";
  let busy = false;
  let polling = 0;

  if (!stage || !waiting || !drawButton || !field) return;

  function renderSlips(count) {
    const total = Math.max(0, Number(count) || 0);
    field.replaceChildren();
    for (let index = 0; index < total; index += 1) {
      const slip = document.createElement("span");
      slip.className = "paper-slip";
      slip.style.left = `${8 + ((index * 37) % 84)}%`;
      slip.style.top = `${12 + ((index * 23) % 70)}%`;
      slip.style.animationDelay = `${-((index * 137) % 1200)}ms`;
      field.append(slip);
    }
    if (remainingCount) remainingCount.textContent = String(count ?? 0);
  }

  async function updateState() {
    try {
      const state = await apiGet("/api/state");
      renderSlips(state.remaining);
      if (state.budget_text) document.getElementById("bowl-budget").textContent = state.budget_text;
      if (state.status === "OPEN") {
        waiting.hidden = true;
        stage.hidden = false;
        window.clearInterval(polling);
      } else {
        waiting.hidden = false;
        stage.hidden = true;
      }
    } catch {
      drawError.textContent = "Couldn't check the draw. We'll keep trying when you're back online.";
    }
  }

  function addGiftRain() {
    const rain = document.getElementById("gift-rain");
    if (!rain) return;
    rain.replaceChildren();
    ["🎁", "⭐", "🎀", "✨", "🍬", "🎄", "🧦"].forEach((gift, index) => {
      const piece = document.createElement("span");
      piece.textContent = gift;
      piece.style.setProperty("--x", `${8 + index * 13}%`);
      piece.style.setProperty("--size", `${1.1 + (index % 3) * .25}rem`);
      piece.style.animationDelay = `${index * 80}ms`;
      rain.append(piece);
    });
    window.setTimeout(() => rain.replaceChildren(), 2600);
  }

  bindHoldReveal({
    holdButton,
    toggleButton,
    hideButton,
    resultElement,
    onReveal: async () => secretName,
    onShow: () => {
      document.getElementById("secret-reminder").hidden = false;
      document.getElementById("budget-reminder").textContent = budget ? `Remember the budget: ${budget}!` : "Keep your pick secret!";
      celebrate("trio");
      playSound("jingle");
      addGiftRain();
      document.querySelectorAll(".parol").forEach((parol, index) => {
        if (window.gsap && !prefersReducedMotion()) window.gsap.fromTo(parol, { scale: 1, opacity: .65 }, { scale: 1.22, opacity: 1, duration: .32, yoyo: true, repeat: 1, delay: index * .08, transformOrigin: "50% 45%" });
      });
    },
    onHide: () => {
      document.getElementById("secret-reminder").hidden = true;
      document.getElementById("gift-rain")?.replaceChildren();
    },
  });

  shakeButton?.addEventListener("click", async () => {
    if (busy || prefersReducedMotion()) {
      if (!busy) {
        scene.classList.remove("fade-feedback");
        void scene.offsetWidth;
        scene.classList.add("fade-feedback");
        playSound("shuffle");
      }
      return;
    }
    scene.classList.add("is-shaking");
    navigator.vibrate?.([30, 20, 45]);
    playSound("shuffle");
    if (window.gsap) {
      await Promise.all([
        window.gsap.to(scene, { rotation: 9, x: 6, duration: .16, yoyo: true, repeat: 7, ease: "elastic.out(1,.35)", transformOrigin: "50% 85%" }),
        window.gsap.to(field.children, { rotation: () => window.gsap.utils.random(-150, 150), x: () => window.gsap.utils.random(-32, 32), y: () => window.gsap.utils.random(-28, 28), duration: .32, yoyo: true, repeat: 5, stagger: .012, ease: "sine.inOut" }),
      ]);
    } else {
      await wait(1000);
    }
    scene.classList.remove("is-shaking");
    renderSlips(remainingCount?.textContent);
  });

  async function handleDrawError(error) {
    let state = null;
    try { state = await apiGet("/api/state"); } catch { /* retain the original draw error */ }
    const saved = readIdentity();
    if (error?.code === "already_drawn" && saved?.participantId === participantId && saved.recovery_key) {
      window.location.assign("/my-pick/");
      return;
    }
    if (error?.code === "not_open") {
      drawError.textContent = "The draw isn't open yet. Please wait for the organizer.";
      return;
    }
    if (error?.code === "deadlock") {
      drawError.textContent = "The draw couldn't be completed. Please ask the organizer to reset it.";
      return;
    }
    if (state?.status && state.status !== "OPEN") {
      drawError.textContent = "Your draw was recorded, but we couldn't verify the result. Please ask the organizer to reset the draw.";
      return;
    }
    drawError.textContent = "Your draw was recorded, but the result was lost. Please ask the organizer to reset the draw.";
  }

  drawButton.addEventListener("click", async () => {
    if (busy) return;
    busy = true;
    drawButton.disabled = true;
    shakeButton.disabled = true;
    drawError.textContent = "";
    const startedAt = performance.now();
    scene.classList.add("is-grabbing");
    const drawRequest = (async () => {
      if (!prefersReducedMotion()) await wait(560);
      playSound("shuffle");
      return apiPost("/api/draw", {});
    })();

    if (!prefersReducedMotion() && window.gsap) {
      window.gsap.to(scene, { rotation: -6, y: 6, duration: .35, yoyo: true, repeat: 1, ease: "power2.inOut" });
      window.gsap.fromTo(document.getElementById("grab-hand"), { y: -45, rotation: -16, opacity: 0 }, { y: 16, rotation: 9, opacity: 1, duration: .48, ease: "power2.in" });
    }

    const [requestResult] = await Promise.allSettled([drawRequest, wait(Math.max(0, 3000 - (performance.now() - startedAt)))]);
    scene.classList.remove("is-grabbing");
    if (requestResult.status === "rejected") {
      const error = requestResult.reason;
      await handleDrawError(error);
      busy = false;
      return;
    }

    const result = requestResult.value;
    secretName = String(result.name || "");
    saveIdentity(participantId, result.recovery_key);
    recoveryOutput.textContent = result.recovery_key;
    recoveryBox.hidden = false;
    drawCard.hidden = false;
    drawButton.hidden = true;
    shakeButton.hidden = true;
    playSound("jingle");
    if (prefersReducedMotion()) {
      drawCard.classList.add("fade-in");
      countdown.textContent = "Ready?";
      await wait(350);
      countdown.textContent = "";
      flipCard.classList.add("is-flipped");
    } else {
      if (window.gsap) await window.gsap.fromTo(flipCard, { y: -110, scale: .34, rotation: -160, opacity: .15 }, { y: 0, scale: 1, rotation: 0, opacity: 1, duration: .72, ease: "back.out(1.35)" });
      for (const numeral of ["3", "2", "1"]) {
        countdown.textContent = numeral;
        if (window.gsap) await window.gsap.fromTo(countdown, { scale: .7, opacity: .2 }, { scale: 1.18, opacity: 1, duration: .34, yoyo: true, repeat: 1, ease: "back.out(2)" });
        else await wait(600);
      }
      countdown.textContent = "";
      flipCard.classList.add("is-flipped");
      await wait(760);
    }
    drawCard.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "center" });
    holdButton.focus({ preventScroll: true });
    busy = false;
  });

  document.getElementById("copy-recovery-key")?.addEventListener("click", async () => {
    try {
      await copyText(recoveryOutput.textContent);
      keyStatus.textContent = "Recovery key copied to the clipboard.";
      playSound("blip");
    } catch {
      keyStatus.textContent = "Couldn't copy automatically. Press and hold the key to copy it.";
    }
  });

  void updateState();
  polling = window.setInterval(updateState, 10_000);
  window.addEventListener("pagehide", () => window.clearInterval(polling), { once: true });
}
