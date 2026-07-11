'use client';

import { useEffect } from 'react';
import {
  MessageSquare, Clock, BookOpen, Wrench, Folder, Brain,
  Settings, Menu, X, Zap,
} from 'lucide-react';
import { useHelix } from '@/lib/store';
import { HelixAPI } from '@/lib/api';
import { cn } from '@/lib/utils';

const NAV = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'sessions', label: 'Sessions', icon: Clock },
  { id: 'skills', label: 'Skills', icon: BookOpen },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'files', label: 'Files', icon: Folder },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'settings', label: 'Settings', icon: Settings },
] as const;

export function Sidebar() {
  const {
    sidebarOpen, setSidebarOpen, activeView, setActiveView,
    setStatus, setTools, setSkills, setMemory, setSessions,
    setBackendReady, sessionId, setSessionId,
  } = useHelix();

  // Initial load: fetch status, tools, skills, memory
  useEffect(() => {
    (async () => {
      try {
        const [status, tools, skills, memory, sessions] = await Promise.all([
          HelixAPI.status(),
          HelixAPI.tools(),
          HelixAPI.skills(),
          HelixAPI.memory(),
          HelixAPI.sessions(),
        ]);
        setStatus(status);
        setTools(tools);
        setSkills(skills);
        setMemory(memory);
        setSessions(sessions);
        setBackendReady(true);

        // Auto-create a session if none active
        if (!sessionId) {
          const s = await HelixAPI.newSession();
          setSessionId(s.session_id);
        }
      } catch (e) {
        console.error('Backend not reachable:', e);
        setBackendReady(false);
      }
    })();
  }, []); // eslint-disable-line

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={cn(
          'fixed lg:static inset-y-0 left-0 z-50',
          'w-64 lg:w-64 flex-shrink-0',
          'bg-helix-bg-card/80 backdrop-blur-md border-r border-helix-border',
          'flex flex-col transition-transform duration-200',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Header */}
        <div className="p-4 border-b border-helix-border flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="relative w-8 h-8 flex items-center justify-center">
              <div className="absolute w-7 h-1 bg-gradient-to-r from-helix-red to-transparent rounded-full" style={{ transform: 'translateY(-5px) rotate(18deg)' }} />
              <div className="absolute w-7 h-1 bg-gradient-to-r from-transparent to-helix-blue rounded-full" style={{ transform: 'translateY(5px) rotate(-18deg)' }} />
              <div className="absolute w-7 h-1 bg-gradient-to-r from-helix-red/60 to-transparent rounded-full" style={{ transform: 'rotate(18deg)' }} />
              <div className="absolute w-7 h-1 bg-gradient-to-r from-transparent to-helix-blue/60 rounded-full" style={{ transform: 'rotate(-18deg)' }} />
            </div>
            <div>
              <div className="font-bold text-base tracking-tight bg-gradient-to-r from-helix-red via-helix-text to-helix-blue bg-clip-text text-transparent">
                HELIX
              </div>
              <div className="text-[10px] text-helix-text-mute -mt-0.5">Agent Harness</div>
            </div>
          </div>
          <button
            className="lg:hidden text-helix-text-dim hover:text-helix-text"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto p-2 no-scrollbar">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                  active
                    ? 'bg-gradient-to-r from-helix-red/15 to-helix-blue/15 text-helix-text border border-helix-blue/30'
                    : 'text-helix-text-dim hover:bg-helix-bg-elev hover:text-helix-text'
                )}
              >
                <Icon size={16} className={active ? 'text-helix-blue' : ''} />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-helix-border text-xs text-helix-text-mute">
          <div className="flex items-center gap-1.5">
            <Zap size={12} className="text-helix-red" />
            <span>Self-improving · v0.1.0</span>
          </div>
        </div>
      </aside>

      {/* Mobile menu button */}
      <button
        className="lg:hidden fixed top-3 left-3 z-30 bg-helix-bg-card/80 backdrop-blur-md border border-helix-border rounded-lg p-2"
        onClick={() => setSidebarOpen(true)}
      >
        <Menu size={18} />
      </button>
    </>
  );
}
