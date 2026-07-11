'use client';

import { useEffect, useRef, useState } from 'react';
import { Send, Loader2, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useHelix, type ChatMessage, type ToolCall } from '@/lib/store';
import { HelixAPI, wsUrl } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ToolCallCard } from './ToolCallCard';

export function ChatView() {
  const {
    sessionId, setSessionId, messages, addMessage, appendToMessage,
    isStreaming, setStreaming, upsertToolCall, updateToolCall,
    pendingToolCalls, backendReady,
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

  // WebSocket setup
  useEffect(() => {
    if (!sessionId) return;
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'hello', session_id: sessionId }));
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        handleWsMessage(msg);
      } catch (e) {
        console.error('bad ws message', e);
      }
    };

    ws.onerror = () => setError('WebSocket error');
    ws.onclose = () => setError('WebSocket closed');

    return () => ws.close();
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
    if (msg.type !== 'message' && msg.type !== 'action' && msg.type !== 'observation'
        && msg.type !== 'error' && msg.type !== 'finish') return;

    const data = msg.data;
    if (!data) return;

    if (msg.type === 'message') {
      if (data.role === 'user') {
        // We already added it locally; skip
        return;
      }
      // Assistant message — add new
      addMessage({
        id: data.id,
        role: data.role,
        content: data.content,
        ts: data.ts,
      });
    } else if (msg.type === 'action') {
      // Tool call started
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
      // Tool call finished
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

  async function send() {
    const text = input.trim();
    if (!text || isStreaming) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket not connected');
      return;
    }
    setError(null);

    // Optimistic add user message
    addMessage({
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      ts: Date.now() / 1000,
    });

    setInput('');
    setStreaming(true);
    wsRef.current.send(JSON.stringify({ type: 'send', content: text }));
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  // Group pending tool calls with the nearest preceding assistant message
  const pendingList = Object.values(pendingToolCalls).sort((a, b) => a.ts - b.ts);

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="border-b border-helix-border px-4 py-3 flex items-center justify-between lg:pl-4 pl-16">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Chat</span>
          {sessionId && (
            <span className="text-xs text-helix-text-mute font-mono">{sessionId}</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div className={cn(
            'w-2 h-2 rounded-full',
            backendReady ? 'bg-green-500' : 'bg-helix-red animate-pulse'
          )} />
          <span className="text-helix-text-dim">
            {backendReady ? 'Connected' : 'Connecting...'}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && pendingList.length === 0 && (
          <div className="text-center text-helix-text-mute py-16">
            <div className="text-4xl mb-3">🧬</div>
            <div className="font-medium">HELIX is ready</div>
            <div className="text-xs mt-1">
              Ask anything. The agent can run shell commands, edit files, browse the web,
              and on phones — control your device.
            </div>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}

        {/* Pending tool calls */}
        {pendingList.length > 0 && (
          <div className="space-y-2">
            {pendingList.map((tc) => (
              <ToolCallCard key={tc.id} tc={tc} />
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mb-2 p-3 rounded-lg bg-helix-red/10 border border-helix-red/30 text-helix-red-light text-sm flex items-center gap-2">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {/* Input */}
      <div className="border-t border-helix-border p-3">
        <div className="flex items-end gap-2 max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Send a message..."
            rows={1}
            className="flex-1 resize-none max-h-32"
            style={{ minHeight: '42px' }}
            disabled={isStreaming}
          />
          <button
            onClick={send}
            disabled={!input.trim() || isStreaming}
            className="btn btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isStreaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            <span className="hidden sm:inline">{isStreaming ? 'Working...' : 'Send'}</span>
          </button>
        </div>
        <div className="text-[10px] text-helix-text-mute text-center mt-1.5">
          Enter to send · Shift+Enter for newline
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  return (
    <div className={cn('flex msg-enter', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] lg:max-w-[75%] rounded-2xl px-4 py-2.5',
          isUser
            ? 'bg-gradient-to-br from-helix-blue to-helix-blue-dark text-white rounded-br-md'
            : 'bg-helix-bg-card border border-helix-border rounded-bl-md'
        )}
      >
        {isUser ? (
          <div className="text-sm whitespace-pre-wrap">{message.content}</div>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || ' '}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
