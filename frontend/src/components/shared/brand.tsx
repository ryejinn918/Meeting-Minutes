import { MessageSquareText } from "lucide-react";

import { cn } from "@/lib/cn";

export function Brand({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <div className={cn("inline-flex items-center gap-2.5", className)}>
      <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-500 text-white shadow-lg shadow-indigo-200">
        <MessageSquareText aria-hidden="true" className="h-5 w-5" />
      </span>
      {!compact && <span className="text-xl font-extrabold tracking-tight text-slate-900">MeetFlow</span>}
    </div>
  );
}

