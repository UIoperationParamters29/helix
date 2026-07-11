'use client';

import { useState } from 'react';
import { Brain, Save } from 'lucide-react';
import { useHelix } from '@/lib/store';
import { HelixAPI } from '@/lib/api';
import { cn } from '@/lib/utils';

const KINDS = ['IDENTITY', 'USER', 'MEMORY'] as const;
type Kind = typeof KINDS[number];

const DESCRIPTIONS: Record<Kind, string> = {
  IDENTITY: "The agent's persona. Rarely changed. Defines how HELIX presents itself.",
  USER: 'Facts about the user: name, preferences, projects, contact info.',
  MEMORY: 'General persistent notes. Lessons learned, recurring patterns, important context.',
};

export function MemoryView() {
  const { memory, setMemory } = useHelix();
  const [editing, setEditing] = useState<Kind | null>(null);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  function startEdit(kind: Kind) {
    setEditing(kind);
    setDraft(memory?.[kind] || '');
  }

  async function save() {
    if (!editing) return;
    setSaving(true);
    try {
      await HelixAPI.updateMemory(editing, draft);
      setMemory({ ...(memory || {}), [editing]: draft });
      setEditing(null);
    } catch (e) {
      console.error(e);
    }
    setSaving(false);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-helix-border px-4 py-3 flex items-center gap-2 lg:pl-4 pl-16">
        <Brain size={16} className="text-helix-blue" />
        <span className="font-medium">Memory</span>
        <span className="text-xs text-helix-text-mute">Agent-owned learning</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {KINDS.map((kind) => (
          <div key={kind} className="card p-3">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-medium text-sm">{kind}.md</div>
                <div className="text-[10px] text-helix-text-mute">{DESCRIPTIONS[kind]}</div>
              </div>
              {editing !== kind ? (
                <button onClick={() => startEdit(kind)} className="btn btn-ghost text-xs">
                  Edit
                </button>
              ) : (
                <button onClick={save} disabled={saving} className="btn btn-primary text-xs">
                  <Save size={12} /> {saving ? 'Saving...' : 'Save'}
                </button>
              )}
            </div>
            {editing === kind ? (
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={10}
                className="font-mono text-xs"
              />
            ) : (
              <pre className="text-xs font-mono whitespace-pre-wrap text-helix-text-dim bg-helix-bg/50 border border-helix-border rounded p-2 max-h-64 overflow-y-auto">
                {memory?.[kind] || '(empty)'}
              </pre>
            )}
          </div>
        ))}

        <div className="card p-3 border-l-2 border-l-helix-blue/40">
          <div className="text-xs text-helix-text-dim">
            <strong className="text-helix-blue-light">Self-improvement loop:</strong>{' '}
            After solving a non-trivial task, HELIX appends lessons to MEMORY and may create skills.
            These persist across sessions and shape future behavior. Edit freely — the agent respects your overrides.
          </div>
        </div>
      </div>
    </div>
  );
}
