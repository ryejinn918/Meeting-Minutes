import { FileAudio, FileText, Trash2, UploadCloud } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { formatFileSize } from "@/lib/format";

export function FileUpload({ mode, file, onChange }: { mode: "audio" | "document"; file: File | null; onChange: (file: File | null) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const accept = mode === "audio" ? ".mp3,.m4a,.wav,audio/mpeg,audio/mp4,audio/wav" : ".txt,.pdf,text/plain,application/pdf";
  const Icon = mode === "audio" ? FileAudio : FileText;
  return (
    <div>
      {!file ? (
        <button type="button" onClick={() => inputRef.current?.click()} className={cn("flex min-h-44 w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50 px-5 text-center transition hover:border-indigo-300 hover:bg-indigo-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500")}>
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-indigo-600 shadow-sm"><UploadCloud className="h-6 w-6" /></span>
          <span className="text-sm font-bold text-slate-800">파일을 선택해 주세요</span>
          <span className="mt-1 text-xs leading-5 text-slate-500">{mode === "audio" ? "MP3, M4A, WAV · 최대 25MB" : "TXT, 텍스트 기반 PDF · 최대 10MB"}</span>
        </button>
      ) : (
        <div className="flex min-w-0 items-center gap-3 rounded-2xl border border-indigo-200 bg-indigo-50/60 p-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-indigo-600"><Icon className="h-5 w-5" /></span>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-bold text-slate-800">{file.name}</p><p className="mt-0.5 text-xs text-slate-500">{formatFileSize(file.size)}</p><button className="mt-1 text-xs font-semibold text-indigo-600" onClick={() => inputRef.current?.click()} type="button">다른 파일 선택</button></div>
          <Button aria-label="선택한 파일 제거" onClick={() => onChange(null)} size="icon" variant="ghost"><Trash2 className="h-4 w-4" /></Button>
        </div>
      )}
      <input ref={inputRef} accept={accept} className="sr-only" onChange={(event) => { onChange(event.target.files?.[0] ?? null); event.target.value = ""; }} type="file" />
    </div>
  );
}
