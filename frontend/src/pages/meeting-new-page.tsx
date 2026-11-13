import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileAudio, FileText, Keyboard, LoaderCircle, Mic, Save, UploadCloud } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { FileUpload } from "@/components/shared/file-upload";
import { Recorder } from "@/features/recording/recorder";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";
import { apiService, sha256File } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";
import type { MeetingType } from "@/types/api";

type InputMode = "audio" | "recording" | "document" | "text";
type UploadStage = "idle" | "preparing" | "uploading" | "confirming";

const configuredAudioLimit = Number(import.meta.env.VITE_MAX_AUDIO_BYTES ?? 52_428_800);
const MAX_AUDIO_BYTES = Number.isFinite(configuredAudioLimit)
  ? Math.min(Math.max(configuredAudioLimit, 1), 104_857_600)
  : 52_428_800;

const MIME_BY_EXTENSION: Record<string, string> = {
  mp3: "audio/mpeg",
  m4a: "audio/mp4",
  wav: "audio/wav",
  webm: "audio/webm",
  ogg: "audio/ogg",
  txt: "text/plain",
  pdf: "application/pdf",
};

function extensionOf(filename: string) {
  return filename.toLowerCase().split(".").pop() ?? "";
}

export function MeetingNewPage() {
  const { teamId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pendingMeetingId = useRef<string | null>(null);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [topic, setTopic] = useState("");
  const [location, setLocation] = useState("");
  const [meetingType, setMeetingType] = useState<MeetingType>("general");
  const [templateId, setTemplateId] = useState("");
  const [attendeeIds, setAttendeeIds] = useState<string[]>([]);
  const [mode, setMode] = useState<InputMode>("text");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [sttProvider, setSttProvider] = useState<"openai" | "whisperx">("openai");
  const [error, setError] = useState("");
  const [uploadStage, setUploadStage] = useState<UploadStage>("idle");
  const teamQuery = useQuery({
    queryKey: queryKeys.team(teamId),
    queryFn: () => apiService.getTeam(teamId),
    enabled: Boolean(teamId),
  });
  const qualityQuery = useQuery({
    queryKey: queryKeys.qualityOptions(teamId),
    queryFn: () => apiService.getQualityOptions(teamId),
    enabled: Boolean(teamId),
  });

  const metadata = {
    topic: topic.trim(),
    location: location.trim(),
    meeting_type: meetingType,
    template_id: templateId.startsWith("builtin-") || !templateId ? null : templateId,
    attendees: attendeeIds.map((user_id) => ({ user_id })),
    metadata_confirmed: true,
  };

  const create = useMutation({
    mutationFn: async () => {
      if (mode === "text") {
        const meeting = await apiService.createMeeting({
          team_id: teamId,
          title: title.trim(),
          meeting_at: `${date}T09:00:00+09:00`,
          source_type: "direct",
          ...metadata,
        });
        return { meeting: await apiService.saveTranscript(meeting.id, text.trim()), jobId: null };
      }
      if (!file) throw new Error("업로드할 파일을 선택해 주세요.");
      const extension = extensionOf(file.name);
      const contentType = MIME_BY_EXTENSION[extension];
      if (!contentType) throw new Error("지원하지 않는 파일 형식입니다.");
      if (!pendingMeetingId.current) {
        const meeting = await apiService.createMeeting({
          team_id: teamId,
          title: title.trim(),
          meeting_at: `${date}T09:00:00+09:00`,
          source_type: mode === "audio" || mode === "recording" ? "audio" : extension === "pdf" ? "pdf" : "txt",
          ...metadata,
        });
        pendingMeetingId.current = meeting.id;
      }
      setUploadStage("preparing");
      const upload = await apiService.createUploadUrl(pendingMeetingId.current, {
        filename: file.name,
        content_type: contentType,
        size_bytes: file.size,
        sha256: await sha256File(file),
        stt_provider: sttProvider,
      });
      setUploadStage("uploading");
      await apiService.uploadFile(upload, file);
      setUploadStage("confirming");
      const completed = await apiService.completeUpload(pendingMeetingId.current, upload.file.id);
      const meetingId = pendingMeetingId.current;
      pendingMeetingId.current = null;
      return { meeting: { id: meetingId }, jobId: completed.job_id };
    },
    onSuccess: ({ meeting, jobId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.meetings(teamId) });
      setUploadStage("idle");
      navigate(jobId ? `/meetings/${meeting.id}/processing?job=${jobId}` : `/meetings/${meeting.id}`);
    },
    onError: () => setUploadStage("idle"),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return setError("회의 제목을 입력해 주세요.");
    if (mode === "text" && text.trim().length < 20) {
      return setError("회의 전문을 20자 이상 입력해 주세요.");
    }
    if (mode !== "text") {
      if (!file) return setError("업로드할 파일을 선택해 주세요.");
      const extension = extensionOf(file.name);
      const allowed = mode === "audio" || mode === "recording" ? ["mp3", "m4a", "wav", "webm", "ogg"] : ["txt", "pdf"];
      if (!allowed.includes(extension)) return setError("선택한 입력 방식에 맞는 파일을 선택해 주세요.");
      const limit = mode === "audio" || mode === "recording" ? MAX_AUDIO_BYTES : 10 * 1024 * 1024;
      if (file.size === 0) return setError("빈 파일은 업로드할 수 없습니다.");
      if (file.size > limit) return setError(mode === "audio" || mode === "recording" ? `음성파일은 ${Math.floor(MAX_AUDIO_BYTES / 1024 / 1024)}MB 이하만 업로드할 수 있습니다.` : "문서 파일은 10MB 이하만 업로드할 수 있습니다.");
    }
    setError("");
    create.mutate();
  }

  const options = [
    { id: "audio" as const, label: "음성파일", caption: "MP3 · M4A · WAV", icon: FileAudio },
    { id: "recording" as const, label: "직접 녹음", caption: "마이크로 녹음", icon: Mic },
    { id: "document" as const, label: "문서", caption: "TXT · PDF", icon: FileText },
    { id: "text" as const, label: "직접 입력", caption: "전문 붙여넣기", icon: Keyboard },
  ];
  const stageMessage = uploadStage === "uploading"
    ? "파일을 업로드하고 있어요."
    : uploadStage === "confirming"
      ? mode === "audio" ? "녹음된 회의 내용을 글로 옮길 준비를 하고 있어요." : "문서에서 회의 내용을 가져올 준비를 하고 있어요."
      : "파일을 안전하게 확인하고 있어요.";

  return <><PageHeader back title="새 회의록" description="회의 내용을 직접 입력하거나 파일에서 가져올 수 있어요." />
    <form className="mt-5 space-y-5" onSubmit={submit}>
      <Card><CardContent className="space-y-4">
        <label className="block text-sm font-semibold text-slate-700">회의 제목<Input className="mt-2" maxLength={100} onChange={(event) => setTitle(event.target.value)} placeholder="예: 11월 주간 프로젝트 회의" value={title} /></label>
        <label className="block text-sm font-semibold text-slate-700">회의 주제<Input className="mt-2" maxLength={500} onChange={(event) => setTopic(event.target.value)} placeholder="이번 회의에서 다룰 핵심 주제" value={topic} /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-semibold text-slate-700">회의 날짜<Input className="mt-2" onChange={(event) => setDate(event.target.value)} type="date" value={date} /></label>
          <label className="block text-sm font-semibold text-slate-700">장소<Input className="mt-2" maxLength={300} onChange={(event) => setLocation(event.target.value)} placeholder="선택 입력" value={location} /></label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-semibold text-slate-700">회의 유형<select className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" onChange={(event) => setMeetingType(event.target.value as MeetingType)} value={meetingType}><option value="general">일반 회의</option><option value="project">프로젝트 회의</option><option value="interview">인터뷰</option><option value="workshop">워크숍·아이디어 회의</option></select></label>
          <label className="block text-sm font-semibold text-slate-700">회의록 템플릿<select className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" onChange={(event) => setTemplateId(event.target.value)} value={templateId}><option value="">유형 기본 템플릿</option>{qualityQuery.data?.templates.filter((item) => item.meeting_type === meetingType).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        </div>
        {teamQuery.data?.members.length ? <fieldset><legend className="text-sm font-semibold text-slate-700">참석자</legend><div className="mt-2 grid gap-2 sm:grid-cols-2">{teamQuery.data.members.map((member) => <label className="flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-3 text-sm" key={member.id}><input checked={attendeeIds.includes(member.id)} onChange={(event) => setAttendeeIds((current) => event.target.checked ? [...current, member.id] : current.filter((id) => id !== member.id))} type="checkbox" />{member.name}</label>)}</div></fieldset> : null}
        <p className="text-xs leading-5 text-slate-500">입력한 회의 정보와 참석자를 확인한 상태로 저장됩니다. 나중에 상세 화면에서 수정할 수 있어요.</p>
      </CardContent></Card>
      <section><h2 className="mb-3 text-sm font-bold text-slate-800">입력 방식</h2><div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{options.map(({ id, label, caption, icon: Icon }) => <button className={cn("min-w-0 rounded-2xl border bg-white p-3 text-left transition", mode === id ? "border-indigo-400 ring-2 ring-indigo-100" : "border-slate-200")} disabled={create.isPending} key={id} onClick={() => { setMode(id); setFile(null); setError(""); }} type="button"><Icon className={cn("h-5 w-5", mode === id ? "text-indigo-600" : "text-slate-400")} /><span className="mt-3 block truncate text-xs font-bold text-slate-800">{label}</span><span className="mt-0.5 block truncate text-[10px] text-slate-400">{caption}</span></button>)}</div></section>
      {(mode === "audio" || mode === "recording") && <Card className="shadow-none"><CardContent><label className="block text-sm font-semibold text-slate-700">전사 방식<select className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" onChange={(event) => setSttProvider(event.target.value as "openai" | "whisperx")} value={sttProvider}><option value="openai">OpenAI 전사</option><option value="whisperx">내 GPU 워커 (WhisperX)</option></select></label>{sttProvider === "whisperx" && <p className="mt-2 text-xs leading-5 text-amber-700">GPU 본체가 꺼져 있으면 작업은 안전하게 대기합니다. OpenAI로 자동 전환하지 않습니다.</p>}</CardContent></Card>}
      <Card><CardContent>{mode === "text" ? <label className="block text-sm font-semibold text-slate-700">회의 전문<Textarea className="mt-2 min-h-60" onChange={(event) => setText(event.target.value)} placeholder="회의 내용을 여기에 입력하거나 붙여넣어 주세요." value={text} /><span className="mt-2 block text-right text-xs text-slate-400">{text.length.toLocaleString()}자</span></label> : mode === "recording" ? <Recorder onFile={setFile} /> : <FileUpload file={file} maxAudioBytes={MAX_AUDIO_BYTES} mode={mode} onChange={setFile} />}</CardContent></Card>
      {create.isPending && mode !== "text" && <Card className="border-indigo-100 bg-indigo-50/60 shadow-none"><CardContent aria-live="polite" className="flex items-center gap-3" role="status"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-indigo-600"><LoaderCircle className="h-5 w-5 animate-spin" /></span><div><p className="text-sm font-bold text-slate-800">{stageMessage}</p><p className="mt-1 text-xs text-slate-500">이 화면을 닫지 말고 잠시 기다려 주세요.</p></div></CardContent></Card>}
      {(error || create.error) && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700" role="alert">{error || create.error?.message}</p>}
      <div className="sticky bottom-20 z-20 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-xl backdrop-blur"><Button className="w-full" disabled={create.isPending} type="submit">{mode === "text" ? <Save className="h-4 w-4" /> : <UploadCloud className="h-4 w-4" />}{create.isPending ? mode === "text" ? "회의록 저장 중..." : "파일 처리 요청 중..." : mode === "text" ? "회의록 저장" : "파일에서 회의 내용 가져오기"}</Button></div>
    </form>
  </>;
}
