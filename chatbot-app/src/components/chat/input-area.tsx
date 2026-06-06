"use client";

import { useRef, useState, KeyboardEvent } from "react";
import { Send, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface InputAreaProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  isStreaming?: boolean;
  onStop?: () => void;
}

export function InputArea({ onSend, disabled, isStreaming, onStop }: InputAreaProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="relative flex items-end gap-2 rounded-2xl border border-border bg-card shadow-sm focus-within:ring-2 focus-within:ring-ring/50 transition-shadow px-4">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onInput={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask your knowledge base..."
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none min-h-[44px] max-h-[180px] leading-relaxed"
        />

        <div className="flex items-center mb-1.5 shrink-0">
          {isStreaming ? (
            <Button
              size="icon"
              className="h-9 w-9 rounded-xl bg-destructive hover:bg-destructive/90 text-white"
              onClick={onStop}
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </Button>
          ) : (
            <Button
              size="icon"
              className={cn(
                "h-9 w-9 rounded-xl transition-all duration-200",
                canSend
                  ? "bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
              disabled={!canSend}
              onClick={handleSend}
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
      <p className="text-center text-[11px] text-muted-foreground mt-2">
        Responses are based on connected knowledge bases only.
      </p>
    </div>
  );
}
