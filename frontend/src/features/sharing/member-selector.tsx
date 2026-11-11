import { Check, Search, ShieldCheck } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import type { TeamMember } from "@/types/api";

export function MemberSelector({ members, selectedIds, query, onQueryChange, onToggle }: { members: TeamMember[]; selectedIds: string[]; query: string; onQueryChange: (value: string) => void; onToggle: (id: string) => void }) {
  const filtered = members.filter((member) => `${member.name} ${member.email}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div>
      <label className="relative block"><Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" /><Input className="pl-10" onChange={(event) => onQueryChange(event.target.value)} placeholder="이름 또는 이메일 검색" value={query} /></label>
      <div className="mt-4 space-y-2">
        {filtered.map((member) => {
          const checked = selectedIds.includes(member.id);
          return <label className={cn("flex min-h-16 cursor-pointer items-center gap-3 rounded-2xl border bg-white p-3 transition", checked ? "border-indigo-300 bg-indigo-50/40" : "border-slate-200 hover:border-slate-300")} key={member.id}>
            <input checked={checked} className="sr-only" onChange={() => onToggle(member.id)} type="checkbox" />
            <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white", member.avatar_color)}>{member.name.slice(0, 1)}</span>
            <span className="min-w-0 flex-1"><span className="flex items-center gap-1.5 text-sm font-bold text-slate-800">{member.name}{member.role !== "member" && <ShieldCheck className="h-3.5 w-3.5 text-indigo-500" />}</span><span className="block truncate text-xs text-slate-500">{member.email}</span></span>
            <span className={cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border", checked ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-300 bg-white")}><Check className={cn("h-4 w-4", !checked && "opacity-0")} /></span>
          </label>;
        })}
      </div>
    </div>
  );
}

