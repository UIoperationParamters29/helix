'use client';

import { useState } from 'react';
import { Zap, Loader2, CheckCircle2, XCircle, Copy, List } from 'lucide-react';
import { HelixAPI } from '@/lib/api';

type TestResult = {
  ok: boolean;
  config?: { provider: string; model: string; base_url: string | null; api_key_set: boolean; api_key_prefix?: string };
  content?: string;
  finish_reason?: string;
  error?: string;
  status?: number;
  url?: string;
  hint?: string;
  usage?: Record<string, number>;
};

type ModelsResult = {
  ok: boolean;
  url?: string;
  status?: number;
  models?: string[];
  count?: number;
  error?: string;
};

export function TestConnectionButton({ compact = false }: { compact?: boolean }) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [listingModels, setListingModels] = useState(false);
  const [models, setModels] = useState<ModelsResult | null>(null);
  const [modelFilter, setModelFilter] = useState('');

  async function run() {
    setTesting(true);
    setResult(null);
    try {
      const r = await HelixAPI.testLlm();
      setResult(r as TestResult);
    } catch (e) {
      setResult({ ok: false, error: String(e) });
    }
    setTesting(false);
  }

  async function listModels() {
    setListingModels(true);
    setModels(null);
    try {
      const r = await HelixAPI.listModels();
      setModels(r as ModelsResult);
    } catch (e) {
      setModels({ ok: false, error: String(e) });
    }
    setListingModels(false);
  }

  const filteredModels = (models?.models || []).filter(m =>
    !modelFilter || m.toLowerCase().includes(modelFilter.toLowerCase())
  );

  return (
    <div className={compact ? '' : 'space-y-2'}>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={run}
          disabled={testing}
          className="btn btn-primary text-xs"
        >
          {testing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
          {testing ? 'Testing...' : 'Test connection'}
        </button>
        <button
          onClick={listModels}
          disabled={listingModels}
          className="btn btn-ghost text-xs"
        >
          {listingModels ? <Loader2 size={12} className="animate-spin" /> : <List size={12} />}
          {listingModels ? 'Listing...' : 'List models on gateway'}
        </button>
      </div>

      {/* Test result */}
      {result && (
        <div className={
          'card p-3 text-xs space-y-2 ' +
          (result.ok ? 'border-l-2 border-l-green-500/60' : 'border-l-2 border-l-helix-red/60')
        }>
          <div className="flex items-center gap-2">
            {result.ok ? (
              <CheckCircle2 size={14} className="text-green-500 flex-shrink-0" />
            ) : (
              <XCircle size={14} className="text-helix-red flex-shrink-0" />
            )}
            <span className={result.ok ? 'text-green-400 font-medium' : 'text-helix-red-light font-medium'}>
              {result.ok ? 'Connection works!' : 'Connection failed'}
            </span>
          </div>

          {result.config && (
            <div className="font-mono text-[10px] text-helix-text-dim space-y-0.5">
              <div><span className="text-helix-text-mute">provider:</span> {result.config.provider}</div>
              <div><span className="text-helix-text-mute">model:</span> {result.config.model}</div>
              <div><span className="text-helix-text-mute">base_url:</span> {result.config.base_url || '(provider default)'}</div>
              <div>
                <span className="text-helix-text-mute">api_key:</span>{' '}
                {result.config.api_key_set ? (
                  <span className="text-green-400">✓ set ({result.config.api_key_prefix})</span>
                ) : (
                  <span className="text-helix-red">✗ NOT SET</span>
                )}
              </div>
            </div>
          )}

          {result.url && (
            <div className="text-[10px] text-helix-text-mute break-all">
              <span className="text-helix-text-dim">Request URL:</span>
              <pre className="mt-1 p-1.5 rounded bg-helix-bg/60 border border-helix-border text-[10px] font-mono overflow-x-auto">
{result.url}
              </pre>
            </div>
          )}

          {result.status !== undefined && (
            <div className="text-[10px]">
              <span className="text-helix-text-mute">HTTP status:</span>{' '}
              <span className={result.status >= 400 ? 'text-helix-red-light font-mono' : 'text-green-400 font-mono'}>
                {result.status}
              </span>
            </div>
          )}

          {result.ok && result.content && (
            <div className="text-[10px]">
              <span className="text-helix-text-mute">Model replied:</span>{' '}
              <code className="text-helix-blue-light">{result.content}</code>
            </div>
          )}

          {result.error && (
            <div className="text-[10px]">
              <div className="text-helix-text-mute mb-1">Error:</div>
              <pre className="p-1.5 rounded bg-helix-red/10 border border-helix-red/30 text-helix-red-light text-[10px] font-mono whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
{result.error}
              </pre>
            </div>
          )}

          {result.hint && (
            <div className="text-[10px] p-2 rounded bg-helix-blue/10 border border-helix-blue/30 text-helix-blue-light">
              <strong>Hint:</strong> {result.hint}
            </div>
          )}

          {!result.ok && result.config && (
            <div className="text-[10px] space-y-1.5 pt-1">
              <div className="text-helix-text-mute font-medium">Try these fixes:</div>
              {result.status === 404 && (
                <CopyBlock
                  label="Add /v1 to your base URL"
                  content={`export HELIX_BASE_URL=${(result.config.base_url || 'https://api.gateway.orgn.com').replace(/\/v1\/?$/, '')}/v1`}
                />
              )}
              {!result.config.api_key_set && (
                <CopyBlock
                  label="Set your API key"
                  content="export HELIX_API_KEY=your_key_here"
                />
              )}
              {(result.status === 400 || result.status === 200) && (
                <CopyBlock
                  label="Try a different model name (click 'List models on gateway' above to see what's available)"
                  content={`# Common names: gpt-4o-mini, claude-3-5-sonnet, glm-4, qwen2.5-72b
# Click "List models on gateway" above to see what YOUR gateway supports
export HELIX_MODEL=near_glm_5`}
                />
              )}
              <CopyBlock
                label="After changing env vars, restart helix web"
                content="# Ctrl+C to stop, then:\nhelix web"
              />
            </div>
          )}
        </div>
      )}

      {/* Models list */}
      {models && (
        <div className="card p-3 text-xs space-y-2 border-l-2 border-l-helix-blue/40">
          <div className="flex items-center gap-2">
            <List size={14} className="text-helix-blue-light" />
            <span className="font-medium text-helix-text">
              {models.ok ? `${models.count} models on your gateway` : 'Failed to list models'}
            </span>
          </div>

          {!models.ok && models.error && (
            <pre className="p-1.5 rounded bg-helix-red/10 border border-helix-red/30 text-helix-red-light text-[10px] font-mono whitespace-pre-wrap break-words">
{models.error}
            </pre>
          )}

          {models.ok && models.models && (
            <>
              <input
                value={modelFilter}
                onChange={(e) => setModelFilter(e.target.value)}
                placeholder="Filter models... (e.g. glm, gpt, claude)"
                className="text-xs"
              />
              <div className="max-h-64 overflow-y-auto space-y-0.5">
                {filteredModels.slice(0, 200).map((m) => (
                  <div key={m} className="flex items-center justify-between gap-2 group">
                    <code className="text-[10px] text-helix-text-dim group-hover:text-helix-blue-light font-mono">
                      {m}
                    </code>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(`export HELIX_MODEL=${m}`);
                      }}
                      className="opacity-0 group-hover:opacity-100 text-[10px] text-helix-text-mute hover:text-helix-blue-light"
                      title="Copy export command"
                    >
                      <Copy size={10} />
                    </button>
                  </div>
                ))}
                {filteredModels.length > 200 && (
                  <div className="text-[10px] text-helix-text-mute pt-1">
                    + {filteredModels.length - 200} more — refine filter to see them
                  </div>
                )}
              </div>
              {models.url && (
                <div className="text-[10px] text-helix-text-mute">
                  Source: <code className="font-mono">{models.url}</code>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function CopyBlock({ label, content }: { label: string; content: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div>
      <div className="text-helix-text-mute mb-0.5">{label}</div>
      <div className="relative">
        <pre className="p-1.5 pr-7 rounded bg-helix-bg/60 border border-helix-border text-[10px] font-mono overflow-x-auto">
{content}
        </pre>
        <button
          onClick={() => {
            navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          }}
          className="absolute top-1 right-1 p-1 rounded bg-helix-bg-elev/80 hover:bg-helix-bg-elev border border-helix-border text-helix-text-dim"
        >
          {copied ? <CheckCircle2 size={10} className="text-green-500" /> : <Copy size={10} />}
        </button>
      </div>
    </div>
  );
}
