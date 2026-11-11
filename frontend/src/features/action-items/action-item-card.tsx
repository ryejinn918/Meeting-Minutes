import { CalendarDays, Circle, CircleCheck, UserRound } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { formatDueDate } from "@/lib/format";
import type { ActionItem } from "@/types/api";

export function ActionItemCard({ item, editable, onToggle }: { item: ActionItem; editable: boolean; onToggle?: (item: ActionItem) => void }) {
  const done = item.status === "done";
  return (
    <Card className={cn("shadow-none", done && "bg-slate-50")}>
      <CardContent className="flex items-start gap-3 p-4">
        <button aria-label={done ? "미완료로 변경" : "완료로 변경"} className="mt-0.5 shrink-0 text-indigo-600 disabled:text-slate-300" disabled={!editable} onClick={() => onToggle?.({ ...item, status: done ? "todo" : "done" })} type="button">
          {done ? <CircleCheck className="h-6 w-6" /> : <Circle className="h-6 w-6" />}
        </button>
        <div className="min-w-0 flex-1">
          <p className={cn("break-words text-sm font-semibold leading-6 text-slate-800", done && "text-slate-400 line-through")}>{item.description}</p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1"><UserRound className="h-3.5 w-3.5" />{item.assignee_name ?? "미지정"}</span>
            <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{formatDueDate(item.due_date)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

