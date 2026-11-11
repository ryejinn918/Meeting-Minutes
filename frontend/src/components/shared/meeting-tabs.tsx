import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export type MeetingTab = "summary" | "transcript" | "actions";

export function MeetingTabs({ value, onChange, counts, children }: { value: MeetingTab; onChange: (tab: MeetingTab) => void; counts?: Partial<Record<MeetingTab, number>>; children: ReactNode }) {
  const tabs: { id: MeetingTab; label: string }[] = [{ id: "summary", label: "요약" }, { id: "transcript", label: "회의 전문" }, { id: "actions", label: "액션아이템" }];
  return (
    <div>
      <div className="mb-5 grid grid-cols-3 rounded-xl bg-slate-100 p-1" role="tablist">
        {tabs.map((tab) => <button aria-selected={value === tab.id} className={cn("min-h-10 rounded-lg px-2 text-xs font-bold text-slate-500 transition sm:text-sm", value === tab.id && "bg-white text-indigo-700 shadow-sm")} key={tab.id} onClick={() => onChange(tab.id)} role="tab" type="button">{tab.label}{counts?.[tab.id] !== undefined && <span className="ml-1 text-[10px]">{counts[tab.id]}</span>}</button>)}
      </div>
      <div role="tabpanel">{children}</div>
    </div>
  );
}
