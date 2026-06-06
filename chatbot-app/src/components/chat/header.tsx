"use client";

import { Bot } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

interface ChatHeaderProps {
  conversationTitle: string;
  agentTitle: string;
}

export function ChatHeader({ conversationTitle, agentTitle }: ChatHeaderProps) {
  return (
    <header className="flex items-center justify-between px-4 h-14 border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      {/* Left — bot avatar + conversation title */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center justify-center h-8 w-8 rounded-full bg-primary shrink-0">
          <Bot className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="min-w-0">
          <h1 className="text-sm font-semibold text-foreground truncate leading-tight">
            {conversationTitle}
          </h1>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
            <span className="text-[11px] text-muted-foreground">Online</span>
          </div>
        </div>
      </div>

      {/* Centre — agent title badge */}
      <div className="absolute left-1/2 -translate-x-1/2 pointer-events-none select-none">
        <div className="flex items-center gap-2 bg-primary/8 border border-primary/15 rounded-full px-3.5 py-1">
          <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
          <span className="text-xs font-semibold tracking-widest uppercase text-primary whitespace-nowrap">
            {agentTitle}
          </span>
        </div>
      </div>

      {/* Right — theme toggle */}
      <ThemeToggle />
    </header>
  );
}
