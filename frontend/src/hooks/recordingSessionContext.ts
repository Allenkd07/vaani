import { createContext } from "react";
import type { RecordingSession } from "./useRecordingSessionState";

// Separate module so Fast Refresh of the session logic doesn't recreate the context.
export const RecordingSessionContext = createContext<RecordingSession | null>(null);
