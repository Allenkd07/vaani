import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import RecordingSessionProvider from "./components/RecordingSessionProvider";
import DashboardPage from "./pages/DashboardPage";
import RecordPage from "./pages/RecordPage";

export default function App() {
  return (
    <RecordingSessionProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<RecordPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </RecordingSessionProvider>
  );
}
