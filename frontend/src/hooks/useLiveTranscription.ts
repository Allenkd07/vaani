import { useCallback, useEffect, useRef, useState } from "react";
import { startMicCapture, type MicCapture } from "../audio/micCapture";
import { addLanguage } from "../lib/language";

export type LiveStatus = "idle" | "connecting" | "recording" | "finishing" | "error";

type ServerMessage =
  | { type: "ready" | "done" }
  | { type: "interim" | "final"; text: string; language?: string | null }
  | { type: "error"; message: string };

function socketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws/transcribe`;
}

/** Mic and WebSocket lifecycle; exposes the live transcript as state. */
export function useLiveTranscription() {
  const [status, setStatus] = useState<LiveStatus>("idle");
  const [segments, setSegments] = useState<string[]>([]);
  // Detected languages in order of first appearance, as primary subtags.
  const [languages, setLanguages] = useState<string[]>([]);
  const [interim, setInterim] = useState("");
  const [level, setLevel] = useState(0);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MicCapture | null>(null);
  const interimRef = useRef("");
  const timerRef = useRef<number | null>(null);

  const stopMic = useCallback(async () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    const mic = micRef.current;
    micRef.current = null;
    await mic?.stop();
  }, []);

  const updateInterim = (text: string) => {
    interimRef.current = text;
    setInterim(text);
  };

  // Promote interim text the provider never finalized.
  const flushInterim = () => {
    const text = interimRef.current.trim();
    if (text) setSegments((prev) => [...prev, text]);
    updateInterim("");
  };

  const fail = useCallback(
    (message: string) => {
      flushInterim();
      setError(message);
      setStatus("error");
      void stopMic();
      socketRef.current?.close();
    },
    [stopMic],
  );

  const start = useCallback(async () => {
    setSegments([]);
    setLanguages([]);
    updateInterim("");
    setElapsedSec(0);
    setError(null);
    setStatus("connecting");

    const socket = new WebSocket(socketUrl());
    socket.binaryType = "arraybuffer";
    socketRef.current = socket;

    socket.onmessage = async (event) => {
      const message = JSON.parse(event.data) as ServerMessage;
      switch (message.type) {
        case "ready":
          try {
            micRef.current = await startMicCapture((pcm) => {
              if (socket.readyState === WebSocket.OPEN) socket.send(pcm);
            }, setLevel);
            const startedAt = Date.now();
            timerRef.current = window.setInterval(() => setElapsedSec(Math.round((Date.now() - startedAt) / 1000)), 500);
            setStatus("recording");
          } catch {
            fail("Microphone access was denied or is unavailable.");
          }
          break;
        case "interim":
          updateInterim(message.text);
          setLanguages((prev) => addLanguage(prev, message.language));
          break;
        case "final":
          setSegments((prev) => [...prev, message.text.trim()]);
          setLanguages((prev) => addLanguage(prev, message.language));
          updateInterim("");
          break;
        case "error":
          fail(message.message);
          break;
        case "done":
          flushInterim();
          setStatus("idle");
          break;
      }
    };
    socket.onerror = () => fail("Could not connect to the transcription service.");
    socket.onclose = () => {
      flushInterim();
      void stopMic();
      setStatus((current) => (current === "error" ? current : "idle"));
    };
  }, [fail, stopMic]);

  const stop = useCallback(async () => {
    setStatus("finishing");
    await stopMic();
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "stop" }));
  }, [stopMic]);

  const reset = useCallback(() => {
    setSegments([]);
    setLanguages([]);
    updateInterim("");
    setElapsedSec(0);
    setError(null);
    setStatus("idle");
  }, []);

  useEffect(
    () => () => {
      void stopMic();
      socketRef.current?.close();
    },
    [stopMic],
  );

  return {
    status,
    segments,
    interim,
    transcript: segments.join(" "),
    languages,
    level,
    elapsedSec,
    error,
    start,
    stop,
    reset,
  };
}
