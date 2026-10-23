import { useCallback, useEffect, useRef, useState } from "react";

const TOAST_MS = 3000;

export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  const show = useCallback((text: string) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    setMessage(text);
    timerRef.current = window.setTimeout(() => setMessage(null), TOAST_MS);
  }, []);

  useEffect(() => () => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
  }, []);

  return { message, show };
}
