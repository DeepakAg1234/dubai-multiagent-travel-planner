import { sarvamKey } from "@/lib/sarvam-key";
import {
  SARVAM_TRANSLATE_URL,
  englishFromTranslate,
  guessLanguage,
  needsTranslation,
  translateRequest,
  type TranslateModel,
} from "@/lib/translate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 30;

/**
 * Translates one trip description into English so Fill in my details can read it.
 * Hindi trip words are also read locally. This route covers the other Indic scripts,
 * and Hindi phrasings the local list does not know. The original text stays in the box.
 */
async function callTranslate(key: string, text: string, model: TranslateModel, source: string): Promise<string | null> {
  const upstream = await fetch(SARVAM_TRANSLATE_URL, {
    method: "POST",
    headers: {
      "api-subscription-key": key,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(translateRequest(text, model, source)),
    signal: AbortSignal.timeout(15_000),
    cache: "no-store",
  });
  if (!upstream.ok) {
    console.error(`translate failed: ${upstream.status}`);
    return null;
  }
  return englishFromTranslate(await upstream.json()) || null;
}

export async function POST(request: Request) {
  const key = sarvamKey();
  if (!key) {
    return Response.json({ error: "Voice input is off until a Sarvam key is set. You can still type your trip." }, { status: 503 });
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ error: "Send the trip description as text." }, { status: 400 });
  }
  const text =
    payload && typeof payload === "object" && typeof (payload as { text?: unknown }).text === "string"
      ? (payload as { text: string }).text.trim()
      : "";
  if (!text) return Response.json({ error: "Send the trip description as text." }, { status: 400 });
  if (!needsTranslation(text)) return Response.json({ english: text });

  try {
    const primary = text.length <= 1000 ? await callTranslate(key, text, "mayura:v1", "auto") : null;
    if (primary) return Response.json({ english: primary });
    const fallback = await callTranslate(key, text, "sarvam-translate:v1", guessLanguage(text));
    if (fallback) return Response.json({ english: fallback });
  } catch {
    console.error("translate failed: 502");
  }
  return Response.json({ error: "We could not translate that description." }, { status: 502 });
}
