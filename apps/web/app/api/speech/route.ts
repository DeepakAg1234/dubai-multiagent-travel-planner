import { sarvamKey } from "@/lib/sarvam-key";
import {
  EMPTY_TRANSCRIPT,
  MAX_AUDIO_BYTES,
  SARVAM_MODEL,
  SARVAM_SPEECH_URL,
  acceptedAudioType,
  sarvamAudioFile,
  speechFailureMessage,
  transcriptFromSarvam,
} from "@/lib/speech";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

/**
 * Turns one short microphone clip into text.
 * The Sarvam key stays on this Next.js route. `/api/planner/*` is a different service and never sees the audio.
 * Sarvam's synchronous API accepts 30 seconds; the browser stops the recording there.
 */
export async function POST(request: Request) {
  const key = sarvamKey();
  if (!key) {
    return Response.json({ error: speechFailureMessage(503) }, { status: 503 });
  }

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return Response.json({ error: speechFailureMessage(400) }, { status: 400 });
  }

  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return Response.json({ error: speechFailureMessage(400) }, { status: 400 });
  }
  if (file.size > MAX_AUDIO_BYTES) {
    return Response.json({ error: speechFailureMessage(413) }, { status: 413 });
  }
  if (!acceptedAudioType(file.type)) {
    return Response.json({ error: speechFailureMessage(415) }, { status: 415 });
  }

  const outbound = new FormData();
  outbound.append("file", await sarvamAudioFile(file));
  outbound.append("model", SARVAM_MODEL);
  outbound.append("mode", "transcribe");
  outbound.append("language_code", "unknown");

  let upstream: Response;
  try {
    upstream = await fetch(SARVAM_SPEECH_URL, {
      method: "POST",
      headers: { "api-subscription-key": key },
      body: outbound,
      signal: AbortSignal.timeout(25_000),
      cache: "no-store",
    });
  } catch {
    return Response.json({ error: speechFailureMessage(502) }, { status: 502 });
  }

  if (!upstream.ok) {
    const detail = await upstream.text().catch(() => "");
    console.error(`speech-to-text failed: ${upstream.status} ${detail.replace(/\s+/g, " ").slice(0, 300)}`);
    const status = upstream.status === 401 || upstream.status === 403 || upstream.status === 429 ? upstream.status : 502;
    return Response.json({ error: speechFailureMessage(upstream.status) }, { status });
  }

  let body: unknown;
  try {
    body = await upstream.json();
  } catch {
    return Response.json({ error: speechFailureMessage(502) }, { status: 502 });
  }

  const transcript = transcriptFromSarvam(body);
  if (!transcript) {
    return Response.json({ error: EMPTY_TRANSCRIPT }, { status: 422 });
  }

  const language = body && typeof body === "object" ? (body as { language_code?: unknown }).language_code : null;
  return Response.json({
    transcript,
    language_code: typeof language === "string" ? language : null,
  });
}
