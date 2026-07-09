// API client — REST calls to the Python backend
const API_BASE = '';

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json();
}

export async function apiText(path: string, init?: RequestInit): Promise<string> {
  const r = await fetch(`${API_BASE}${path}`, init);
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.text();
}

export const HelixAPI = {
  health: () => api<{ ok: boolean; version: string }>('/api/health'),
  status: () => api<Record<string, unknown>>('/api/status'),
  tools: () => api<unknown[]>('/api/tools'),
  skills: () => api<{ name: string; title: string; description: string; path: string }[]>('/api/skills'),
  memory: () => api<Record<string, string>>('/api/memory'),
  updateMemory: (kind: string, content: string) =>
    apiText(`/api/memory/${kind}`, {
      method: 'PUT',
      body: content,
      headers: { 'Content-Type': 'text/plain' },
    }),
  sessions: () => api<{ id: string; size: number; modified: number }[]>('/api/sessions'),
  session: (id: string) => api<{ id: string; events: unknown[] }>(`/api/sessions/${id}`),
  newSession: () => api<{ session_id: string }>('/api/sessions/new', { method: 'POST' }),
  files: (path = '.') => api<{ type: string; path?: string; content?: string; items?: unknown[] }>(`/api/files?path=${encodeURIComponent(path)}`),
};

// WebSocket URL
export function wsUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws/chat`;
}
