'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import type { ToolCall } from '@/lib/store';
import { cn } from '@/lib/utils';

export function ToolCallCard({ tc }: { tc: ToolCall }) {
  const [expanded, setExpanded] = useState(false);

  const statusIcon = tc.status === 'running' ? (
    <Loader2 size={14} className="animate-spin text-helix-blue-light" />
  ) : tc.status === 'done' ? (
    <CheckCircle2 size={14} className="text-green-500" />
  ) : tc.status === 'error' ? (
    <XCircle size={14} className="text-helix-red" />
  ) : (
    <div className="w-3 h-3 rounded-full bg-helix-text-mute" />
  );

  // Truncate args for display
  const argsStr = Object.entries(tc.args)
    .map(([k, v]) => {
      const vs = typeof v === 'string' ? v : JSON.stringify(v);
      return `${k}=${vs.length > 60 ? vs.slice(0, 60) + '…' : vs}`;
    })
    .join(', ');

  return (
    <div className="card border-l-2 border-l-helix-blue-light/40 text-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-2.5 text-left hover:bg-helix-bg-elev/40 rounded-lg"
      >
        {statusIcon}
        <span className="font-mono text-helix-blue-light font-medium">{tc.tool}</span>
        <span className="text-helix-text-dim text-xs truncate flex-1 font-mono">({argsStr})</span>
        {expanded ? <ChevronDown size={14} className="text-helix-text-mute" /> : <ChevronRight size={14} className="text-helix-text-mute" />}
      </button>
      {expanded && tc.output && (
        <div className="border-t border-helix-border p-2.5">
          <pre className={cn(
            'text-xs font-mono whitespace-pre-wrap break-words max-h-80 overflow-y-auto',
            tc.is_error ? 'text-helix-red-light' : 'text-helix-text-dim'
          )}>
            {tc.output}
          </pre>
        </div>
      )}
    </div>
  );
}
