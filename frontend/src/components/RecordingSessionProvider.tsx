import type { ReactNode } from "react";
import { RecordingSessionContext } from "../hooks/recordingSessionContext";
import { useRecordingSessionState } from "../hooks/useRecordingSessionState";

export default function RecordingSessionProvider({ children }: { children: ReactNode }) {
  const session = useRecordingSessionState();
  return <RecordingSessionContext.Provider value={session}>{children}</RecordingSessionContext.Provider>;
}
