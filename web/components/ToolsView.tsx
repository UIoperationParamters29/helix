'use client';

import { useState } from 'react';
import { Wrench, Search } from 'lucide-react';
import { useHelix } from '@/lib/store';
import { cn } from '@/lib/utils';

type Tool = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  dangerous: boolean;
  read_only: boolean;
  tags: string[];
};

export function ToolsView() {
  const tools = useHelix((s) => s.tools) as Tool[];
  const [filter, setFilter] = useState('');
  const [tag, setTag] = useState<string | null>(null);

  const allTags = Array.from(new Set(tools.flatMap((t) => t.tags || []))).sort();

  const filtered = tools.filter((t) => {
    if (filter) {
      const f = filter.toLowerCase();
      if (!t.name.toLowerCase().includes(f) && !t.description.toLowerCase().includes(f)) {
        return false;
      }
    }
    if (tag && !(t.tags || []).includes(tag)) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-helix-border px-4 py-3 flex items-center gap-3 lg:pl-4 pl-16">
        <Wrench size={16} className="text-helix-blue" />
        <span className="font-medium">Tools</span>
        <span className="text-xs text-helix-text-mute">({tools.length})</span>
        <div className="flex-1" />
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-helix-text-mute" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search tools..."
            className="pl-9 py-1.5 text-sm w-48"
          />
        </div>
      </div>

      {/* Tag filter */}
      <div className="px-4 py-2 border-b border-helix-border flex gap-1 flex-wrap overflow-x-auto no-scrollbar">
        <button
          onClick={() => setTag(null)}
          className={cn(
            'text-xs px-2 py-1 rounded-md transition-colors',
            !tag ? 'bg-helix-blue/20 text-helix-blue-light' : 'text-helix-text-dim hover:bg-helix-bg-elev'
          )}
        >
          all
        </button>
        {allTags.map((t) => (
          <button
            key={t}
            onClick={() => setTag(t === tag ? null : t)}
            className={cn(
              'text-xs px-2 py-1 rounded-md transition-colors whitespace-nowrap',
              t === tag ? 'bg-helix-blue/20 text-helix-blue-light' : 'text-helix-text-dim hover:bg-helix-bg-elev'
            )}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {filtered.map((t) => (
          <div key={t.name} className="card p-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono font-medium text-helix-blue-light">{t.name}</span>
              {t.dangerous && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-helix-red/20 text-helix-red-light border border-helix-red/30">
                  dangerous
                </span>
              )}
              {t.read_only && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 border border-green-500/30">
                  read-only
                </span>
              )}
              {(t.tags || []).map((tag) => (
                <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-helix-bg-elev text-helix-text-dim">
                  {tag}
                </span>
              ))}
            </div>
            <div className="text-xs text-helix-text-dim mt-1.5">{t.description}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
