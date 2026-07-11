'use client';

import { Settings, Cpu, Smartphone, AlertCircle, ExternalLink, Copy, Check, Key } from 'lucide-react';
import { useState } from 'react';
import { useHelix } from '@/lib/store';

export function SettingsView() {
  const status = useHelix((s) => s.status);
  const [copied, setCopied] = useState(false);

  const rows: { label: string; value: string | boolean | undefined }[] = status ? [
    { label: 'HELIX_HOME', value: status.home as string },
    { label: 'Provider', value: status.provider as string },
    { label: 'Model', value: status.model as string },
    { label: 'Base URL', value: (status.base_url as string) || '(provider default)' },
    { label: 'API key set', value: status.api_key_set as boolean },
    { label: 'On Termux', value: status.on_termux as boolean },
    { label: 'Persona', value: status.persona as string },
  ] : [];

  // Snippet for the user's most likely config
  const setupSnippet = status?.on_termux
    ? `# In Termux (add to ~/.bashrc):
export HELIX_BASE_URL=https://api.gateway.orgn.com
export HELIX_API_KEY=YOUR_KEY_HERE
export HELIX_MODEL=gpt-4o-mini   # or whatever your gateway serves

helix web`
    : `# On PC (add to ~/.bashrc or ~/.zshrc):
export HELIX_BASE_URL=https://api.gateway.orgn.com
export HELIX_API_KEY=YOUR_KEY_HERE
export HELIX_MODEL=gpt-4o-mini

helix web`;

  function copySnippet() {
    navigator.clipboard.writeText(setupSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-helix-border px-4 py-3 flex items-center gap-2 lg:pl-4 pl-16">
        <Settings size={16} className="text-helix-blue" />
        <span className="font-medium">Settings</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 max-w-2xl">
        {/* Quick setup */}
        <div className="card p-4 border-l-2 border-l-helix-blue/40">
          <div className="flex items-center gap-2 mb-3">
            <Key size={14} className="text-helix-blue" />
            <span className="font-medium text-sm">Quick setup</span>
          </div>
          <div className="text-xs text-helix-text-dim mb-2">
            Set these env vars, restart <code className="text-helix-blue-light">helix web</code>, done.
          </div>
          <div className="relative">
            <pre className="text-[11px] font-mono bg-helix-bg/60 border border-helix-border rounded-lg p-3 overflow-x-auto text-helix-text">
{setupSnippet}
            </pre>
            <button
              onClick={copySnippet}
              className="absolute top-2 right-2 p-1.5 rounded bg-helix-bg-elev/80 hover:bg-helix-bg-elev border border-helix-border text-helix-text-dim hover:text-helix-text"
              title="Copy to clipboard"
            >
              {copied ? <Check size={12} className="text-green-500" /> : <Copy size={12} />}
            </button>
          </div>
        </div>

        {/* Runtime status */}
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Cpu size={14} className="text-helix-blue" />
            <span className="font-medium text-sm">Runtime status</span>
          </div>
          <div className="space-y-1.5">
            {rows.map((r) => (
              <div key={r.label} className="flex items-center justify-between text-xs">
                <span className="text-helix-text-dim">{r.label}</span>
                <span className="font-mono">
                  {typeof r.value === 'boolean' ? (
                    <span className={r.value ? 'text-green-400' : 'text-helix-red'}>
                      {r.value ? '✓ yes' : '✗ no'}
                    </span>
                  ) : (
                    <span className="text-helix-text">{r.value || '—'}</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Phone control */}
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Smartphone size={14} className="text-helix-red" />
            <span className="font-medium text-sm">Phone control</span>
          </div>
          <div className="text-xs text-helix-text-dim space-y-2">
            <p>
              To enable phone control, run HELIX inside <strong>Termux</strong> on Android.
              The agent gains access to:
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Hardware</strong>: battery, sensors, torch, vibrate, volume, brightness</li>
              <li><strong>Communications</strong>: SMS, calls, notifications</li>
              <li><strong>Apps</strong>: launch, list, force-stop</li>
              <li><strong>Camera</strong>: take photos</li>
              <li><strong>Location</strong>: GPS coordinates</li>
              <li><strong>UI automation</strong> (requires self-ADB): tap, swipe, type, screenshot, dump UI tree</li>
            </ul>
            <div className="mt-3 p-2 rounded bg-helix-bg-elev/50 border border-helix-border">
              <div className="flex items-center gap-1.5 text-helix-blue-light mb-1">
                <AlertCircle size={12} />
                <span className="font-medium">Setup</span>
              </div>
              See <code className="text-helix-blue-light">docs/PHONE_SETUP.md</code> in the repo for full instructions,
              including how to pair self-ADB for UI automation.
            </div>
          </div>
        </div>

        <div className="card p-4 border-l-2 border-l-helix-red/40">
          <div className="text-xs">
            <div className="font-medium text-helix-red-light mb-1">Security reminder</div>
            <div className="text-helix-text-dim">
              HELIX has full system access when running on your device. Review the
              <code className="mx-1 text-helix-blue-light">dangerous_patterns</code> list in config,
              and keep <code className="text-helix-blue-light">auto_approve_writes: false</code> unless you trust the agent fully.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
