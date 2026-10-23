import { useCallback, useEffect, useState } from "react";
import { detectScriptLanguages, primaryLanguage } from "../lib/language";

/**
 * Language to read a transcript in. English voices can't pronounce other scripts, while most Indian and
 * other non-English voices read embedded English well, so the first non-English language wins.
 */
function speechLanguage(text: string, languages: string | null): string {
  const candidates = languages ? languages.split(",") : detectScriptLanguages(text);
  return candidates.find((code) => code !== "en") ?? candidates[0] ?? "en";
}

/** Text-to-speech via the browser's speechSynthesis. */
export function useSpeech() {
  const [speakingId, setSpeakingId] = useState<number | null>(null);
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;

  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
    setSpeakingId(null);
  }, [supported]);

  const speak = useCallback(
    (id: number, text: string, languages: string | null) => {
      if (!supported) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const language = speechLanguage(text, languages);
      const voices = window.speechSynthesis.getVoices().filter((v) => primaryLanguage(v.lang) === language);
      // Prefer an Indian-English voice for English; it reads romanized Hindi and Indian names naturally.
      const voice = voices.find((v) => language === "en" && v.lang.replace("_", "-") === "en-IN") ?? voices[0];
      utterance.lang = voice?.lang ?? language;
      if (voice) utterance.voice = voice;
      utterance.onend = utterance.onerror = () => setSpeakingId((current) => (current === id ? null : current));
      setSpeakingId(id);
      window.speechSynthesis.speak(utterance);
    },
    [supported],
  );

  useEffect(() => stop, [stop]);

  return { supported, speakingId, speak, stop };
}
