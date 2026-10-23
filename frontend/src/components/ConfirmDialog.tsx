import { useEffect, useRef, useState, type ReactNode } from "react";

interface Props {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

export default function ConfirmDialog({ open, title, children, confirmLabel, onConfirm, onClose }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open) {
      setError(null);
      dialog.showModal();
    } else if (dialog.open) {
      dialog.close();
    }
  }, [open]);

  const confirm = async () => {
    setBusy(true);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${confirmLabel} failed`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialogRef} className="dialog is-compact" onClose={onClose}>
      <div className="dialog-form">
        <h2>{title}</h2>
        <p className="dialog-body">{children}</p>
        {error && <p className="notice is-error">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="btn text" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn text danger" onClick={confirm} disabled={busy} autoFocus>
            {busy ? `${confirmLabel}…` : confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  );
}
