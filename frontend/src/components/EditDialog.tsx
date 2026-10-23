import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Transcription } from "../api/transcriptions";

interface Props {
  transcription: Transcription | null;
  onSave: (id: number, values: { title: string; text: string }) => Promise<void>;
  onClose: () => void;
}

export default function EditDialog({ transcription, onSave, onClose }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (transcription) {
      setTitle(transcription.title);
      setText(transcription.text);
      setError(null);
      dialog.showModal();
    } else if (dialog.open) {
      dialog.close();
    }
  }, [transcription]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!transcription) return;
    setSaving(true);
    try {
      await onSave(transcription.id, { title, text });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <dialog ref={dialogRef} className="dialog" onClose={onClose}>
      <form onSubmit={submit} className="dialog-form">
        <h2>Edit transcription</h2>
        <label className="field">
          <span>Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
        </label>
        <label className="field">
          <span>Text</span>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} required />
        </label>
        {error && <p className="notice is-error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="btn text" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn filled" disabled={saving || !text.trim()}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
