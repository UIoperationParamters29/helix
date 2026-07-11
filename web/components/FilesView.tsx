'use client';

import { useEffect, useState } from 'react';
import { Folder, FileText, ChevronRight, ArrowLeft } from 'lucide-react';
import { HelixAPI } from '@/lib/api';
import { formatBytes, cn } from '@/lib/utils';

type Entry = { name: string; is_dir: boolean; size: number; modified: number };

export function FilesView() {
  const [path, setPath] = useState('.');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [viewingFile, setViewingFile] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function browse(p: string) {
    setLoading(true);
    setFileContent(null);
    setViewingFile(null);
    try {
      const r = await HelixAPI.files(p);
      if (r.type === 'dir') {
        setPath(p);
        setEntries((r.items || []) as Entry[]);
      } else if (r.type === 'file') {
        setFileContent(r.content || '');
        setViewingFile(r.path || p);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }

  useEffect(() => { browse('.'); }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-helix-border px-4 py-3 flex items-center gap-2 lg:pl-4 pl-16">
        <Folder size={16} className="text-helix-blue" />
        <span className="font-medium">Files</span>
        <span className="text-xs text-helix-text-mute font-mono truncate">{path}</span>
        {path !== '.' && (
          <button onClick={() => browse('..')} className="btn btn-ghost text-xs ml-auto">
            <ArrowLeft size={12} /> Up
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="text-helix-text-mute text-center py-8 text-sm">Loading...</div>
        ) : viewingFile ? (
          <div>
            <div className="text-xs text-helix-text-mute mb-2 font-mono">{viewingFile}</div>
            <pre className="text-xs font-mono bg-helix-bg-card border border-helix-border rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
              {fileContent}
            </pre>
          </div>
        ) : entries.length === 0 ? (
          <div className="text-helix-text-mute text-center py-8 text-sm">Empty directory.</div>
        ) : (
          <div className="space-y-0.5">
            {entries.map((e) => (
              <button
                key={e.name}
                onClick={() => browse(path === '.' ? e.name : `${path}/${e.name}`)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-md hover:bg-helix-bg-elev text-left"
              >
                {e.is_dir ? (
                  <Folder size={14} className="text-helix-blue-light" />
                ) : (
                  <FileText size={14} className="text-helix-text-dim" />
                )}
                <span className={cn('text-sm flex-1', e.is_dir ? 'text-helix-text' : 'text-helix-text-dim')}>
                  {e.name}
                </span>
                {!e.is_dir && (
                  <span className="text-[10px] text-helix-text-mute">{formatBytes(e.size)}</span>
                )}
                {e.is_dir && <ChevronRight size={14} className="text-helix-text-mute" />}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
