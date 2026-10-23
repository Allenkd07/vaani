import { useCallback, useEffect, useRef, useState } from "react";
import { transcriptionsApi, type Transcription } from "../api/transcriptions";
import { detectScriptLanguages, toStoredLanguages } from "../lib/language";
import { useLiveTranscription } from "./useLiveTranscription";

/** Recording session state. Provided above the routes so it survives navigation. */
export function useRecordingSessionState() {
  const live = useLiveTranscription();
  const [title, setTitle] = useState("");
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<Transcription | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  // Incremented on every save or delete; the history list reloads on change.
  const [savedVersion, setSavedVersion] = useState(0);
  const wasBusyRef = useRef(false);

  const busy = live.status === "connecting" || live.status === "recording" || live.status === "finishing";
  const dirty = saved !== null && (draft.trim() !== saved.text || title.trim() !== saved.title);

  useEffect(() => {
    if (!busy) setDraft(live.transcript);
  }, [busy, live.transcript]);

  const persist = async (action: () => Promise<Transcription>) => {
    setSaving(true);
    setSaveError(null);
    try {
      const record = await action();
      setSaved(record);
      setTitle(record.title);
      setDraft(record.text);
      setSavedVersion((v) => v + 1);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const create = () => {
    const text = live.transcript.trim();
    if (!text) return;
    void persist(() =>
      transcriptionsApi.create({
        text,
        languages: toStoredLanguages(live.languages.length ? live.languages : detectScriptLanguages(text)),
        duration_sec: live.elapsedSec,
      }),
    );
  };

  // Auto-save when a session ends.
  useEffect(() => {
    if (wasBusyRef.current && !busy) create();
    wasBusyRef.current = busy;
  }, [busy]);

  const clear = () => {
    live.reset();
    setDraft("");
    setTitle("");
    setSaved(null);
    setSaveError(null);
  };

  const start = () => {
    setSaved(null);
    setSaveError(null);
    setTitle("");
    void live.start();
  };

  const update = () => {
    if (!saved) return;
    const text = draft.trim();
    void persist(() =>
      transcriptionsApi.update(saved.id, {
        title: title.trim() || null,
        text,
      }),
    );
  };

  const remove = async () => {
    if (saved) {
      try {
        await transcriptionsApi.remove(saved.id);
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : "Delete failed");
        return;
      }
      setSavedVersion((v) => v + 1);
    }
    clear();
  };

  // Clears the draft when the history page deletes the record it belongs to.
  const forget = useCallback(
    (id: number) => {
      if (saved?.id === id && !busy) clear();
    },
    [saved, busy],
  );

  return {
    live,
    busy,
    dirty,
    title,
    setTitle,
    draft,
    setDraft,
    saving,
    saved,
    saveError,
    savedVersion,
    start,
    stop: live.stop,
    create,
    update,
    remove,
    forget,
  };
}

export type RecordingSession = ReturnType<typeof useRecordingSessionState>;
