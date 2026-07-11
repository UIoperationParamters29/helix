'use client';

import { Camera, Battery, Smartphone, Globe, MessageSquare, MapPin, Volume2, Zap, type LucideIcon } from 'lucide-react';
import { useHelix } from '@/lib/store';

type QuickAction = {
  label: string;
  prompt: string;
  icon: LucideIcon;
  color: string;
  requiresPhone?: boolean;
};

const ACTIONS: QuickAction[] = [
  {
    label: 'Screenshot',
    prompt: 'Take a screenshot of my phone screen and tell me what you see.',
    icon: Camera,
    color: 'text-helix-blue-light',
    requiresPhone: true,
  },
  {
    label: 'Battery',
    prompt: "What's my phone battery level and is it charging?",
    icon: Battery,
    color: 'text-green-400',
    requiresPhone: true,
  },
  {
    label: 'Location',
    prompt: 'Get my current GPS location.',
    icon: MapPin,
    color: 'text-helix-red-light',
    requiresPhone: true,
  },
  {
    label: 'Open website',
    prompt: 'Open https://example.com in my phone browser.',
    icon: Globe,
    color: 'text-helix-blue-light',
    requiresPhone: true,
  },
  {
    label: 'Read SMS',
    prompt: 'Read my 5 most recent SMS messages.',
    icon: MessageSquare,
    color: 'text-green-400',
    requiresPhone: true,
  },
  {
    label: 'Volume',
    prompt: 'Set my media volume to 8.',
    icon: Volume2,
    color: 'text-helix-blue-light',
    requiresPhone: true,
  },
  {
    label: 'Torch',
    prompt: 'Turn on the flashlight for 3 seconds then turn it off.',
    icon: Zap,
    color: 'text-yellow-400',
    requiresPhone: true,
  },
  {
    label: 'Apps',
    prompt: 'List all my installed apps.',
    icon: Smartphone,
    color: 'text-helix-red-light',
    requiresPhone: true,
  },
];

const PC_ACTIONS: QuickAction[] = [
  {
    label: 'List files',
    prompt: 'List all files in the current working directory and explain what each one is.',
    icon: Smartphone,
    color: 'text-helix-blue-light',
  },
  {
    label: 'System info',
    prompt: 'Show me detailed system information about this machine.',
    icon: Battery,
    color: 'text-green-400',
  },
  {
    label: 'Search web',
    prompt: 'Search the web for "latest AI agent news" and summarize the top 3 results.',
    icon: Globe,
    color: 'text-helix-blue-light',
  },
];

export function QuickActions({ onPick }: { onPick: (prompt: string) => void }) {
  const { status } = useHelix();
  const onTermux = status?.on_termux;
  const actions = onTermux ? ACTIONS : PC_ACTIONS;

  return (
    <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-1">
      {actions.map((a) => {
        const Icon = a.icon;
        return (
          <button
            key={a.label}
            onClick={() => onPick(a.prompt)}
            className="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-full
                       bg-helix-bg-card/80 border border-helix-border hover:border-helix-blue/40
                       hover:bg-helix-bg-elev transition-all text-xs whitespace-nowrap"
          >
            <Icon size={11} className={a.color} />
            <span className="text-helix-text-dim">{a.label}</span>
          </button>
        );
      })}
    </div>
  );
}
