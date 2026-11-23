import { apiGet, apiPost, ApiError } from "../api.js";
import { playSound, prefersReducedMotion } from "../fx.js";
import { readIdentity, saveParticipantId } from "../storage.js";

const FAMILY_EMOJIS = ["🎄", "🧑‍🎄", "🧦", "🎁", "⭐", "🕯️", "🍬", "🧸", "🎀", "🍊"];

export function init() {
  const waiting = document.getElementById("waiting-state");
  const content = document.getElementById("pick-content");
  const cards = document.getElementById("participant-cards");
  const errorRegion = document.getElementById("claim-error");
  const modal = document.getElementById("claim-confirm-modal");
  const modalName = document.getElementById("confirm-participant-name");
  const confirmButton = document.getElementById("confirm-claim");
  const cancelButton = document.getElementById("cancel-claim");
  const participantSelect = document.getElementById("participant-select");
  const currentParticipantId = Number(document.getElementById("current-participant-id")?.value) || null;
  const budget = document.getElementById("event-budget");
  const partyDate = document.getElementById("event-party-date");
  if (!cards || !waiting || !content) return;

  let selected = null;
  let busy = false;
  let pollTimer = 0;
  let participantSignature = "";

  const openModal = () => {
    if (!prefersReducedMotion()) modal?.classList.add("animate__animated", "animate__bounceIn");
    if (modal?.showModal) modal.showModal(); else if (modal) modal.open = true;
  };
  const closeModal = () => { if (modal?.close) modal.close(); else if (modal) modal.open = false; };

  async function claimParticipant() {
    if (!selected || busy) return;
    busy = true;
    confirmButton.disabled = true;
    errorRegion.textContent = "";
    participantSelect.value = String(selected.id);
    try {
      await apiPost("/api/claim", { participant_id: selected.id });
      saveParticipantId(selected.id);
      playSound("jingle");
      closeModal();
      if (window.gsap && !prefersReducedMotion()) {
        await window.gsap.to(cards, { opacity: 0, y: -12, duration: .25, ease: "power1.in" });
      }
      window.location.assign("/bowl/");
    } catch (error) {
      if (error instanceof ApiError && error.code === "already_drawn") {
        const record = readIdentity();
        if (record?.participantId === selected.id && record.recovery_key && currentParticipantId === selected.id) {
          closeModal();
          window.location.assign("/my-pick/");
          return;
        }
      }
      errorRegion.textContent = error.message || "Hindi ma-select ang pangalan. Subukan ulit.";
      confirmButton.disabled = false;
    } finally {
      busy = false;
    }
  }

  function renderParticipants(participants) {
    cards.replaceChildren();
    participantSelect.replaceChildren();
    participants.forEach((person, index) => {
      const option = document.createElement("option");
      option.value = String(person.id);
      option.textContent = person.name;
      participantSelect.append(option);

      const wrap = document.createElement("article");
      wrap.className = "participant-item";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "name-card";
      button.style.animationDelay = `${Math.min(index * 45, 420)}ms`;
      button.disabled = Boolean(person.has_drawn);
      button.setAttribute("aria-label", person.has_drawn ? `${person.name}, nakabunot na` : `Piliin si ${person.name}`);
      const emoji = document.createElement("span");
      emoji.className = "name-card-emoji";
      emoji.setAttribute("aria-hidden", "true");
      emoji.textContent = FAMILY_EMOJIS[index % FAMILY_EMOJIS.length];
      const copy = document.createElement("span");
      copy.className = "name-card-copy";
      const name = document.createElement("strong");
      name.textContent = person.name;
      const status = document.createElement("span");
      status.textContent = person.has_drawn ? "Nakabunot na ✓" : "Piliin ako";
      copy.append(name, status);
      button.append(emoji, copy);
      wrap.append(button);

      if (!person.has_drawn) {
        button.addEventListener("click", () => {
          selected = person;
          modalName.textContent = person.name;
          confirmButton.disabled = false;
          errorRegion.textContent = "";
          openModal();
          playSound("blip");
        });
      } else {
        const saved = readIdentity();
        if (saved?.participantId === Number(person.id) && currentParticipantId === Number(person.id)) {
          const link = document.createElement("a");
          link.className = "drawn-pick-link";
          link.href = "/my-pick/";
          link.textContent = "Tingnan ang pick ko →";
          wrap.append(link);
        }
      }
      cards.append(wrap);
    });
    cards.setAttribute("aria-busy", "false");
  }

  async function updateState() {
    try {
      const state = await apiGet("/api/state");
      if (budget) budget.textContent = state.budget_text || "—";
      if (partyDate && state.party_date) partyDate.textContent = new Date(`${state.party_date}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
      if (state.status === "OPEN") {
        waiting.hidden = true;
        content.hidden = false;
        const participants = await apiGet("/api/participants");
        const signature = JSON.stringify(participants);
        if (signature !== participantSignature) {
          participantSignature = signature;
          renderParticipants(participants);
        }
      } else {
        waiting.hidden = false;
        content.hidden = true;
      }
    } catch (error) {
      if (!cards.childElementCount) errorRegion.textContent = "Hindi ma-load ang family list. Pakisuri ang connection at mag-refresh.";
    }
  }

  confirmButton?.addEventListener("click", claimParticipant);
  cancelButton?.addEventListener("click", closeModal);
  modal?.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
  void updateState();
  pollTimer = window.setInterval(updateState, 10_000);
  window.addEventListener("pagehide", () => window.clearInterval(pollTimer), { once: true });
}
