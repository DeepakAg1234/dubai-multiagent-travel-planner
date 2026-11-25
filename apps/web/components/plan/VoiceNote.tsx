"use client";

import { useEffect, useRef, useState } from "react";

import { Mic } from "@/components/site/Icons";
import { RECORDING_LIMIT_MS, baseAudioType, readSpeechResponse, recordingFilename } from "@/lib/speech";

type Phase = "idle" | "starting" | "recording" | "sending";

function preferredMime(): string {
  if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") return "";
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return types.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

function micError(error: unknown): string {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Allow the microphone to speak your trip. You can still type it.";
  }
  if (name === "NotFoundError") return "No microphone was found. You can still type your trip.";
  return "The microphone could not start. You can still type your trip.";
}

/**
 * Records at most 30 seconds and appends the transcript through `onTranscript`.
 * Typing stays available. This control does not fill the wizard steps by itself.
 */
export function VoiceNote({ onTranscript }: { onTranscript: (transcript: string) => void }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [leftMs, setLeftMs] = useState(RECORDING_LIMIT_MS);
  const [note, setNote] = useState("");
  const [tone, setTone] = useState<"ok" | "bad">("ok");
  const alive = useRef(true);
  const phaseRef = useRef<Phase>("idle");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const stopTimer = useRef<number | null>(null);
  const tickTimer = useRef<number | null>(null);
  const startedAt = useRef(0);
  const stopped = useRef(false);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (stopTimer.current !== null) window.clearTimeout(stopTimer.current);
      if (tickTimer.current !== null) window.clearInterval(tickTimer.current);
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        recorder.onstop = null;
        recorder.stop();
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, []);

  function clearTimers() {
    if (stopTimer.current !== null) window.clearTimeout(stopTimer.current);
    if (tickTimer.current !== null) window.clearInterval(tickTimer.current);
    stopTimer.current = null;
    tickTimer.current = null;
  }

  function releaseStream() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function show(message: string, next: "ok" | "bad") {
    if (!alive.current) return;
    setNote(message);
    setTone(next);
  }

  async function upload(blob: Blob) {
    if (!alive.current) return;
    if (blob.size === 0) {
      setPhase("idle");
      phaseRef.current = "idle";
      show("We didn't hear anything. Try again, or type your trip.", "bad");
      return;
    }
    setPhase("sending");
    phaseRef.current = "sending";
    show("Turning speech into text.", "ok");
    const type = baseAudioType(blob.type);
    const body = new FormData();
    body.append("file", new Blob([blob], { type }), recordingFilename(type));
    try {
      const response = await fetch("/api/speech", { method: "POST", body });
      const result = await readSpeechResponse(response);
      if (!alive.current) return;
      if (!result.ok) {
        setPhase("idle");
        phaseRef.current = "idle";
        show(result.error, "bad");
        return;
      }
      onTranscript(result.transcript);
      setPhase("idle");
      phaseRef.current = "idle";
      show("Added what we heard. Edit it, then choose Fill in my details.", "ok");
    } catch {
      if (!alive.current) return;
      setPhase("idle");
      phaseRef.current = "idle";
      show("We could not reach the speech service. You can still type your trip.", "bad");
    }
  }

  function finish(reason: "user" | "limit") {
    if (stopped.current) return;
    stopped.current = true;
    clearTimers();
    setPhase("sending");
    phaseRef.current = "sending";
    show(reason === "limit" ? "30 seconds is the longest recording. Turning it into text." : "Turning speech into text.", "ok");
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
    else {
      releaseStream();
      setPhase("idle");
      phaseRef.current = "idle";
    }
  }

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      show("This browser cannot record audio. Type your trip instead.", "bad");
      setPhase("idle");
      phaseRef.current = "idle";
      return;
    }
    setNote("");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      if (!alive.current) return;
      setPhase("idle");
      phaseRef.current = "idle";
      show(micError(error), "bad");
      return;
    }
    if (!alive.current) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }

    const mime = preferredMime();
    let recorder: MediaRecorder;
    try {
      recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    } catch {
      stream.getTracks().forEach((track) => track.stop());
      setPhase("idle");
      phaseRef.current = "idle";
      show("This browser cannot record audio. Type your trip instead.", "bad");
      return;
    }

    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mime || "audio/webm" });
      chunksRef.current = [];
      recorderRef.current = null;
      releaseStream();
      if (!alive.current) return;
      void upload(blob);
    };

    streamRef.current = stream;
    recorderRef.current = recorder;
    stopped.current = false;
    try {
      recorder.start();
    } catch {
      releaseStream();
      recorderRef.current = null;
      setPhase("idle");
      phaseRef.current = "idle";
      show("The microphone could not start. You can still type your trip.", "bad");
      return;
    }

    startedAt.current = Date.now();
    setLeftMs(RECORDING_LIMIT_MS);
    setPhase("recording");
    phaseRef.current = "recording";
    show("Recording. It stops at 30 seconds.", "ok");
    tickTimer.current = window.setInterval(() => {
      setLeftMs(Math.max(0, RECORDING_LIMIT_MS - (Date.now() - startedAt.current)));
    }, 200);
    stopTimer.current = window.setTimeout(() => finish("limit"), RECORDING_LIMIT_MS);
  }

  function onPress() {
    if (phaseRef.current === "sending" || phaseRef.current === "starting") return;
    if (phaseRef.current === "recording") {
      finish("user");
      return;
    }
    setPhase("starting");
    phaseRef.current = "starting";
    void start();
  }

  const seconds = Math.ceil(leftMs / 1000);
  const recording = phase === "recording";
  const label = recording ? `Stop · ${seconds}s` : phase === "sending" ? "Transcribing" : phase === "starting" ? "Starting" : "Speak";

  return (
    <>
      {note ? (
        <p className={tone === "bad" ? "dj-voice-note dj-voice-note--bad" : "dj-voice-note"} role="status">
          {note}
        </p>
      ) : null}
      <button
        type="button"
        className={recording ? "dj-btn dj-btn--sm dj-btn--rec" : "dj-btn dj-btn--sm dj-btn--ghost"}
        onClick={onPress}
        disabled={phase === "starting" || phase === "sending"}
        aria-pressed={recording}
        aria-label={recording ? "Stop recording" : "Speak your trip, up to 30 seconds"}
      >
        {recording ? <i className="dj-rec-dot" /> : <Mic width={18} height={18} />}
        {label}
      </button>
    </>
  );
}
