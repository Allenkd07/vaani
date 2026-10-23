import { useContext } from "react";
import { RecordingSessionContext } from "./recordingSessionContext";
import type { RecordingSession } from "./useRecordingSessionState";

export function useRecordingSession(): RecordingSession {
  const session = useContext(RecordingSessionContext);
  if (!session) throw new Error("useRecordingSession must be used inside RecordingSessionProvider");
  return session;
}
