import { apiGet, apiPost } from "../api.js";
import { showToast } from "../fx.js";
import { readParticipantId, saveParticipantId } from "../storage.js";

export function init() {
  const list = document.getElementById("wishlists-list");
  const empty = document.getElementById("wishlists-empty");
  const form = document.getElementById("wishlist-form");
  const input = document.getElementById("wishlist-input");
  const counter = document.getElementById("wishlist-count");
  const submit = document.getElementById("wishlist-submit");
  const status = document.getElementById("wishlist-status");
  const identityNote = document.getElementById("wishlist-identity-note");
  const sessionId = Number(document.getElementById("wishlist-participant-id")?.value) || null;
  if (!list || !form || !input) return;

  let participantId = readParticipantId();
  if (sessionId) {
    participantId = sessionId;
    saveParticipantId(sessionId);
  }
  submit.disabled = !participantId;
  identityNote.textContent = participantId ? "Ready na ang save button para sa pangalan mo." : "Piliin muna ang pangalan mo para makapag-save.";

  function updateCount() {
    counter.textContent = `${input.value.length} / 500`;
    counter.setAttribute("aria-label", `${input.value.length} of 500 characters`);
  }

  async function loadLists() {
    try {
      const wishlists = await apiGet("/api/wishlists");
      list.replaceChildren();
      wishlists.forEach((entry) => {
        const card = document.createElement("article");
        card.className = "wishlist-card";
        const name = document.createElement("h3");
        name.textContent = `🎁 ${entry.name}`;
        const text = document.createElement("p");
        text.textContent = entry.wish_list;
        card.append(name, text);
        list.append(card);
      });
      empty.hidden = wishlists.length > 0;
      list.setAttribute("aria-busy", "false");
    } catch (error) {
      status.textContent = error.message || "Hindi ma-load ang wish lists. Pakisubukan ulit.";
      list.setAttribute("aria-busy", "false");
    }
  }

  input.addEventListener("input", updateCount);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!participantId) {
      status.textContent = "Pumili muna ng pangalan sa page ng bunutan.";
      return;
    }
    if (input.value.length > 500) {
      status.textContent = "Hanggang 500 character lang.";
      return;
    }
    submit.disabled = true;
    status.textContent = "Sine-save…";
    try {
      await apiPost("/api/wishlist", { text: input.value });
      status.textContent = "Na-save na ang wish list mo! 🎀";
      showToast("Na-save ang wish list mo 🎀");
      await loadLists();
    } catch (error) {
      status.textContent = error.message || "Hindi na-save. Pakisubukan ulit.";
    } finally {
      submit.disabled = !participantId;
    }
  });

  updateCount();
  void loadLists();
}
