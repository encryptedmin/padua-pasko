import { apiGet } from "../api.js";
import { copyText } from "../storage.js";
import { prefersReducedMotion, showToast } from "../fx.js";

const CONFIRM_COPY = {
  open: ["Buksan ang bunutan?", "Kapag nagsimula na, naka-lock ang listahan ng participants at exclusions."],
  reveal: ["Simulan ang reveal?", "Hindi na makakabunot ang sinumang hindi pa nakakabunot."],
  close: ["Isara ang bunutan?", "Hindi na makakabunot ang pamilya habang sarado ito."],
  reset: ["I-reset ang lahat ng result?", "Mabubura ang lahat ng draw at kailangan bumunot muli ang buong pamilya."],
};

export function init() {
  const total = document.getElementById("total-count");
  const drawn = document.getElementById("drawn-count");
  const remaining = document.getElementById("remaining-count");
  const bar = document.getElementById("progress-bar");
  const track = document.getElementById("progress-track");
  const label = document.getElementById("progress-label");
  const statusPill = document.getElementById("event-status");
  const code = document.getElementById("event-code")?.textContent.trim() || "";
  const copyStatus = document.getElementById("copy-event-code-status");
  const modal = document.getElementById("action-confirm-modal");
  const modalTitle = document.getElementById("action-modal-title");
  const modalCopy = document.getElementById("action-modal-copy");
  const confirmButton = document.getElementById("confirm-action");
  const cancelButton = document.getElementById("cancel-action");
  const resetInput = document.getElementById("reset-confirm");
  let pendingForm = null;
  let polling = 0;
  if (!total || !bar) return;

  async function copy(value, message) {
    try {
      await copyText(value);
      if (copyStatus) copyStatus.textContent = message;
      showToast(message);
    } catch {
      if (copyStatus) copyStatus.textContent = "Hindi automatic ang copy. Pindutin nang matagal ang code para kopyahin.";
    }
  }

  document.getElementById("copy-event-code-button")?.addEventListener("click", () => copy(code, "Nakopya ang event code!"));
  document.getElementById("copy-invitation-button")?.addEventListener("click", () => {
    const invitation = `Maligayang Pasko! 🎁 Salihan ang bunutan natin: ${window.location.origin}/\nIlagay ang Sikretong Code: ${code}\nPiliin lang ang sarili mong pangalan. Secret lang natin! 🤫`;
    copy(invitation, "Nakopya ang imbitasyon para sa group chat!");
  });

  async function updateStats() {
    try {
      const state = await apiGet("/api/state");
      const all = Number(state.total) || 0;
      const complete = Number(state.drawn_count) || 0;
      const left = Number(state.remaining) || 0;
      const ratio = all > 0 ? Math.max(0, Math.min(1, complete / all)) : 0;
      total.textContent = String(all);
      drawn.textContent = String(complete);
      remaining.textContent = String(left);
      track.setAttribute("aria-valuemax", String(all));
      track.setAttribute("aria-valuenow", String(complete));
      label.textContent = all ? `${complete} sa ${all} ang nakabunot` : "Magdagdag muna ng participants.";
      if (statusPill) statusPill.textContent = state.status || "—";
      if (window.gsap && !prefersReducedMotion()) window.gsap.to(bar, { scaleX: ratio, duration: .65, ease: "power2.out", transformOrigin: "left center" });
      else bar.style.transform = `scaleX(${ratio})`;
    } catch {
      label.textContent = "Hindi ma-refresh ang stats. Susubok ulit mamaya.";
    }
  }

  function closeModal() {
    if (modal?.close) modal.close(); else if (modal) modal.open = false;
    pendingForm = null;
  }

  document.querySelectorAll("form[data-danger-action]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const action = form.dataset.dangerAction;
      if (action === "reset" && resetInput?.value.trim() !== "RESET") {
        resetInput?.focus();
        resetInput?.setCustomValidity("I-type ang RESET para magpatuloy.");
        resetInput?.reportValidity();
        window.setTimeout(() => resetInput?.setCustomValidity(""), 1200);
        return;
      }
      const [title, description] = CONFIRM_COPY[action] || ["Sigurado ka ba?", "Pakisuri muna bago magpatuloy."];
      modalTitle.textContent = title;
      modalCopy.textContent = description;
      pendingForm = form;
      if (modal?.showModal) modal.showModal(); else if (modal) modal.open = true;
    });
  });
  cancelButton?.addEventListener("click", closeModal);
  modal?.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
  confirmButton?.addEventListener("click", () => {
    if (!pendingForm) return;
    const form = pendingForm;
    confirmButton.disabled = true;
    closeModal();
    HTMLFormElement.prototype.submit.call(form);
  });

  void updateStats();
  polling = window.setInterval(updateStats, 15_000);
  window.addEventListener("pagehide", () => window.clearInterval(polling), { once: true });
}
