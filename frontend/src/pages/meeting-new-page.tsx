import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileAudio, FileText, Keyboard, Save } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { FileUpload } from "@/components/shared/file-upload";
import { MockBanner } from "@/components/shared/mock-banner";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

type InputMode = "audio" | "document" | "text";

export function MeetingNewPage() {
  const { teamId = "" } = useParams(); const navigate = useNavigate(); const queryClient = useQueryClient();
  const pendingMeetingId = useRef<string | null>(null);
  const [title, setTitle] = useState(""); const [date, setDate] = useState(new Date().toISOString().slice(0, 10)); const [mode, setMode] = useState<InputMode>("text"); const [file, setFile] = useState<File | null>(null); const [text, setText] = useState(""); const [error, setError] = useState("");
  const create = useMutation({
    mutationFn: async () => {
      if (!pendingMeetingId.current) {
        const meeting = await apiService.createMeeting({ team_id: teamId, title: title.trim(), meeting_at: `${date}T09:00:00+09:00` });
        pendingMeetingId.current = meeting.id;
      }
      const meeting = await apiService.saveTranscript(pendingMeetingId.current, text.trim());
      pendingMeetingId.current = null;
      return meeting;
    },
    onSuccess: (meeting) => { void queryClient.invalidateQueries({ queryKey: queryKeys.meetings(teamId) }); navigate(`/meetings/${meeting.id}`); },
  });
  function submit(event: FormEvent) { event.preventDefault(); if (!title.trim()) return setError("회의 제목을 입력해 주세요."); if (mode !== "text") return setError("파일 업로드는 다음 단계에서 연결됩니다. 지금은 회의 전문 직접 입력을 이용해 주세요."); if (text.trim().length < 20) return setError("회의 전문을 20자 이상 입력해 주세요."); setError(""); create.mutate(); }
  const options = [{ id: "audio" as const, label: "음성파일", caption: "MP3 · M4A · WAV", icon: FileAudio }, { id: "document" as const, label: "문서", caption: "TXT · PDF", icon: FileText }, { id: "text" as const, label: "직접 입력", caption: "전문 붙여넣기", icon: Keyboard }];
  return <><PageHeader back title="새 회의록" description="직접 입력한 회의 전문을 안전하게 저장합니다." />{mode !== "text" && <MockBanner message="파일 업로드 UI는 미리보기입니다. 선택한 파일은 서버로 전송되지 않습니다." />}<form className="mt-5 space-y-5" onSubmit={submit}>
    <Card><CardContent className="space-y-4"><label className="block text-sm font-semibold text-slate-700">회의 제목<Input className="mt-2" maxLength={100} onChange={(e) => setTitle(e.target.value)} placeholder="예: 11월 주간 프로젝트 회의" value={title} /></label><label className="block text-sm font-semibold text-slate-700">회의 날짜<Input className="mt-2" onChange={(e) => setDate(e.target.value)} type="date" value={date} /></label></CardContent></Card>
    <section><h2 className="mb-3 text-sm font-bold text-slate-800">입력 방식</h2><div className="grid grid-cols-3 gap-2">{options.map(({ id, label, caption, icon: Icon }) => <button className={cn("min-w-0 rounded-2xl border bg-white p-3 text-left transition", mode === id ? "border-indigo-400 ring-2 ring-indigo-100" : "border-slate-200")} key={id} onClick={() => { setMode(id); setFile(null); setError(""); }} type="button"><Icon className={cn("h-5 w-5", mode === id ? "text-indigo-600" : "text-slate-400")} /><span className="mt-3 block truncate text-xs font-bold text-slate-800">{label}</span><span className="mt-0.5 block truncate text-[10px] text-slate-400">{caption}</span></button>)}</div></section>
    <Card><CardContent>{mode === "text" ? <label className="block text-sm font-semibold text-slate-700">회의 전문<Textarea className="mt-2 min-h-60" onChange={(e) => setText(e.target.value)} placeholder="회의 내용을 여기에 입력하거나 붙여넣어 주세요." value={text} /><span className="mt-2 block text-right text-xs text-slate-400">{text.length.toLocaleString()}자</span></label> : <FileUpload file={file} mode={mode} onChange={setFile} />}</CardContent></Card>
    {(error || create.error) && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700" role="alert">{error || create.error?.message}</p>}
    <div className="sticky bottom-20 z-20 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-xl backdrop-blur"><Button className="w-full" disabled={create.isPending || mode !== "text"} type="submit"><Save className="h-4 w-4" />{create.isPending ? "회의록 저장 중..." : mode === "text" ? "회의록 저장" : "파일 업로드는 다음 단계"}</Button></div>
  </form></>;
}
