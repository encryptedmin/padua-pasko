import { prefersReducedMotion } from "./fx.js";

/** Adds a hold gesture plus a keyboard/screen-reader toggle without exposing text early. */
export function bindHoldReveal({ holdButton, toggleButton, hideButton, resultElement, onReveal, onShow, onHide }) {
  if (!holdButton || !resultElement) return;
  let revealed = false;
  let holdTimer = 0;
  let activatedByHold = false;
  let hideTimer = 0;

  const hide = () => {
    if (!revealed) return;
    revealed = false;
    window.clearTimeout(hideTimer);
    resultElement.textContent = "";
    resultElement.classList.remove("is-visible");
    holdButton.setAttribute("aria-expanded", "false");
    if (toggleButton) {
      toggleButton.setAttribute("aria-pressed", "false");
      toggleButton.textContent = "Ipakita ang pangalan";
    }
    if (hideButton) hideButton.hidden = true;
    onHide?.();
  };

  const armAutoHide = () => {
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(hide, 20_000);
  };

  const show = async () => {
    if (revealed) { armAutoHide(); return; }
    try {
      const name = await onReveal();
      // A slow request may finish after visibilitychange already fired.
      // Keep the result out of the DOM until the page is visible again and
      // the user explicitly asks to reveal it.
      if (!name || document.hidden) return;
      revealed = true;
      resultElement.textContent = name;
      resultElement.classList.remove("is-visible");
      if (!prefersReducedMotion()) requestAnimationFrame(() => resultElement.classList.add("is-visible"));
      holdButton.setAttribute("aria-expanded", "true");
      if (toggleButton) {
        toggleButton.setAttribute("aria-pressed", "true");
        toggleButton.textContent = "Pangalan ko 'to — nakatago";
      }
      if (hideButton) hideButton.hidden = false;
      onShow?.();
      armAutoHide();
    } catch { /* page handler displays a friendly error */ }
  };

  holdButton.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    activatedByHold = false;
    window.clearTimeout(holdTimer);
    holdTimer = window.setTimeout(() => {
      activatedByHold = true;
      void show();
    }, 520);
  });
  ["pointerup", "pointercancel", "pointerleave"].forEach((type) => holdButton.addEventListener(type, () => window.clearTimeout(holdTimer)));
  holdButton.addEventListener("click", (event) => {
    if (event.detail > 0) {
      event.preventDefault();
      if (activatedByHold) event.stopPropagation();
      return;
    }
    event.preventDefault();
    if (revealed) hide(); else void show();
  });
  toggleButton?.addEventListener("click", () => revealed ? hide() : void show());
  hideButton?.addEventListener("click", hide);
  document.addEventListener("pointerdown", () => { if (revealed) armAutoHide(); }, { passive: true });
  document.addEventListener("keydown", () => { if (revealed) armAutoHide(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) hide(); });
  return { hide, show };
}
