import { apiPost, ApiError } from "../api.js";
import { celebrate, playSound, prefersReducedMotion } from "../fx.js";

export function init() {
  const form = document.getElementById("code-entry-form");
  const grid = document.getElementById("code-boxes");
  const inputs = [...(grid?.querySelectorAll("input[data-code-index]") || [])];
  const errorRegion = document.getElementById("code-error");
  const lockoutRegion = document.getElementById("code-lockout");
  const submitButton = document.getElementById("code-submit");
  if (!form || inputs.length !== 9) return;

  let lockTimer = 0;
  const focusAt = (index) => inputs[Math.max(0, Math.min(8, index))]?.focus();
  const cleanCode = (value) => value.replace(/[\s-]+/g, "").toUpperCase().replace(/[^A-Z0-9]/g, "");

  const setCode = (value, startAt = 0) => {
    const chars = cleanCode(value).slice(0, 9 - startAt);
    chars.split("").forEach((char, offset) => { inputs[startAt + offset].value = char; });
    if (chars.length) focusAt(Math.min(8, startAt + chars.length));
  };

  inputs.forEach((input, index) => {
    input.addEventListener("input", () => {
      const value = cleanCode(input.value);
      input.value = value.slice(-1);
      if (input.value && index < 8) focusAt(index + 1);
      errorRegion.textContent = "";
      grid.classList.remove("is-wrong");
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !input.value && index > 0) {
        inputs[index - 1].value = "";
        focusAt(index - 1);
      } else if (event.key === "ArrowLeft" && index > 0) {
        event.preventDefault();
        focusAt(index - 1);
      } else if (event.key === "ArrowRight" && index < 8) {
        event.preventDefault();
        focusAt(index + 1);
      }
    });
    input.addEventListener("paste", (event) => {
      const pasted = event.clipboardData?.getData("text") || "";
      if (pasted.length > 1) {
        event.preventDefault();
        setCode(pasted, 0);
      }
    });
  });

  function startLockout(seconds) {
    window.clearInterval(lockTimer);
    let remaining = Math.max(1, Number(seconds) || 300);
    inputs.forEach((input) => { input.disabled = true; });
    submitButton.disabled = true;
    lockoutRegion.hidden = false;
    const paint = () => {
      const minutes = Math.floor(remaining / 60).toString().padStart(2, "0");
      const secs = (remaining % 60).toString().padStart(2, "0");
      lockoutRegion.textContent = `Please wait — you can try again in ${minutes}:${secs}.`;
      if (remaining <= 0) {
        window.clearInterval(lockTimer);
        lockoutRegion.hidden = true;
        inputs.forEach((input) => { input.disabled = false; });
        submitButton.disabled = false;
        focusAt(0);
      }
      remaining -= 1;
    };
    paint();
    lockTimer = window.setInterval(paint, 1000);
  }

  async function flashWrong(message) {
    errorRegion.textContent = message || "That code doesn't match. Check it and try again.";
    grid.classList.remove("is-wrong");
    void grid.offsetWidth;
    grid.classList.add("is-wrong");
    window.setTimeout(() => grid.classList.remove("is-wrong"), 850);
    document.querySelectorAll(".parol").forEach((parol, index) => {
      if (window.gsap && !prefersReducedMotion()) window.gsap.to(parol, { rotation: index ? -48 : 48, duration: .15, yoyo: true, repeat: 3, transformOrigin: "50% 20%", ease: "power1.inOut" });
      else parol.classList.add("parol-flash");
    });
    playSound("blip");
    window.setTimeout(() => document.querySelectorAll(".parol-flash").forEach((item) => item.classList.remove("parol-flash")), 1000);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const code = inputs.map((input) => input.value).join("");
    if (code.length !== 9) {
      errorRegion.textContent = "Enter all 9 characters of the code first.";
      focusAt(inputs.findIndex((input) => !input.value));
      return;
    }
    errorRegion.textContent = "";
    lockoutRegion.hidden = true;
    submitButton.disabled = true;
    try {
      await apiPost("/api/enter", { code });
      celebrate("gold");
      playSound("jingle");
      document.querySelectorAll(".parol").forEach((parol, index) => {
        if (window.gsap && !prefersReducedMotion()) window.gsap.fromTo(parol, { scale: .72, opacity: .55 }, { scale: 1.24, opacity: 1, duration: .38, yoyo: true, repeat: 1, delay: index * .07, transformOrigin: "50% 45%" });
        else parol.classList.add("parol-flash");
      });
      const main = document.getElementById("main-content");
      if (window.gsap && !prefersReducedMotion()) {
        await window.gsap.to(main, { opacity: 0, scale: 1.06, duration: .55, ease: "power2.in" });
      } else {
        main?.classList.add("fade-out");
        await new Promise((resolve) => window.setTimeout(resolve, 220));
      }
      window.location.assign("/pick-name/");
    } catch (error) {
      submitButton.disabled = false;
      if (error instanceof ApiError && error.status === 429) {
        errorRegion.textContent = error.message;
        startLockout(error.retryAfter || 300);
      } else if (error instanceof ApiError && error.code === "bad_code") {
        void flashWrong(error.message);
      } else {
        errorRegion.textContent = error.message || "We couldn't verify the code. Check your connection and try again.";
      }
    }
  });

  focusAt(0);
}
