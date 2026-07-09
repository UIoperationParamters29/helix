'use client';

import { useHelix } from '@/lib/store';
import { ChatView } from '@/components/ChatView';
import { SessionsView } from '@/components/SessionsView';
import { SkillsView } from '@/components/SkillsView';
import { ToolsView } from '@/components/ToolsView';
import { FilesView } from '@/components/FilesView';
import { MemoryView } from '@/components/MemoryView';
import { SettingsView } from '@/components/SettingsView';

export default function Page() {
  const activeView = useHelix((s) => s.activeView);

  switch (activeView) {
    case 'chat': return <ChatView />;
    case 'sessions': return <SessionsView />;
    case 'skills': return <SkillsView />;
    case 'tools': return <ToolsView />;
    case 'files': return <FilesView />;
    case 'memory': return <MemoryView />;
    case 'settings': return <SettingsView />;
    default: return <ChatView />;
  }
}
