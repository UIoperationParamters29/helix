'use client';

import { useEffect, useState } from 'react';
import { Clock, Trash2, Plus } from 'lucide-react';
import { useHelix } from '@/lib/store';
import { HelixAPI } from '@/lib/api';
import { formatTime, formatBytes } from '@/lib/utils';

export function SessionsView() {
  const { sessions, setSessions, setSessionId, setActiveView, reset } = useHelix();
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const s = await HelixAPI.sessions();
      setSessions(s);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  useEffect(() => { refresh(); }, []);

  async function newSession() {
    const s = await HelixAPI.newSession();
    setSessionId(s.session_id);
    reset();
    setActiveView('chat');
  }

  async function openSession(id: string) {
    setSessionId(id);
    reset();
    setActiveView('chat');
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-helix-border px-4 py-3 flex items-center justify-between lg:pl-4 pl-16">
        <div className="flex items-center gap-2">
          <Clock size={16} className="text-helix-blue" />
          <span className="font-medium">Sessions</span>
          <span className="text-xs text-helix-text-mute">({sessions.length})</span>
        </div>
        <button onClick={newSession} className="btn btn-primary text-xs">
          <Plus size={12} /> New
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {loading ? (
          <div className="text-helix-text-mute text-center py-8 text-sm">Loading...</div>
        ) : sessions.length === 0 ? (
          <div className="text-helix-text-mute text-center py-8 text-sm">No sessions yet.</div>
        ) : (
          sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => openSession(s.id)}
              className="card w-full p-3 text-left hover:border-helix-blue/40 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="font-mono text-xs text-helix-blue-light">{s.id}</div>
                <div className="text-[10px] text-helix-text-mute">{formatBytes(s.size)}</div>
              </div>
              <div className="text-[10px] text-helix-text-mute mt-1">{formatTime(s.modified)}</div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
