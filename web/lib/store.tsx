'use client';

import { create } from 'zustand';

export type ToolCall = {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  thought?: string;
  ts: number;
  status: 'pending' | 'running' | 'done' | 'error';
  output?: string;
  is_error?: boolean;
  metadata?: Record<string, unknown>;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  ts: number;
  toolCalls?: ToolCall[];
};

// Tool calls that are done (completed or errored) get moved from pendingToolCalls
// to the message they belong to. This keeps the chat clean — only currently-running
// tool calls show in the "pending" area.

export type Session = {
  id: string;
  size: number;
  modified: number;
};

export type Skill = {
  name: string;
  title: string;
  description: string;
  path: string;
};

type HelixState = {
  // Connection
  backendReady: boolean;
  ws: WebSocket | null;

  // Session
  sessionId: string | null;
  messages: ChatMessage[];
  pendingToolCalls: Record<string, ToolCall>;
  isStreaming: boolean;

  // Data
  sessions: Session[];
  skills: Skill[];
  tools: unknown[];
  status: Record<string, unknown> | null;
  memory: Record<string, string> | null;

  // UI
  sidebarOpen: boolean;
  activeView: 'chat' | 'sessions' | 'skills' | 'tools' | 'files' | 'memory' | 'settings';

  // Actions
  setBackendReady: (v: boolean) => void;
  setWs: (ws: WebSocket | null) => void;
  setSessionId: (id: string | null) => void;
  addMessage: (m: ChatMessage) => void;
  appendToMessage: (id: string, content: string) => void;
  setStreaming: (v: boolean) => void;
  upsertToolCall: (tc: ToolCall) => void;
  updateToolCall: (id: string, patch: Partial<ToolCall>) => void;
  setSessions: (s: Session[]) => void;
  setSkills: (s: Skill[]) => void;
  setTools: (t: unknown[]) => void;
  setStatus: (s: Record<string, unknown> | null) => void;
  setMemory: (m: Record<string, string> | null) => void;
  setSidebarOpen: (v: boolean) => void;
  setActiveView: (v: HelixState['activeView']) => void;
  reset: () => void;
};

export const useHelix = create<HelixState>((set, get) => ({
  backendReady: false,
  ws: null,
  sessionId: null,
  messages: [],
  pendingToolCalls: {},
  isStreaming: false,
  sessions: [],
  skills: [],
  tools: [],
  status: null,
  memory: null,
  sidebarOpen: false,
  activeView: 'chat',

  setBackendReady: (v) => set({ backendReady: v }),
  setWs: (ws) => set({ ws }),
  setSessionId: (id) => set({ sessionId: id }),
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  appendToMessage: (id, content) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + content } : m
      ),
    })),
  setStreaming: (v) => set({ isStreaming: v }),
  upsertToolCall: (tc) =>
    set((s) => ({ pendingToolCalls: { ...s.pendingToolCalls, [tc.id]: tc } })),
  updateToolCall: (id, patch) =>
    set((s) => {
      const tc = s.pendingToolCalls[id];
      if (!tc) return {};
      const updated = { ...tc, ...patch };
      // If the tool call is now done/error, move it to the last assistant message
      // and remove from pending. This keeps the pending area clean — only
      // currently-running tools show there.
      if (updated.status === 'done' || updated.status === 'error') {
        const messages = [...s.messages];
        // Find the last assistant message to attach this tool call to
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === 'assistant' || messages[i].role === 'user') {
            messages[i] = {
              ...messages[i],
              toolCalls: [...(messages[i].toolCalls || []), updated],
            };
            break;
          }
        }
        const newPending = { ...s.pendingToolCalls };
        delete newPending[id];
        return { pendingToolCalls: newPending, messages };
      }
      return { pendingToolCalls: { ...s.pendingToolCalls, [id]: updated } };
    }),
  setSessions: (sessions) => set({ sessions }),
  setSkills: (skills) => set({ skills }),
  setTools: (tools) => set({ tools }),
  setStatus: (status) => set({ status }),
  setMemory: (memory) => set({ memory }),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setActiveView: (activeView) => set({ activeView, sidebarOpen: false }),
  reset: () => set({
    sessionId: null, messages: [], pendingToolCalls: {}, isStreaming: false,
  }),
}));

// HelixProvider — wraps app, runs initial fetches
export function HelixProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

// Note: keep 'use client' at top — this file uses Zustand + JSX.
