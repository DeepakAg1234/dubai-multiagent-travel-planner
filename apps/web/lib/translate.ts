/** Turns a non-English trip description into English before the local detail reader runs. */

export const SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate";

const INDIC =
  /[\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0600-\u06FF\u1C50-\u1C7F\uABC0-\uABFF]/;

/** True when the description uses a script Saaras can hear and Mayura or Sarvam-Translate can read. */
export function needsTranslation(text: string): boolean {
  return INDIC.test(text);
}

/**
 * Script-to-language guess for Sarvam-Translate, which does not auto-detect.
 * Shared scripts (Devanagari, Bengali, Arabic) use the most common travel language in that script.
 */
export function guessLanguage(text: string): string {
  if (/[\u0B80-\u0BFF]/.test(text)) return "ta-IN";
  if (/[\u0C00-\u0C7F]/.test(text)) return "te-IN";
  if (/[\u0C80-\u0CFF]/.test(text)) return "kn-IN";
  if (/[\u0D00-\u0D7F]/.test(text)) return "ml-IN";
  if (/[\u0A80-\u0AFF]/.test(text)) return "gu-IN";
  if (/[\u0A00-\u0A7F]/.test(text)) return "pa-IN";
  if (/[\u0B00-\u0B7F]/.test(text)) return "od-IN";
  if (/[\u0980-\u09FF]/.test(text)) return "bn-IN";
  if (/[\u0600-\u06FF]/.test(text)) return "ur-IN";
  if (/[\u1C50-\u1C7F]/.test(text)) return "sat-IN";
  if (/[\uABC0-\uABFF]/.test(text)) return "mni-IN";
  return "hi-IN";
}

export type TranslateModel = "mayura:v1" | "sarvam-translate:v1";

export function translateRequest(text: string, model: TranslateModel, source: string): Record<string, string> {
  const limit = model === "mayura:v1" ? 1000 : 2000;
  return {
    input: text.trim().slice(0, limit),
    source_language_code: source,
    target_language_code: "en-IN",
    model,
    mode: model === "mayura:v1" ? "modern-colloquial" : "formal",
    numerals_format: "international",
  };
}

export function englishFromTranslate(body: unknown): string {
  if (!body || typeof body !== "object") return "";
  const text = (body as { translated_text?: unknown }).translated_text;
  return typeof text === "string" ? text.trim() : "";
}

export const TRANSLATION_UNAVAILABLE =
  "We couldn't translate that into English. Type the trip in English, or use the steps below.";

export const DIRECT_READING =
  "We couldn't show an English translation, so we read the details we recognized.";

/** A translation is usable only when it is English. Leftover Indic text is a failed translation. */
export function isEnglishReading(text: string): boolean {
  const value = text.trim();
  return Boolean(value) && !needsTranslation(value);
}

export type ReadingPlan =
  | { action: "extract"; text: string }
  | { action: "translate" }
  | { action: "use-english"; text: string };

/**
 * English is read as written. Another language is translated, unless the visitor
 * already has an English line for this exact description, including their edits.
 */
export function readingPlan(original: string, english: string, englishFor: string): ReadingPlan {
  const raw = original.trim();
  if (!needsTranslation(raw)) return { action: "extract", text: raw };
  const edited = english.trim();
  if (edited && englishFor === raw) return { action: "use-english", text: edited };
  return { action: "translate" };
}

/** Asks the web route for an English reading. Returns null when Sarvam cannot translate. */
export async function translateForDetails(text: string): Promise<string | null> {
  const raw = text.trim();
  if (!raw || !needsTranslation(raw)) return raw;
  try {
    const response = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: raw.slice(0, 2000) }),
    });
    if (!response.ok) return null;
    const body: unknown = await response.json();
    const english = body && typeof body === "object" ? (body as { english?: unknown }).english : null;
    return typeof english === "string" && isEnglishReading(english) ? english.trim() : null;
  } catch {
    return null;
  }
}
