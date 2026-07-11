'use client';

import { useEffect, useRef, useState } from 'react';
import { Send, Loader2, AlertTriangle, Sparkles, Zap, Cpu, Wifi } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useHelix, type ChatMessage, type ToolCall } from '@/lib/store';
import { HelixAPI, wsUrl } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ToolCallCard } from './ToolCallCard';
import { OnboardingBanner, PhoneStatusBanner } from './OnboardingBanner';
import { QuickActions } from './QuickActions';

const EXAMPLE_PROMPTS = [
  {
    icon: '📷',
    title: 'Take a screenshot',
    desc: 'See what is on my screen right now',
    prompt: 'Take a screenshot of my phone screen and tell me what is visible.',
  },
  {
    icon: '🔋',
    title: 'Battery status',
    desc: 'Check my phone battery + charging state',
    prompt: "What's my phone battery level and charging state?",
  },
  {
    icon: '💬',
    title: 'Read my SMS',
    desc: 'Show recent text messages',
    prompt: 'Read my 5 most recent SMS messages and summarize them.',
  },
  {
    icon: '🌐',
    title: 'Browse a website',
    desc: 'Open Chrome and visit a URL',
    prompt: 'Open https://news.ycombinator.com in Chrome and tell me the top 3 headlines.',
  },
  {
    icon: '📁',
    title: 'Organize files',
    desc: 'List + clean up a directory',
    prompt: 'List all files in HELIX_HOME and suggest what to clean up.',
  },
  {
    icon: '🧠',
    title: 'Create a skill',
    desc: 'Teach yourself something new',
    prompt: 'Create a skill called "morning-routine" that captures how to: take a screenshot, read my SMS, and post a notification summarizing both.',
  },
];

export function ChatView() {
  const {
    sessionId, setSessionId, messages, addMessage,
    isStreaming, setStreaming, upsertToolCall, updateToolCall,
    pendingToolCalls, backendReady, status,
  } = useHelix();
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, pendingToolCalls]);

  // WebSocket setup with AUTO-RECONNECT
  // When the tab is backgrounded (user switches to another app), the browser
  // closes the WebSocket. We auto-reconnect when the tab comes back.
  useEffect(() => {
    if (!sessionId) return;

    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectAttempts = 0;
    let shouldReconnect = true;

    function connect() {
      ws = new WebSocket(wsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempts = 0;
        setError(null);
        ws!.send(JSON.stringify({ type: 'hello', session_id: sessionId }));
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          handleWsMessage(msg);
        } catch (e) {
          console.error('bad ws message', e);
        }
      };

      ws.onerror = () => {
        // Don't set error here — onclose will handle reconnect
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (shouldReconnect) {
          reconnectAttempts++;
          const delay = Math.min(1000 * reconnectAttempts, 5000); // 1s, 2s, 3s... max 5s
          setError(`Connection lost — reconnecting in ${delay/1000}s... (attempt ${reconnectAttempts})`);
          reconnectTimer = setTimeout(() => {
            if (shouldReconnect) connect();
          }, delay);
        } else {
          setError('WebSocket closed');
        }
      };
    }

    connect();

    // Cleanup on unmount
    return () => {
      shouldReconnect = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
    // eslint-disable-next-line
  }, [sessionId]);

  function handleWsMessage(msg: any) {
    if (msg.type === 'session_ready') {
      if (msg.session_id !== sessionId) setSessionId(msg.session_id);
      return;
    }
    if (msg.type === 'error') {
      setError(msg.message);
      setStreaming(false);
      return;
    }
    if (msg.type === 'done') {
      setStreaming(false);
      return;
    }

    const data = msg.data;
    if (!data) return;

    if (msg.type === 'message') {
      if (data.role === 'user') return; // we added locally
      addMessage({
        id: data.id,
        role: data.role,
        content: data.content,
        ts: data.ts,
      });
    } else if (msg.type === 'action') {
      const tc: ToolCall = {
        id: data.id,
        tool: data.tool,
        args: data.args,
        thought: data.thought,
        ts: data.ts,
        status: 'running',
      };
      upsertToolCall(tc);
    } else if (msg.type === 'observation') {
      updateToolCall(data.action_id, {
        status: data.is_error ? 'error' : 'done',
        output: data.output,
        is_error: data.is_error,
        metadata: data.metadata,
      });
    } else if (msg.type === 'error') {
      setError(data.message);
    }
  }

  async function send(text?: string) {
    const content = (text ?? input).trim();
    if (!content || isStreaming) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket not connected');
      return;
    }
    setError(null);

    addMessage({
      id: `u-${Date.now()}`,
      role: 'user',
      content,
      ts: Date.now() / 1000,
    });

    setInput('');
    setStreaming(true);
    wsRef.current.send(JSON.stringify({ type: 'send', content }));
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  const pendingList = Object.values(pendingToolCalls).sort((a, b) => a.ts - b.ts);
  const apiKeySet = status?.api_key_set;

  return (
    <div className="flex flex-col h-full">
      {/* Onboarding */}
      <OnboardingBanner />
      <PhoneStatusBanner />

      {/* Top bar — status pill */}
      <div className="border-b border-helix-border px-4 py-2.5 flex items-center justify-between lg:pl-4 pl-16">
        <div className="flex items-center gap-2 text-xs">
          <span className="font-medium">Chat</span>
          {sessionId && (
            <span className="text-helix-text-mute font-mono text-[10px]">#{sessionId.slice(0, 8)}</span>
          )}
        </div>
        <StatusPill />
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && pendingList.length === 0 ? (
          <EmptyState onPick={(p) => send(p)} apiKeySet={!!apiKeySet} />
        ) : (
          <>
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {/* Only show CURRENTLY RUNNING tool calls in the pending area.
                Completed ones are now attached to their message. */}
            {pendingList.length > 0 && (
              <div className="space-y-2">
                {pendingList.map((tc) => (
                  <ToolCallCard key={tc.id} tc={tc} />
                ))}
              </div>
            )}
            {isStreaming && pendingList.length === 0 && (
              <div className="flex items-center gap-2 text-xs text-helix-text-mute pl-2">
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-helix-blue rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-helix-blue rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-helix-blue rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
                HELIX is working...
              </div>
            )}
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mb-2 p-3 rounded-lg bg-helix-red/10 border border-helix-red/30 text-helix-red-light text-sm flex items-center gap-2">
          <AlertTriangle size={14} className="flex-shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-helix-text-mute hover:text-helix-text">×</button>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-helix-border p-3 space-y-2">
        {/* Quick actions */}
        <QuickActions onPick={(p) => send(p)} />

        {/* Input row */}
        <div className="flex items-end gap-2 max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder={apiKeySet ? "Tell HELIX what to do..." : "Set API key first (see banner above)"}
            rows={1}
            className="flex-1 resize-none max-h-32"
            style={{ minHeight: '42px' }}
            disabled={isStreaming || !apiKeySet}
          />
          <button
            onClick={() => send()}
            disabled={!input.trim() || isStreaming || !apiKeySet}
            className="btn btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isStreaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            <span className="hidden sm:inline">{isStreaming ? 'Working' : 'Send'}</span>
          </button>
        </div>
        <div className="text-[10px] text-helix-text-mute text-center">
          Enter to send · Shift+Enter for newline · Quick actions above
        </div>
      </div>
    </div>
  );
}

function StatusPill() {
  const { backendReady, status } = useHelix();
  return (
    <div className="flex items-center gap-3 text-[10px]">
      {/* Connection */}
      <div className="flex items-center gap-1.5">
        <div className={cn(
          'w-2 h-2 rounded-full',
          backendReady ? 'bg-green-500' : 'bg-helix-red animate-pulse'
        )} />
        <Wifi size={10} className={backendReady ? 'text-green-500' : 'text-helix-red'} />
        <span className="text-helix-text-dim">{backendReady ? 'Live' : 'Off'}</span>
      </div>
      {status ? (
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-helix-bg-card border border-helix-border">
          <Cpu size={10} className="text-helix-blue-light" />
          <span className="text-helix-text-dim font-mono">
            {String(status.provider)}/{String(status.model)}
          </span>
        </div>
      ) : null}
      {status?.on_termux ? (
        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-helix-red/10 border border-helix-red/30">
          <Zap size={10} className="text-helix-red-light" />
          <span className="text-helix-red-light">Phone</span>
        </div>
      ) : null}
    </div>
  );
}

function EmptyState({ onPick, apiKeySet }: { onPick: (p: string) => void; apiKeySet: boolean }) {
  return (
    <div className="max-w-2xl mx-auto py-8">
      {/* Logo + welcome */}
      <div className="text-center mb-8">
        <div className="relative w-16 h-16 mx-auto mb-4 flex items-center justify-center">
          <div className="absolute w-14 h-1.5 bg-gradient-to-r from-helix-red to-transparent rounded-full" style={{ transform: 'translateY(-10px) rotate(18deg)' }} />
          <div className="absolute w-14 h-1.5 bg-gradient-to-r from-transparent to-helix-blue rounded-full" style={{ transform: 'translateY(10px) rotate(-18deg)' }} />
          <div className="absolute w-14 h-1.5 bg-gradient-to-r from-helix-red/50 to-transparent rounded-full" style={{ transform: 'rotate(18deg)' }} />
          <div className="absolute w-14 h-1.5 bg-gradient-to-r from-transparent to-helix-blue/50 rounded-full" style={{ transform: 'rotate(-18deg)' }} />
        </div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-helix-red via-helix-text to-helix-blue bg-clip-text text-transparent">
          HELIX is ready
        </h1>
        <p className="text-sm text-helix-text-mute mt-2 max-w-md mx-auto">
          {apiKeySet
            ? 'An agent that runs on your device. It can run shell, edit files, browse the web, and on phones — fully control the device.'
            : 'Set your LLM API key first (see the red banner above), then pick a starter prompt below.'}
        </p>
      </div>

      {/* Example prompts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {EXAMPLE_PROMPTS.map((ex) => (
          <button
            key={ex.title}
            onClick={() => onPick(ex.prompt)}
            disabled={!apiKeySet}
            className="card p-3 text-left hover:border-helix-blue/40 transition-all disabled:opacity-40 disabled:cursor-not-allowed group"
          >
            <div className="flex items-start gap-3">
              <span className="text-xl flex-shrink-0">{ex.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm text-helix-text group-hover:text-helix-blue-light transition-colors">
                  {ex.title}
                </div>
                <div className="text-xs text-helix-text-mute mt-0.5 truncate">
                  {ex.desc}
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Hint */}
      <div className="mt-6 text-center text-xs text-helix-text-mute flex items-center justify-center gap-1.5">
        <Sparkles size={11} className="text-helix-blue-light" />
        Or type your own request above. Try: <em>"Take a selfie with the front camera"</em>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  return (
    <div className={cn('flex msg-enter flex-col', isUser ? 'items-end' : 'items-start')}>
      <div
        className={cn(
          'max-w-[85%] lg:max-w-[75%] rounded-2xl px-4 py-2.5',
          isUser
            ? 'bg-gradient-to-br from-helix-blue to-helix-blue-dark text-white rounded-br-md'
            : 'bg-helix-bg-card border border-helix-border rounded-bl-md'
        )}
      >
        {isUser ? (
          <div className="text-sm whitespace-pre-wrap break-words">{message.content}</div>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none
                          prose-p:my-2 prose-pre:bg-helix-bg prose-pre:border prose-pre:border-helix-border
                          prose-code:text-helix-blue-light prose-code:before:content-none prose-code:after:content-none
                          prose-headings:mt-3 prose-headings:mb-1.5 prose-headings:text-helix-text
                          prose-a:text-helix-blue-light prose-strong:text-helix-text
                          prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || ' '}
            </ReactMarkdown>
          </div>
        )}
      </div>
      {/* Render tool calls attached to this message INLINE */}
      {message.toolCalls && message.toolCalls.length > 0 && (
        <div className={cn('w-full max-w-[85%] lg:max-w-[75%] space-y-1.5 mt-1', isUser ? 'self-end' : 'self-start')}>
          {message.toolCalls.map((tc) => (
            <ToolCallCard key={tc.id} tc={tc} />
          ))}
        </div>
      )}
    </div>
  );
}
