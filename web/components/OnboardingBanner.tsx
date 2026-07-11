'use client';

import { AlertCircle, X, Terminal, Key, Smartphone } from 'lucide-react';
import { useState } from 'react';
import { useHelix } from '@/lib/store';

export function OnboardingBanner() {
  const { status, backendReady } = useHelix();
  const [dismissed, setDismissed] = useState(false);

  // Don't show if backend not reachable, or API key set, or dismissed
  if (!backendReady || !status) return null;
  if (status.api_key_set) return null;
  if (dismissed) return null;

  return (
    <div className="border-b border-helix-red/30 bg-helix-red/5 px-4 py-3 lg:pl-4 pl-16">
      <div className="flex items-start gap-2 max-w-4xl mx-auto">
        <AlertCircle size={16} className="text-helix-red mt-0.5 flex-shrink-0" />
        <div className="flex-1 text-xs">
          <div className="font-medium text-helix-red-light mb-1">
            No LLM API key set — HELIX can't think yet.
          </div>
          <div className="text-helix-text-dim space-y-1">
            <div className="flex items-start gap-1.5">
              <Key size={11} className="mt-0.5 text-helix-blue-light" />
              <div>
                Set your key (pick one):
                <pre className="mt-1 p-2 rounded bg-helix-bg/60 border border-helix-border text-[10px] font-mono overflow-x-auto">
{`# Option A: Your gateway
export HELIX_BASE_URL=https://api.gateway.orgn.com
export HELIX_API_KEY=your_key_here
export HELIX_MODEL=gpt-4o-mini

# Option B: Z.ai GLM
export HELIX_PROVIDER=zai ZAI_API_KEY=...

# Option C: Local Ollama (no key)
export HELIX_PROVIDER=ollama HELIX_BASE_URL=http://localhost:11434/v1 HELIX_MODEL=qwen2.5:7b HELIX_API_KEY=ollama`}
                </pre>
              </div>
            </div>
            <div className="flex items-start gap-1.5">
              <Terminal size={11} className="mt-0.5 text-helix-blue-light" />
              <span>Then run <code className="text-helix-blue-light font-mono">helix web</code> and refresh this page.</span>
            </div>
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-helix-text-mute hover:text-helix-text flex-shrink-0"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}

export function PhoneStatusBanner() {
  const { status } = useHelix();
  if (!status) return null;
  if (status.on_termux) return null;

  return (
    <div className="border-b border-helix-blue/20 bg-helix-blue/5 px-4 py-2 lg:pl-4 pl-16">
      <div className="flex items-center gap-2 max-w-4xl mx-auto text-xs">
        <Smartphone size={12} className="text-helix-blue-light" />
        <span className="text-helix-text-dim">
          Running on PC. For full phone control, install HELIX in Termux — see
          <code className="mx-1 text-helix-blue-light">docs/PHONE_SETUP.md</code>.
        </span>
      </div>
    </div>
  );
}
