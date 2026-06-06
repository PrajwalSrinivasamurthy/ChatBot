"use client";

import { useState } from "react";
import {
  MessageSquare,
  Plus,
  Search,
  Trash2,
  MoreHorizontal,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { Conversation } from "@/types/chat";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  collapsed,
  onToggle,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const grouped = groupByDate(
    conversations.filter((c) =>
      c.title.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-sidebar transition-all duration-300 ease-in-out",
        collapsed ? "w-14" : "w-72"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border h-14">
        {!collapsed && (
          <span className="text-sm font-semibold text-sidebar-foreground tracking-wide truncate">
            Conversations
          </span>
        )}
        <div className={cn("flex items-center gap-1", collapsed && "w-full justify-center")}>
          <Button
            variant="ghost"
            size="icon"
            onClick={onNew}
            className="h-8 w-8 rounded-lg hover:bg-sidebar-accent"
            title="New conversation"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Search */}
      {!collapsed && (
        <div className="px-3 py-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-sm rounded-md bg-sidebar-accent/50 border border-border placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring text-sidebar-foreground"
            />
          </div>
        </div>
      )}

      {/* Conversation list */}
      <ScrollArea className="flex-1">
        <div className="px-2 py-1">
          {collapsed ? (
            <div className="flex flex-col gap-1">
              {conversations.map((c) => (
                <Button
                  key={c.id}
                  variant="ghost"
                  size="icon"
                  onClick={() => onSelect(c.id)}
                  className={cn(
                    "h-9 w-9 rounded-lg mx-auto",
                    activeId === c.id && "bg-sidebar-accent"
                  )}
                  title={c.title}
                >
                  <MessageSquare className="h-4 w-4" />
                </Button>
              ))}
            </div>
          ) : (
            Object.entries(grouped).map(([label, items]) => (
              <div key={label} className="mb-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-2 mb-1">
                  {label}
                </p>
                {items.map((c) => (
                  <ConversationItem
                    key={c.id}
                    conversation={c}
                    active={c.id === activeId}
                    onSelect={onSelect}
                    onDelete={onDelete}
                  />
                ))}
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      {/* Collapse toggle */}
      <div className="p-2 border-t border-border">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className="h-8 w-8 rounded-lg hover:bg-sidebar-accent w-full"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>
    </aside>
  );
}

function ConversationItem({
  conversation,
  active,
  onSelect,
  onDelete,
}: {
  conversation: Conversation;
  active: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div
      className={cn(
        "group flex items-center gap-2 rounded-lg px-2 py-2 cursor-pointer hover:bg-sidebar-accent transition-colors",
        active && "bg-sidebar-accent"
      )}
      onClick={() => onSelect(conversation.id)}
    >
      <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-sidebar-foreground truncate leading-tight">
          {conversation.title}
        </p>
        <p className="text-[11px] text-muted-foreground truncate">
          {conversation.lastMessage}
        </p>
      </div>
      {conversation.unread && (
        <Badge className="h-4 w-4 p-0 flex items-center justify-center text-[10px] shrink-0 bg-primary text-primary-foreground">
          {conversation.unread}
        </Badge>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger
          className="inline-flex items-center justify-center h-6 w-6 rounded-md opacity-0 group-hover:opacity-100 shrink-0 hover:bg-accent transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-36">
          <DropdownMenuItem
            className="text-destructive focus:text-destructive gap-2"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(conversation.id);
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function groupByDate(conversations: Conversation[]): Record<string, Conversation[]> {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const sevenDaysAgo = new Date(today);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const groups: Record<string, Conversation[]> = {};

  for (const c of conversations) {
    const d = new Date(c.updatedAt);
    let label: string;
    if (d >= today) label = "Today";
    else if (d >= yesterday) label = "Yesterday";
    else if (d >= sevenDaysAgo) label = "Past 7 days";
    else label = "Older";

    if (!groups[label]) groups[label] = [];
    groups[label].push(c);
  }

  return groups;
}
