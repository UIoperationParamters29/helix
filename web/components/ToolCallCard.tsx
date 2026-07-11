'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, XCircle, Terminal, FileText, Globe, Phone, Brain, Wrench } from 'lucide-react';
import type { ToolCall } from '@/lib/store';
import { cn } from '@/lib/utils';

// Pick an icon per tool category
function toolIcon(name: string) {
  if (name.startsWith('phone_ui') || name === 'phone_screen_state' || name === 'phone_screen_wake') return Phone;
  if (name.startsWith('phone_app')) return Phone;
  if (name.startsWith('phone_')) return Phone;
  if (name.startsWith('file_')) return FileText;
  if (name.startsWith('web_')) return Globe;
  if (name.startsWith('skill_') || name.startsWith('memory_')) return Brain;
  if (name === 'bash') return Terminal;
  return Wrench;
}

export function ToolCallCard({ tc }: { tc: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = toolIcon(tc.tool);

  const statusVisual = tc.status === 'running' ? (
    <div className="flex items-center gap-1.5 text-helix-blue-light">
      <Loader2 size={12} className="animate-spin" />
      <span className="text-[10px] uppercase tracking-wider">Running</span>
    </div>
  ) : tc.status === 'done' ? (
    <div className="flex items-center gap-1.5 text-green-500">
      <CheckCircle2 size={12} />
      <span className="text-[10px] uppercase tracking-wider">Done</span>
    </div>
  ) : tc.status === 'error' ? (
    <div className="flex items-center gap-1.5 text-helix-red">
      <XCircle size={12} />
      <span className="text-[10px] uppercase tracking-wider">Error</span>
    </div>
  ) : null;

  // Truncate args for the collapsed view
  const argEntries = Object.entries(tc.args);
  const argsStr = argEntries
    .map(([k, v]) => {
      const vs = typeof v === 'string' ? v : JSON.stringify(v);
      return `${k}=${vs.length > 50 ? vs.slice(0, 50) + '…' : vs}`;
    })
    .join(', ');

  return (
    <div className={cn(
      'card border-l-2 text-sm overflow-hidden transition-colors',
      tc.status === 'running' && 'border-l-helix-blue-light/60',
      tc.status === 'done' && 'border-l-green-500/60',
      tc.status === 'error' && 'border-l-helix-red/60',
    )}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-2.5 text-left hover:bg-helix-bg-elev/40"
      >
        <Icon size={14} className="text-helix-text-dim flex-shrink-0" />
        <span className="font-mono text-helix-blue-light font-medium text-xs">{tc.tool}</span>
        <span className="text-helix-text-mute text-[10px] font-mono truncate flex-1">({argsStr})</span>
        <div className="flex-shrink-0">{statusVisual}</div>
        {expanded ? <ChevronDown size={14} className="text-helix-text-mute flex-shrink-0" /> : <ChevronRight size={14} className="text-helix-text-mute flex-shrink-0" />}
      </button>
      {expanded && tc.output && (
        <div className="border-t border-helix-border p-2.5 bg-helix-bg/40">
          <pre className={cn(
            'text-[11px] font-mono whitespace-pre-wrap break-words max-h-80 overflow-y-auto',
            tc.is_error ? 'text-helix-red-light' : 'text-helix-text-dim'
          )}>
            {tc.output}
          </pre>
        </div>
      )}
    </div>
  );
}
