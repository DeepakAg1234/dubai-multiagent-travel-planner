/** Spoken descriptions stay on the synchronous Sarvam endpoint, which accepts 30 seconds. */
export const RECORDING_LIMIT_MS = 30_000;

/** A 30-second browser clip is far smaller than this. The cap rejects a pasted long file. */
export const MAX_AUDIO_BYTES = 2 * 1024 * 1024;

export const SARVAM_SPEECH_URL = "https://api.sarvam.ai/speech-to-text";
export const SARVAM_MODEL = "saaras:v4";

export const EMPTY_TRANSCRIPT = "We didn't catch any words. Try again, or type your trip.";

export function mergeTranscript(current: string, spoken: string): string {
  const next = spoken.trim();
  if (!next) return current;
  const base = current.trim();
  if (!base) return next;
  return `${base} ${next}`;
}

export function recordingFilename(mime: string): string {
  const base = mime.split(";")[0]?.trim().toLowerCase() ?? "";
  if (base.includes("mp4") || base.includes("m4a") || base.includes("aac")) return "trip.m4a";
  if (base.includes("ogg")) return "trip.ogg";
  if (base.includes("wav")) return "trip.wav";
  if (base.includes("mpeg") || base.includes("mp3")) return "trip.mp3";
  return "trip.webm";
}

/** Browsers label microphone clips as audio/*, or as video/webm and video/mp4. */
export function acceptedAudioType(mime: string): boolean {
  const base = mime.split(";")[0]?.trim().toLowerCase() ?? "";
  if (!base) return true;
  if (base.startsWith("audio/")) return true;
  return base === "video/webm" || base === "video/mp4";
}

export function speechFailureMessage(status: number): string {
  if (status === 503) return "Voice input is off until a Sarvam key is set. You can still type your trip.";
  if (status === 401 || status === 403) return "Sarvam rejected the key. You can still type your trip.";
  if (status === 429) return "Sarvam is busy right now. Wait a moment, or type your trip.";
  if (status === 400 || status === 413 || status === 415 || status === 422) {
    return "That recording could not be transcribed. Keep it under 30 seconds and try again, or type your trip.";
  }
  return "We could not turn that recording into text. You can still type your trip.";
}

export function transcriptFromSarvam(body: unknown): string {
  if (!body || typeof body !== "object") return "";
  const transcript = (body as { transcript?: unknown }).transcript;
  return typeof transcript === "string" ? transcript.trim() : "";
}

export type SpeechResult =
  | { ok: true; transcript: string; languageCode: string | null }
  | { ok: false; status: number; error: string };

export async function readSpeechResponse(response: Response): Promise<SpeechResult> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && typeof (payload as { error?: unknown }).error === "string"
        ? (payload as { error: string }).error
        : speechFailureMessage(response.status);
    return { ok: false, status: response.status, error: message };
  }
  const transcript = transcriptFromSarvam(payload);
  if (!transcript) return { ok: false, status: 422, error: EMPTY_TRANSCRIPT };
  const language = payload && typeof payload === "object" ? (payload as { language_code?: unknown }).language_code : null;
  return { ok: true, transcript, languageCode: typeof language === "string" ? language : null };
}
