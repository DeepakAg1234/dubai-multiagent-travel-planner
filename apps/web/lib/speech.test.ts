import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sarvamKeyFromText } from "./sarvam-key.ts";
import {
  EMPTY_TRANSCRIPT,
  MAX_AUDIO_BYTES,
  RECORDING_LIMIT_MS,
  acceptedAudioType,
  baseAudioType,
  mergeTranscript,
  readSpeechResponse,
  recordingFilename,
  sarvamAudioFile,
  speechFailureMessage,
  transcriptFromSarvam,
} from "./speech.ts";

describe("sarvamKeyFromText", () => {
  it("reads only the speech key and keeps other secrets out", () => {
    const text = ["# comment", "ANTHROPIC_API_KEY=secret", "SARVAM_API_KEY=\"voice-key\"", "ORS_API_KEY=other"].join("\n");
    assert.equal(sarvamKeyFromText(text), "voice-key");
    assert.equal(sarvamKeyFromText("SARVAM_API_KEY="), "");
    assert.equal(sarvamKeyFromText("SARVAM_API_KEY = plain"), "plain");
  });
});

describe("speech limits", () => {
  it("caps a spoken description at the synchronous Sarvam limit", () => {
    assert.equal(RECORDING_LIMIT_MS, 30_000);
    assert.ok(MAX_AUDIO_BYTES < 4.5 * 1024 * 1024);
  });
});

describe("mergeTranscript", () => {
  it("uses the spoken line when the box is empty", () => {
    assert.equal(mergeTranscript("  ", "  Four days in Dubai  "), "Four days in Dubai");
  });

  it("keeps typed text and appends the transcript", () => {
    assert.equal(mergeTranscript("culture and beaches", "relaxed pace"), "culture and beaches relaxed pace");
  });

  it("leaves the box alone when nothing was heard", () => {
    assert.equal(mergeTranscript("already typed", "   "), "already typed");
  });
});

describe("recording shape", () => {
  it("names the clip from the browser mime type", () => {
    assert.equal(recordingFilename("audio/webm;codecs=opus"), "trip.webm");
    assert.equal(recordingFilename("audio/mp4"), "trip.m4a");
    assert.equal(recordingFilename("audio/ogg"), "trip.ogg");
    assert.equal(recordingFilename(""), "trip.webm");
  });

  it("accepts microphone containers and rejects other uploads", () => {
    assert.equal(acceptedAudioType(""), true);
    assert.equal(acceptedAudioType("audio/webm;codecs=opus"), true);
    assert.equal(acceptedAudioType("video/webm"), true);
    assert.equal(acceptedAudioType("video/mp4"), true);
    assert.equal(acceptedAudioType("text/plain"), false);
  });

  it("drops the codec parameter Sarvam rejects", async () => {
    assert.equal(baseAudioType("audio/webm;codecs=opus"), "audio/webm");
    assert.equal(baseAudioType("audio/mp4;codecs=opus"), "audio/mp4");
    assert.equal(baseAudioType("video/webm"), "video/webm");
    assert.equal(baseAudioType(""), "audio/webm");
    const source = new File([Uint8Array.from([1, 2, 3, 4])], "clip.webm", { type: "audio/webm;codecs=opus" });
    const clean = await sarvamAudioFile(source);
    assert.equal(clean.type, "audio/webm");
    assert.equal(clean.name, "trip.webm");
    assert.equal(clean.size, 4);
  });
});

describe("Sarvam responses", () => {
  it("reads a transcript and ignores a blank one", () => {
    assert.equal(transcriptFromSarvam({ transcript: "  four days  " }), "four days");
    assert.equal(transcriptFromSarvam({ transcript: "  " }), "");
    assert.equal(transcriptFromSarvam(null), "");
  });

  it("keeps a missing key distinct from a rejected recording", () => {
    assert.match(speechFailureMessage(503), /Sarvam key/);
    assert.match(speechFailureMessage(401), /rejected the key/);
    assert.match(speechFailureMessage(429), /busy/);
    assert.match(speechFailureMessage(400), /30 seconds/);
    assert.match(speechFailureMessage(502), /could not turn that recording/);
  });

  it("parses a successful body and prefers the route error string", async () => {
    const ok = await readSpeechResponse(
      Response.json({ transcript: " four days in Dubai ", language_code: "en-IN" }),
    );
    assert.equal(ok.ok, true);
    if (ok.ok) {
      assert.equal(ok.transcript, "four days in Dubai");
      assert.equal(ok.languageCode, "en-IN");
    }

    const missing = await readSpeechResponse(Response.json({ error: "Voice input is off until a Sarvam key is set. You can still type your trip." }, { status: 503 }));
    assert.equal(missing.ok, false);
    if (!missing.ok) assert.match(missing.error, /type your trip/);

    const blank = await readSpeechResponse(Response.json({ transcript: " " }));
    assert.equal(blank.ok, false);
    if (!blank.ok) assert.equal(blank.error, EMPTY_TRANSCRIPT);

    const broken = await readSpeechResponse(new Response("nope", { status: 502 }));
    assert.equal(broken.ok, false);
    if (!broken.ok) assert.match(broken.error, /could not turn that recording/);
  });
});
