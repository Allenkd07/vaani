import { request } from "./http";

export interface Transcription {
  id: number;
  title: string;
  text: string;
  languages: string | null;
  duration_sec: number | null;
  created_at: string;
  updated_at: string;
}

export interface TranscriptionPage {
  items: Transcription[];
  total: number;
  page: number;
  size: number;
}

export interface TranscriptionInput {
  title?: string | null;
  text?: string;
  languages?: string | null;
  duration_sec?: number | null;
}

const BASE = "/api/transcriptions";

export const transcriptionsApi = {
  list: (params: { search?: string; page?: number; size?: number }) => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.page) query.set("page", String(params.page));
    if (params.size) query.set("size", String(params.size));
    return request<TranscriptionPage>(`${BASE}?${query}`);
  },
  get: (id: number) => request<Transcription>(`${BASE}/${id}`),
  create: (data: TranscriptionInput & { text: string }) =>
    request<Transcription>(BASE, { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: TranscriptionInput) =>
    request<Transcription>(`${BASE}/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  remove: (id: number) => request<void>(`${BASE}/${id}`, { method: "DELETE" }),
};
