"use client";

import { cn } from "@/lib/utils";
import { Message } from "@/types/chat";
import { Bot, Copy, ThumbsUp, ThumbsDown, RotateCcw, User } from "lucide-react";
import { useState } from "react";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";

interface MessageBubbleProps {
  message: Message;
  onRegenerate?: () => void;
}

export function MessageBubble({ message, onRegenerate }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState<"up" | "down" | null>(null);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const time = new Date(message.timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      className={cn(
        "group flex gap-3 px-4 py-3 animate-in fade-in slide-in-from-bottom-2 duration-300",
        isUser && "flex-row-reverse"
      )}
    >
      {/* Avatar */}
      {!isUser ? (
        <div className="flex-shrink-0 mt-0.5">
          <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center ring-2 ring-background">
            <Bot className="h-4 w-4 text-primary-foreground" />
          </div>
        </div>
      ) : (
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center ring-2 ring-background flex-shrink-0 mt-0.5">
          <User className="h-4 w-4 text-white" />
        </div>
      )}

      <div
        className={cn(
          "flex flex-col gap-1 max-w-[75%]",
          isUser && "items-end"
        )}
      >
        {/* Bubble */}
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words",
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-sm"
              : "bg-muted text-foreground rounded-tl-sm"
          )}
        >
          {message.isStreaming ? (
            <span>
              {message.content}
              <span className="inline-flex gap-0.5 ml-1">
                <span className="w-1 h-1 bg-current rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1 h-1 bg-current rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1 h-1 bg-current rounded-full animate-bounce [animation-delay:300ms]" />
              </span>
            </span>
          ) : (
            message.content
          )}
        </div>

        {/* Inline images (assistant only) */}
        {!isUser && !message.isStreaming && message.imageIds && message.imageIds.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {message.imageIds.map((id) => (
              <img
                key={id}
                src={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/static/images/${id}`}
                alt="Knowledge base illustration"
                className="max-w-xs rounded-xl border border-border shadow-sm object-contain"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            ))}
          </div>
        )}

        {/* Timestamp + actions */}
        <div
          className={cn(
            "flex items-center gap-1 px-1",
            isUser ? "flex-row-reverse" : "flex-row"
          )}
        >
          <span className="text-[10px] text-muted-foreground">{time}</span>

          {!isUser && !message.isStreaming && (
            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
              <ActionButton label={copied ? "Copied!" : "Copy"} onClick={handleCopy}>
                <Copy className="h-3 w-3" />
              </ActionButton>
              <ActionButton
                label="Good response"
                onClick={() => setLiked(liked === "up" ? null : "up")}
                active={liked === "up"}
              >
                <ThumbsUp className="h-3 w-3" />
              </ActionButton>
              <ActionButton
                label="Bad response"
                onClick={() => setLiked(liked === "down" ? null : "down")}
                active={liked === "down"}
              >
                <ThumbsDown className="h-3 w-3" />
              </ActionButton>
              {onRegenerate && (
                <ActionButton label="Regenerate" onClick={onRegenerate}>
                  <RotateCcw className="h-3 w-3" />
                </ActionButton>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  active,
  children,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        onClick={onClick}
        className={cn(
          "inline-flex items-center justify-center h-6 w-6 rounded-md hover:bg-accent transition-colors text-muted-foreground hover:text-foreground",
          active && "text-primary bg-primary/10 hover:bg-primary/15 hover:text-primary"
        )}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent side="bottom" className="text-xs">
        {label}
      </TooltipContent>
    </Tooltip>
  );
}
