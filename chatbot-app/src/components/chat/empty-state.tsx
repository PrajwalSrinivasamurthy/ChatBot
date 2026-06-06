"use client";

import { BookOpen, Search, Shield } from "lucide-react";

export function EmptyState() {
  return (
    <div className="flex flex-col items-center px-4 pt-24 pb-12 text-center max-w-xl mx-auto">
      <div className="flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 mb-5 ring-1 ring-primary/20">
        <BookOpen className="h-8 w-8 text-primary" />
      </div>
      <h2 className="text-2xl font-semibold text-foreground mb-2">
        Welcome to TTU AI ChatBot
      </h2>
      <p className="text-sm text-muted-foreground mb-8 max-w-sm leading-relaxed">
        Ask questions about TTU Online programs, admissions, courses, and more.
        Answers are pulled directly from the TTU knowledge base.
      </p>

      <div className="flex flex-wrap gap-2 justify-center">
        {[
          { icon: Search, label: "KB-powered answers" },
          { icon: Shield, label: "Internal use only" },
          { icon: BookOpen, label: "Source-cited responses" },
        ].map(({ icon: Icon, label }) => (
          <div
            key={label}
            className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted rounded-full px-3 py-1.5"
          >
            <Icon className="h-3 w-3" />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
