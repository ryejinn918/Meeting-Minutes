import { CheckCircle2, CircleAlert, Clock3, LoaderCircle, PencilLine, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ProcessingStatus } from "@/types/api";

const statusMap: Record<ProcessingStatus, { label: string; className: string; icon: LucideIcon }> = {
  draft: { label: "초안", className: "bg-slate-100 text-slate-600", icon: PencilLine },
  uploaded: { label: "업로드됨", className: "bg-sky-50 text-sky-700", icon: Clock3 },
  transcribing: { label: "전사 중", className: "bg-violet-50 text-violet-700", icon: LoaderCircle },
  analyzing: { label: "정리 중", className: "bg-indigo-50 text-indigo-700", icon: LoaderCircle },
  ready: { label: "정리 완료", className: "bg-emerald-50 text-emerald-700", icon: CheckCircle2 },
  failed: { label: "정리 실패", className: "bg-rose-50 text-rose-700", icon: CircleAlert },
};

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  const item = statusMap[status];
  const Icon = item.icon;
  const spinning = status === "transcribing" || status === "analyzing";
  return <Badge className={item.className}><Icon aria-hidden="true" className={`h-3.5 w-3.5 ${spinning ? "animate-spin" : ""}`} />{item.label}</Badge>;
}
