import { useCallback, useEffect, useRef, useState } from "react";
import { startMicCapture, type MicCapture } from "../audio/micCapture";
import { addLanguage, detectScriptLanguages } from "../lib/language";

export type LiveStatus = "idle" | "connecting" | "recording" | "finishing" | "error";

type ServerMessage =
  | { type: "ready" | "done" }
  | { type: "interim" | "final"; text: string; language?: string | null }
  | { type: "error"; message: string };

// Audio captured before the server is ready is queued, up to ~10 s of 100 ms chunks.
const MAX_BUFFERED_CHUNKS = 100;

/** One recording's socket plus the audio queued while the provider session opens. */
interface Connection {
  socket: WebSocket;
  ready: boolean;
  buffer: ArrayBuffer[];
  stopRequested: boolean;
}

const STOP_MESSAGE = JSON.stringify({ type: "stop" });

/** The provider's language when it reports one, otherwise languages guessed from the text's script. */
function messageLanguages(text: string, language: string | null | undefined): string[] {
  return language ? [language] : detectScriptLanguages(text);
}

const mergeLanguages = (current: string[], codes: string[]) => codes.reduce(addLanguage, current);

function socketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws/transcribe`;
}

/**
 * Mic and WebSocket lifecycle; exposes the live transcript as state.
 * The mic starts immediately and the WebSocket connects in parallel, so speech during setup is not lost.
 */
export function useLiveTranscription() {
  const [status, setStatus] = useState<LiveStatus>("idle");
  const [segments, setSegments] = useState<string[]>([]);
  // Detected languages in order of first appearance, as primary subtags.
  const [languages, setLanguages] = useState<string[]>([]);
  const [interim, setInterim] = useState("");
  const [level, setLevel] = useState(0);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // True once the provider session is open; distinguishes "couldn't start" from a mid-session failure.
  const [connected, setConnected] = useState(false);

  const connectionRef = useRef<Connection | null>(null);
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
      connectionRef.current?.socket.close();
    },
    [stopMic],
  );

  const start = useCallback(async () => {
    setSegments([]);
    setLanguages([]);
    updateInterim("");
    setElapsedSec(0);
    setError(null);
    setConnected(false);
    setStatus("connecting");

    const socket = new WebSocket(socketUrl());
    socket.binaryType = "arraybuffer";
    const connection: Connection = { socket, ready: false, buffer: [], stopRequested: false };
    connectionRef.current = connection;

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as ServerMessage;
      switch (message.type) {
        case "ready":
          connection.ready = true;
          setConnected(true);
          connection.buffer.forEach((pcm) => socket.send(pcm));
          connection.buffer = [];
          if (connection.stopRequested) socket.send(STOP_MESSAGE);
          break;
        case "interim":
          updateInterim(message.text);
          setLanguages((prev) => mergeLanguages(prev, messageLanguages(message.text, message.language)));
          break;
        case "final":
          setSegments((prev) => [...prev, message.text.trim()]);
          setLanguages((prev) => mergeLanguages(prev, messageLanguages(message.text, message.language)));
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

    try {
      const mic = await startMicCapture((pcm) => {
        if (connection.ready) {
          if (socket.readyState === WebSocket.OPEN) socket.send(pcm);
        } else if (connection.buffer.length < MAX_BUFFERED_CHUNKS) {
          connection.buffer.push(pcm);
        }
      }, setLevel);
      // The session may have failed or been replaced while the permission prompt was open.
      if (connectionRef.current !== connection || socket.readyState >= WebSocket.CLOSING) {
        await mic.stop();
        return;
      }
      micRef.current = mic;
      const startedAt = Date.now();
      timerRef.current = window.setInterval(() => setElapsedSec(Math.round((Date.now() - startedAt) / 1000)), 500);
      setStatus((current) => (current === "connecting" ? "recording" : current));
    } catch {
      fail("Microphone access was denied or is unavailable.");
    }
  }, [fail, stopMic]);

  const stop = useCallback(async () => {
    setStatus("finishing");
    await stopMic();
    const connection = connectionRef.current;
    if (!connection) return;
    // Before ready, the stop is sent after the queued audio is flushed.
    if (!connection.ready) connection.stopRequested = true;
    else if (connection.socket.readyState === WebSocket.OPEN) connection.socket.send(STOP_MESSAGE);
  }, [stopMic]);

  const reset = useCallback(() => {
    setSegments([]);
    setLanguages([]);
    updateInterim("");
    setElapsedSec(0);
    setError(null);
    setConnected(false);
    setStatus("idle");
  }, []);

  useEffect(
    () => () => {
      void stopMic();
      connectionRef.current?.socket.close();
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
    connected,
    start,
    stop,
    reset,
  };
}
