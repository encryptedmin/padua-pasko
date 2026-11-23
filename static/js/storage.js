const IDENTITY_KEY = "bunutan.me";
const PARTICIPANT_KEY = "bunutan.participantId";

export function readIdentity() {
  try {
    const value = JSON.parse(localStorage.getItem(IDENTITY_KEY) || "null");
    if (!value || !Number.isInteger(Number(value.participantId)) || typeof value.recovery_key !== "string") return null;
    return { participantId: Number(value.participantId), recovery_key: value.recovery_key };
  } catch { return null; }
}

export function saveIdentity(participantId, recoveryKey) {
  const identity = { participantId: Number(participantId), recovery_key: String(recoveryKey) };
  try {
    localStorage.setItem(IDENTITY_KEY, JSON.stringify(identity));
    localStorage.setItem(PARTICIPANT_KEY, String(identity.participantId));
  } catch { /* recovery key remains available in the page for copying */ }
  return identity;
}

export function saveParticipantId(participantId) {
  try { localStorage.setItem(PARTICIPANT_KEY, String(Number(participantId))); } catch { /* optional convenience */ }
}

export function readParticipantId() {
  const identity = readIdentity();
  if (identity) return identity.participantId;
  try {
    const value = Number(localStorage.getItem(PARTICIPANT_KEY));
    return Number.isInteger(value) && value > 0 ? value : null;
  } catch { return null; }
}

export async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(String(text));
    return true;
  }
  const field = document.createElement("textarea");
  field.value = String(text);
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.append(field);
  field.select();
  const copied = document.execCommand("copy");
  field.remove();
  if (!copied) throw new Error("Copy not supported");
  return true;
}
