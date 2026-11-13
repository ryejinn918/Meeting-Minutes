import { X } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  pending?: boolean;
  keepOpenOnConfirm?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "확인",
  pending = false,
  keepOpenOnConfirm = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open && !ref.current?.open) ref.current?.showModal();
    if (!open && ref.current?.open) ref.current.close();
  }, [open]);

  return <dialog className="w-[calc(100%-2rem)] max-w-sm rounded-2xl p-0 shadow-2xl backdrop:bg-slate-950/40" onCancel={pending ? undefined : onClose} ref={ref}>
    <div className="p-5"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><h2 className="text-lg font-bold text-slate-950">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{description}</p></div><Button aria-label="닫기" disabled={pending} onClick={onClose} size="icon" variant="ghost"><X className="h-5 w-5" /></Button></div><div className="mt-6 grid grid-cols-2 gap-2"><Button disabled={pending} onClick={onClose} variant="outline">취소</Button><Button disabled={pending} onClick={() => { onConfirm(); if (!keepOpenOnConfirm) onClose(); }}>{confirmLabel}</Button></div></div>
  </dialog>;
}
