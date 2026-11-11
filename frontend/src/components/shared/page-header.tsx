import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function PageHeader({ title, description, back = false, action }: { title: string; description?: string; back?: boolean; action?: ReactNode }) {
  const navigate = useNavigate();
  return (
    <header className="mb-6 flex min-w-0 items-start gap-3">
      {back && <Button aria-label="뒤로 가기" onClick={() => navigate(-1)} size="icon" variant="ghost"><ArrowLeft className="h-5 w-5" /></Button>}
      <div className="min-w-0 flex-1">
        <h1 className="break-words text-2xl font-extrabold tracking-tight text-slate-950">{title}</h1>
        {description && <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>}
      </div>
      {action}
    </header>
  );
}

