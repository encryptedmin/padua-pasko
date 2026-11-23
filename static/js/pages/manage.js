import { apiGet } from "../api.js";
import { copyText } from "../storage.js";
import { prefersReducedMotion, showToast } from "../fx.js";

const CONFIRM_COPY = {
  open: ["Open the draw?", "The participant list and exclusions will be locked once the draw opens."],
  reveal: ["Start the reveal?", "Anyone who has not drawn will no longer be able to draw."],
  close: ["Close the draw?", "Your family will not be able to draw while it is closed."],
  reset: ["Reset all results?", "All draws will be erased and everyone in the family will need to draw again."],
};

function englishMessage(text) {
  const exact = new Map([
    ["Na-update ang settings.", "Settings updated."],
    ["Na-update ang event settings.", "Event settings updated."],
    ["Pakisuri ang event settings.", "Please review the event settings."],
    ["Naka-lock na ang listahan ng pangalan pagkatapos buksan ang bunutan.", "The participant list is locked after the draw opens."],
    ["Maglagay ng kahit isang pangalan.", "Enter at least one name."],
    ["Tinanggal ang participant at kaugnay na exclusions.", "Participant and related exclusions deleted."],
    ["Hindi makita ang pangalan.", "Participant not found."],
    ["Naka-lock na ang exclusions pagkatapos buksan ang bunutan.", "Exclusions are locked after the draw opens."],
    ["Naka-lock na ang exclusions matapos buksan ang bunutan.", "Exclusions are locked after the draw opens."],
    ["Pumili ng dalawang magkaibang pangalan.", "Select two different participants."],
    ["Nagdagdag ng mutual exclusion.", "Mutual exclusion added."],
    ["Idinagdag ang mutual exclusion.", "Mutual exclusion added."],
    ["Inalis ang mutual exclusion.", "Mutual exclusion removed."],
    ["Pumili muna ng exclusion na aalisin.", "Select an exclusion pair to remove."],
    ["Bukas na ang bunutan!", "The draw is now open!"],
    ["Bukas na ang bunutan.", "The draw is now open."],
    ["Nagsimula na ang reveal.", "The reveal has started."],
    ["Nagsimula na ang reveal!", "The reveal has started!"],
    ["Sarado na ang bunutan.", "The draw is closed."],
    ["Isinara na ang bunutan.", "The draw is closed."],
    ["Na-reset ang bunutan.", "The draw has been reset."],
    ["Na-reset ang lahat ng draw.", "All draws have been reset."],
  ]);
  if (exact.has(text)) return exact.get(text);
  let match = text.match(/^Nagdagdag ng (\d+) pangalan\.?$/);
  if (match) return `Added ${match[1]} participant${match[1] === "1" ? "" : "s"}.`;
  match = text.match(/^May kaparehong pangalan na: (.+)\.?$/);
  if (match) return `A participant named ${match[1]} already exists.`;
  match = text.match(/^(.+) ay lampas sa 40 character\.?$/);
  if (match) return `“${match[1]}” is longer than the 40-character limit.`;
  match = text.match(/^Hindi maidagdag ang (.+)\.?$/);
  if (match) return `Could not add ${match[1]}.`;
  if (/\b(?:Nagdagdag|Na-update|Tinanggal|Inalis|Binuksan|Bukas na|Isinara|Sarado na|Nagsimula|Na-reset)\b/i.test(text)) {
    return "The requested change was saved.";
  }
  if (/\b(?:Hindi|Pumili|Maglagay|Naka-lock|kailangan|lampas)\b/i.test(text)) {
    return "Please check the information and try again.";
  }
  return text;
}

export function init() {
  document.querySelectorAll(".manage-message, .manage-login-card .form-message").forEach((message) => {
    message.textContent = englishMessage(message.textContent.trim());
  });

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

  const addOneForm = document.querySelector(".add-one-form");
  const firstName = document.getElementById("participant-first-name");
  const lastName = document.getElementById("participant-last-name");
  const fullName = document.getElementById("participant-name");
  const nameError = document.getElementById("participant-name-error");
  addOneForm?.addEventListener("submit", (event) => {
    const first = firstName?.value.trim() || "";
    const last = lastName?.value.trim() || "";
    const combined = [first, last].filter(Boolean).join(" ");
    if (!first || !last) {
      event.preventDefault();
      if (nameError) nameError.textContent = "Enter both a first name and a last name.";
      (first ? lastName : firstName)?.focus();
      return;
    }
    if (combined.length > 40) {
      event.preventDefault();
      if (nameError) nameError.textContent = "The combined full name must be 40 characters or fewer.";
      lastName?.focus();
      return;
    }
    if (nameError) nameError.textContent = "";
    if (fullName) fullName.value = combined;
  });

  async function copy(value, message) {
    try {
      await copyText(value);
      if (copyStatus) copyStatus.textContent = message;
      showToast(message);
    } catch {
      if (copyStatus) copyStatus.textContent = "Copy is unavailable. Select and copy the code manually.";
    }
  }

  document.getElementById("copy-event-code-button")?.addEventListener("click", () => copy(code, "Event code copied!"));
  document.getElementById("copy-invitation-button")?.addEventListener("click", () => {
    const invitation = `Join our Christmas gift exchange: ${window.location.origin}/\nEnter the secret code: ${code}\nChoose your own name, then keep your pick secret!`;
    copy(invitation, "Invitation copied for your group chat!");
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
      label.textContent = all ? `${complete} of ${all} have drawn` : "Add participants to get started.";
      if (statusPill) statusPill.textContent = state.status || "—";
      if (window.gsap && !prefersReducedMotion()) window.gsap.to(bar, { scaleX: ratio, duration: .65, ease: "power2.out", transformOrigin: "left center" });
      else bar.style.transform = `scaleX(${ratio})`;
    } catch {
      label.textContent = "Could not refresh the stats. We will try again shortly.";
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
        resetInput?.setCustomValidity("Type RESET to continue.");
        resetInput?.reportValidity();
        window.setTimeout(() => resetInput?.setCustomValidity(""), 1200);
        return;
      }
      const [title, description] = CONFIRM_COPY[action] || ["Are you sure?", "Please review this action before continuing."];
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
