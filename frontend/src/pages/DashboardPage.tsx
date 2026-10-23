import { useState } from "react";
import { Link } from "react-router-dom";
import type { Transcription } from "../api/transcriptions";
import ConfirmDialog from "../components/ConfirmDialog";
import EditDialog from "../components/EditDialog";
import Highlight from "../components/Highlight";
import Icon from "../components/Icon";
import { useSpeech } from "../hooks/useSpeech";
import { useToast } from "../hooks/useToast";
import { useTranscriptions } from "../hooks/useTranscriptions";
import { formatDuration, formatLanguages } from "../lib/language";
import { dateGroup, fullDateTime, relativeTime } from "../lib/time";

const SKELETON_ROWS = 3;

function groupByDate(items: Transcription[]) {
  const now = new Date();
  const groups: { label: string; items: Transcription[] }[] = [];
  for (const item of items) {
    const label = dateGroup(new Date(item.created_at), now);
    const last = groups[groups.length - 1];
    if (last?.label === label) last.items.push(item);
    else groups.push({ label, items: [item] });
  }
  return groups;
}

export default function DashboardPage() {
  const { search, setSearch, query, page, setPage, totalPages, data, loading, error, update, remove } =
    useTranscriptions();
  const speech = useSpeech();
  const toast = useToast();
  const [editing, setEditing] = useState<Transcription | null>(null);
  const [deleting, setDeleting] = useState<Transcription | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const confirmDelete = async () => {
    if (!deleting) return;
    if (speech.speakingId === deleting.id) speech.stop();
    await remove(deleting.id);
    toast.show("Transcript deleted");
  };

  const copy = async (item: Transcription) => {
    await navigator.clipboard.writeText(item.text);
    toast.show("Copied to clipboard");
  };

  const first = data && data.total > 0 ? (data.page - 1) * data.size + 1 : 0;
  const last = data ? Math.min(data.page * data.size, data.total) : 0;
  const now = new Date();

  return (
    <section className="history">
      <div className="history-head">
        <h1>History</h1>
        {data && (
          <span className="history-count">
            {data.total} transcript{data.total === 1 ? "" : "s"}
          </span>
        )}
      </div>

      <label className="searchbox">
        <Icon name="search" />
        <input
          type="search"
          placeholder="Search transcripts"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search transcripts"
        />
      </label>

      {error && <p className="notice is-error">{error}</p>}

      {loading && !data && (
        <ul className="history-list" aria-busy="true" aria-label="Loading transcripts">
          {Array.from({ length: SKELETON_ROWS }, (_, i) => (
            <li key={i} className="history-item is-skeleton">
              <span className="skeleton-line is-title" />
              <span className="skeleton-line" />
              <span className="skeleton-line is-short" />
            </li>
          ))}
        </ul>
      )}

      {!loading && data?.items.length === 0 && (
        <div className="empty">
          <Icon name={query ? "search" : "history"} size={40} />
          <p>{query ? `Nothing matches “${query}”.` : "Your saved transcripts will appear here."}</p>
          {!query && (
            <Link to="/" className="btn filled">
              Start recording
            </Link>
          )}
        </div>
      )}

      {!!data?.items.length && (
        <div className={`history-groups ${loading ? "is-loading" : ""}`}>
          {groupByDate(data.items).map((group) => (
            <section key={group.label} className="history-group">
              <h2>{group.label}</h2>
              <ul className="history-list">
                {group.items.map((item) => {
                  const expanded = expandedId === item.id;
                  const speaking = speech.speakingId === item.id;
                  const created = new Date(item.created_at);
                  return (
                    <li key={item.id} className="history-item">
                      <button
                        className="history-item-main"
                        onClick={() => setExpandedId(expanded ? null : item.id)}
                        aria-expanded={expanded}
                      >
                        <span className="history-row">
                          <span className="history-title">
                            <Highlight text={item.title} query={query} />
                          </span>
                          <time className="history-time" dateTime={item.created_at} title={fullDateTime.format(created)}>
                            {relativeTime(created, now)}
                          </time>
                        </span>
                        <span className={`history-text ${expanded ? "" : "is-clamped"}`}>
                          <Highlight text={item.text} query={query} />
                        </span>
                        <span className="history-meta">
                          <span>
                            <Icon name="schedule" size={16} />
                            {formatDuration(item.duration_sec)}
                          </span>
                          {item.languages && (
                            <span>
                              <Icon name="translate" size={16} />
                              {formatLanguages(item.languages)}
                            </span>
                          )}
                        </span>
                      </button>
                      <div className="history-actions">
                        {speech.supported && (
                          <button
                            className="icon-btn"
                            onClick={() => (speaking ? speech.stop() : speech.speak(item.id, item.text, item.languages))}
                            aria-label={speaking ? "Stop listening" : "Listen"}
                            title={speaking ? "Stop listening" : "Listen"}
                          >
                            <Icon name={speaking ? "stop" : "volume"} />
                          </button>
                        )}
                        <button className="icon-btn" onClick={() => copy(item)} aria-label="Copy text" title="Copy text">
                          <Icon name="copy" />
                        </button>
                        <button className="icon-btn" onClick={() => setEditing(item)} aria-label="Edit" title="Edit">
                          <Icon name="edit" />
                        </button>
                        <button
                          className="icon-btn danger"
                          onClick={() => setDeleting(item)}
                          aria-label="Delete"
                          title="Delete"
                        >
                          <Icon name="delete" />
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}

      {data && totalPages > 1 && (
        <div className="pager">
          <span>
            {first}–{last} of {data.total}
          </span>
          <button className="icon-btn" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page">
            <Icon name="chevronLeft" />
          </button>
          <button className="icon-btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)} aria-label="Next page">
            <Icon name="chevronRight" />
          </button>
        </div>
      )}

      <EditDialog
        transcription={editing}
        onSave={async (id, values) => {
          await update(id, values);
          toast.show("Changes saved");
        }}
        onClose={() => setEditing(null)}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete transcript?"
        confirmLabel="Delete"
        onConfirm={confirmDelete}
        onClose={() => setDeleting(null)}
      >
        “{deleting?.title}” will be permanently deleted.
      </ConfirmDialog>

      <div className={`toast ${toast.message ? "is-visible" : ""}`} role="status" aria-live="polite">
        {toast.message}
      </div>
    </section>
  );
}
