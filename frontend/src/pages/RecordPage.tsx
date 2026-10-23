import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import Icon from "../components/Icon";
import { useRecordingSession } from "../hooks/useRecordingSession";
import { useSpeech } from "../hooks/useSpeech";
import { formatDuration, languageName } from "../lib/language";

const STATUS_LABEL = {
  idle: "Ready",
  connecting: "Connecting…",
  recording: "Listening…",
  finishing: "Finishing up…",
  error: "Stopped",
} as const;

export default function RecordPage() {
  const session = useRecordingSession();
  const { live, busy, saved, saving, saveError, dirty, title, draft } = session;
  const speech = useSpeech();
  const [copied, setCopied] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const recording = live.status === "recording";
  const hasText = !busy && draft.trim().length > 0;
  const detected = saved?.languages ? saved.languages.split(",") : live.languages;
  const neverStarted = live.status === "error" && live.elapsedSec === 0 && live.segments.length === 0;
  const statusLabel = neverStarted ? "Couldn’t start" : STATUS_LABEL[live.status];

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight });
  }, [live.segments, live.interim]);

  const copy = async () => {
    await navigator.clipboard.writeText(draft);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  // The halo around the mic follows the input level.
  const micStyle = { "--level": recording ? Math.min(1, live.level * 3) : 0 } as CSSProperties;

  return (
    <section className="record">
      <div className="panel">
        <div className="panel-bar">
          <span className="chip is-selected">Auto-detect</span>
          {detected.length ? (
            <span className="detected" aria-live="polite">
              {detected.map((code) => (
                <span key={code} className="chip small">
                  {languageName(code)}
                </span>
              ))}
              <span className="panel-bar-note">detected</span>
            </span>
          ) : (
            <span className="panel-bar-note">Your language, or a mix, is detected as you speak</span>
          )}
        </div>

        <div className="panel-body">
          {busy ? (
            <div className="transcript" ref={transcriptRef} aria-live="polite">
              {live.segments.length === 0 && !live.interim && <span className="placeholder">Start speaking…</span>}
              {live.segments.map((segment, i) => (
                <span key={i}>{segment} </span>
              ))}
              {live.interim && <span className="interim">{live.interim}</span>}
            </div>
          ) : (
            <textarea
              className="transcript"
              value={draft}
              onChange={(e) => session.setDraft(e.target.value)}
              placeholder="Tap the mic and start speaking"
              readOnly={!saved}
              aria-label="Transcript"
            />
          )}
        </div>

        <div className="panel-foot">
          <button
            className={`mic ${recording ? "is-recording" : ""}`}
            style={micStyle}
            onClick={recording ? session.stop : session.start}
            disabled={live.status === "connecting" || live.status === "finishing" || saving}
            aria-label={recording ? "Stop recording" : "Start recording"}
          >
            <Icon name={recording ? "stop" : "mic"} size={28} />
          </button>
          <div className="mic-status">
            <span className={`status status-${live.status}`}>{statusLabel}</span>
            {(busy || live.elapsedSec > 0) && <span className="timer">{formatDuration(live.elapsedSec)}</span>}
          </div>
          {hasText && (
            <div className="panel-actions">
              {speech.supported && (
                <button
                  className="icon-btn"
                  onClick={() => (speech.speakingId === 0 ? speech.stop() : speech.speak(0, draft, saved?.languages ?? null))}
                  aria-label={speech.speakingId === 0 ? "Stop listening" : "Listen"}
                  title={speech.speakingId === 0 ? "Stop listening" : "Listen"}
                >
                  <Icon name={speech.speakingId === 0 ? "stop" : "volume"} />
                </button>
              )}
              <button className="icon-btn" onClick={copy} aria-label="Copy text" title={copied ? "Copied" : "Copy text"}>
                <Icon name={copied ? "check" : "copy"} />
              </button>
            </div>
          )}
        </div>
      </div>

      {live.error && <p className="notice is-error">{live.error}</p>}

      {!busy && (saved || saving || saveError) && (
        <div className="save-bar">
          {saved && (
            <>
              <input
                className="input"
                placeholder="Title"
                value={title}
                maxLength={200}
                onChange={(e) => session.setTitle(e.target.value)}
                aria-label="Title"
              />
              <button className="btn text danger" onClick={session.remove} disabled={saving}>
                Delete
              </button>
              <button className="btn filled" onClick={session.update} disabled={!dirty || !draft.trim() || saving}>
                {saving ? "Saving…" : "Update"}
              </button>
            </>
          )}
          {saving && !saved && <p className="notice">Saving…</p>}
          {saved && !dirty && !saving && (
            <p className="notice is-success">
              <Icon name="check" size={18} />
              Saved to history. <Link to="/dashboard">Open history</Link>
            </p>
          )}
          {saveError && (
            <p className="notice is-error">
              {saveError}
              {!saved && (
                <button className="btn text" onClick={session.create}>
                  Retry
                </button>
              )}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
