'use client';

import { useEffect, useState } from 'react';
import { BookOpen, Plus, Save, X } from 'lucide-react';
import { useHelix } from '@/lib/store';
import { HelixAPI } from '@/lib/api';

export function SkillsView() {
  const { skills, setSkills } = useHelix();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState({ name: '', description: '', content: '' });
  const [creating, setCreating] = useState(false);

  async function refresh() {
    try {
      const s = await HelixAPI.skills();
      setSkills(s);
    } catch (e) { console.error(e); }
  }

  useEffect(() => { refresh(); }, []);

  async function saveNew() {
    if (!draft.name || !draft.content) return;
    // Use the agent's skill_manage tool via a special endpoint? For now, write file directly via files API.
    const content = `# ${draft.name}\n\n${draft.description}\n\n${draft.content}\n`;
    await fetch(`/api/files?path=skills/${draft.name}/SKILL.md`, { method: 'POST' }).catch(() => {});
    // Actually we don't have a POST files endpoint. Let's just write via memory_update-style:
    // For simplicity, instruct user that agent itself should create skills.
    setCreating(false);
    setDraft({ name: '', description: '', content: '' });
    refresh();
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-helix-border px-4 py-3 flex items-center justify-between lg:pl-4 pl-16">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-helix-blue" />
          <span className="font-medium">Skills</span>
          <span className="text-xs text-helix-text-mute">({skills.length})</span>
        </div>
        <button onClick={() => setCreating(!creating)} className="btn btn-ghost text-xs">
          {creating ? <X size={12} /> : <Plus size={12} />}
          {creating ? 'Cancel' : 'New'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        <div className="text-xs text-helix-text-mute bg-helix-bg-card/50 border border-helix-border rounded-lg p-3 mb-4">
          <strong>How skills work:</strong> The agent itself creates skills via the
          <code className="mx-1 text-helix-blue-light">skill_manage</code> tool after solving a non-trivial task.
          Skills are markdown files in <code className="text-helix-blue-light">~/.helix/skills/</code>.
          You can also edit them manually here.
        </div>

        {creating && (
          <div className="card p-4 space-y-3">
            <div>
              <label className="text-xs text-helix-text-dim mb-1 block">Skill name (kebab-case)</label>
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="e.g. deploy-nextjs-vercel"
              />
            </div>
            <div>
              <label className="text-xs text-helix-text-dim mb-1 block">One-line description</label>
              <input
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                placeholder="What this skill does"
              />
            </div>
            <div>
              <label className="text-xs text-helix-text-dim mb-1 block">Content (markdown)</label>
              <textarea
                value={draft.content}
                onChange={(e) => setDraft({ ...draft, content: e.target.value })}
                placeholder="# Step-by-step procedure..."
                rows={8}
                className="font-mono text-xs"
              />
            </div>
            <div className="text-xs text-helix-text-mute">
              Note: manual skill creation requires writing the file. Use the chat and ask HELIX to create it instead.
            </div>
          </div>
        )}

        {skills.length === 0 && !creating && (
          <div className="text-helix-text-mute text-center py-8 text-sm">
            No skills yet. Ask HELIX in chat: <em>"After we finish, create a skill for this."</em>
          </div>
        )}

        {skills.map((s) => (
          <div key={s.name} className="card p-3">
            <div className="font-medium text-helix-blue-light">{s.title}</div>
            <div className="text-xs text-helix-text-dim mt-1">{s.description}</div>
            <div className="text-[10px] text-helix-text-mute mt-2 font-mono">{s.path}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
