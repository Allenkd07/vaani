import { useCallback, useEffect, useState } from "react";
import { transcriptionsApi, type TranscriptionInput, type TranscriptionPage } from "../api/transcriptions";
import { useRecordingSession } from "./useRecordingSession";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 300;

/** Paginated, searchable transcription list with update and delete. */
export function useTranscriptions() {
  const { savedVersion, forget } = useRecordingSession();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<TranscriptionPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await transcriptionsApi.list({ search: debouncedSearch, page, size: PAGE_SIZE }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transcriptions");
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, page]);

  // Reload after the recording session saves.
  useEffect(() => {
    void load();
  }, [load, savedVersion]);

  const update = useCallback(
    async (id: number, input: TranscriptionInput) => {
      await transcriptionsApi.update(id, input);
      await load();
    },
    [load],
  );

  const remove = useCallback(
    async (id: number) => {
      await transcriptionsApi.remove(id);
      forget(id);
      // Deleting the last item on a page moves back one page.
      if (data && data.items.length === 1 && page > 1) setPage(page - 1);
      else await load();
    },
    [data, page, load, forget],
  );

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return { search, setSearch, query: debouncedSearch, page, setPage, totalPages, data, loading, error, update, remove };
}
