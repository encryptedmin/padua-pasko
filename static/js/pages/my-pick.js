import { apiGet, apiPost } from "../api.js";
import { celebrate, playSound } from "../fx.js";
import { bindHoldReveal } from "../reveal.js";
import { readIdentity, saveIdentity, saveParticipantId } from "../storage.js";

export function init() {
  const form = document.getElementById("my-pick-form");
  const idInput = document.getElementById("participant-id");
  const participantSelect = document.getElementById("manual-participant-select");
  const keyInput = document.getElementById("recovery-key-input");
  const localStatus = document.getElementById("local-key-status");
  const errorRegion = document.getElementById("my-pick-error");
  const resultCard = document.getElementById("my-pick-result-card");
  const revealButton = document.getElementById("reveal-myself-button");
  let participantId = Number(idInput?.value) || null;
  let savedIdentity = readIdentity();
  let cachedName = "";
  let busy = false;

  if (!form || !keyInput || !resultCard) return;

  function loadSavedKey() {
    savedIdentity = readIdentity();
    if (savedIdentity && savedIdentity.participantId === participantId) {
      keyInput.value = savedIdentity.recovery_key;
      localStatus.textContent = "May saved recovery key sa device na ito.";
      return true;
    }
    keyInput.value = "";
    localStatus.textContent = "Walang saved key sa device na ito — ilagay ang recovery key mo.";
    return false;
  }

  async function loadParticipants() {
    try {
      const people = await apiGet("/api/participants");
      participantSelect.replaceChildren();
      people.forEach((person) => {
        const option = document.createElement("option");
        option.value = String(person.id);
        option.textContent = person.has_drawn ? `${person.name} — Nakabunot na` : person.name;
        option.selected = Number(person.id) === participantId;
        participantSelect.append(option);
      });
    } catch {
      participantSelect.disabled = true;
      localStatus.textContent = "Hindi ma-load ang pangalan. Subukang mag-refresh kapag may connection.";
    }
  }

  const controller = bindHoldReveal({
    holdButton: document.getElementById("view-pick-button"),
    toggleButton: document.getElementById("accessibility-my-pick-toggle"),
    hideButton: document.getElementById("hide-my-pick"),
    resultElement: document.getElementById("my-pick-result"),
    onReveal: async () => {
      if (cachedName) return cachedName;
      const recoveryKey = keyInput.value.trim();
      if (!participantId || !recoveryKey) {
        errorRegion.textContent = "Piliin ang pangalan at ilagay ang recovery key muna.";
        return null;
      }
      try {
        const result = await apiPost("/api/my-pick", { participant_id: participantId, recovery_key: recoveryKey });
        cachedName = String(result.name || "");
        if (cachedName) {
          saveIdentity(participantId, recoveryKey);
          localStatus.textContent = "Naka-save na sa device na ito ang recovery key.";
          errorRegion.textContent = "";
        }
        return cachedName;
      } catch (error) {
        errorRegion.textContent = error.message || "Hindi tugma ang recovery key.";
        return null;
      }
    },
    onShow: () => { celebrate("gold", true); playSound("jingle"); },
  });

  form.addEventListener("submit", (event) => event.preventDefault());
  participantSelect.addEventListener("change", async () => {
    const nextId = Number(participantSelect.value) || null;
    if (!nextId || nextId === participantId || busy) return;
    busy = true;
    participantSelect.disabled = true;
    try {
      await apiPost("/api/claim", { participant_id: nextId });
      participantId = nextId;
      idInput.value = String(nextId);
      saveParticipantId(nextId);
      cachedName = "";
      controller?.hide();
      loadSavedKey();
      errorRegion.textContent = "";
    } catch (error) {
      errorRegion.textContent = error.code === "already_drawn"
        ? "Nakabunot na ang pangalang ito. Sa bagong device, hindi pa kayang i-claim ng backend ang dating draw. Tingnan ang TODO sa FRONTEND.md."
        : error.message;
    } finally {
      participantSelect.disabled = false;
      busy = false;
    }
  });

  revealButton?.addEventListener("click", async () => {
    if (busy) return;
    const recoveryKey = keyInput.value.trim();
    if (!participantId || !recoveryKey) {
      errorRegion.textContent = "Ilagay muna ang recovery key mo.";
      return;
    }
    busy = true;
    revealButton.disabled = true;
    try {
      const result = await apiPost("/api/my-pick", { participant_id: participantId, recovery_key: recoveryKey, reveal: true });
      cachedName = String(result.name || "");
      saveIdentity(participantId, recoveryKey);
      localStatus.textContent = "Naibahagi na ang pick mo sa reveals page.";
      errorRegion.textContent = "";
      if (cachedName) await controller?.show();
    } catch (error) {
      errorRegion.textContent = error.message || "Hindi ma-reveal ang pick. Pakisubukan ulit.";
    } finally {
      revealButton.disabled = false;
      busy = false;
    }
  });

  resultCard.hidden = false;
  loadSavedKey();
  void loadParticipants();
}
