import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Edit3, LockKeyhole, Save, Share2, Sparkles, Trash2, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { MeetingTabs, type MeetingTab } from "@/components/shared/meeting-tabs";
import { MockBanner } from "@/components/shared/mock-banner";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState, InlineSavingState, LoadingState } from "@/components/shared/states";
import { ActionItemCard } from "@/features/action-items/action-item-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { formatMeetingDate } from "@/lib/format";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";
import type { DiscussionItem, SaveStatus, TranscriptSegment, TranscriptSpeaker } from "@/types/api";

function itemsToText(items: DiscussionItem[]) {
  return items.map((item) => item.text).join("\n");
}

function textToItems(text: string, previous: DiscussionItem[]): DiscussionItem[] {
  return text.split("\n").map((line) => line.trim()).filter(Boolean).map((value, index) => {
    const existing = previous[index];
    return {
      id: existing?.id ?? crypto.randomUUID(),
      text: value,
      evidence: existing?.text === value ? existing.evidence : undefined,
    };
  });
}

function SectionCard({ title, items, tone = "indigo" }: { title: string; items: DiscussionItem[]; tone?: "indigo" | "emerald" | "violet" }) {
  const tones = { indigo: "bg-indigo-500", emerald: "bg-emerald-500", violet: "bg-violet-500" };
  return <Card className="shadow-none"><CardContent><h3 className="flex items-center gap-2 text-sm font-bold text-slate-900"><span className={`h-2 w-2 rounded-full ${tones[tone]}`} />{title}</h3>{items.length ? <ul className="mt-3 space-y-3">{items.map((item) => <li className="text-sm leading-6 text-slate-600" key={item.id}><div className="flex gap-2"><span className="mt-2.5 h-1 w-1 shrink-0 rounded-full bg-slate-300" /><span>{item.text}</span></div>{item.evidence && <p className="ml-3 mt-1 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">근거: {item.evidence}</p>}</li>)}</ul> : <p className="mt-3 text-sm text-slate-400">해당 항목이 없습니다.</p>}</CardContent></Card>;
}

function segmentTime(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  return [hours, minutes, secs].map((value) => String(value).padStart(2, "0")).join(":");
}

function DiarizedTranscript({
  meetingId,
  speakers,
  segments,
  editable,
}: {
  meetingId: string;
  speakers: TranscriptSpeaker[];
  segments: TranscriptSegment[];
  editable: boolean;
}) {
  const queryClient = useQueryClient();
  const [visibleCount, setVisibleCount] = useState(100);
  const [names, setNames] = useState<Record<string, string>>({});
  useEffect(() => {
    setNames(Object.fromEntries(speakers.map((speaker) => [speaker.id, speaker.display_name])));
  }, [speakers]);
  useEffect(() => setVisibleCount(100), [meetingId, segments]);
  const rename = useMutation({
    mutationFn: ({ speakerId, displayName }: { speakerId: string; displayName: string }) =>
      apiService.updateTranscriptSpeaker(meetingId, speakerId, displayName),
    onSuccess: (updated) => queryClient.setQueryData(queryKeys.meeting(meetingId), updated),
  });

  return <Card className="mt-3 shadow-none"><CardContent>
    <div className="flex items-center justify-between gap-3">
      <h3 className="font-bold text-slate-900">화자별 발언</h3>
      <Badge className="bg-indigo-50 text-indigo-700">타임스탬프 포함</Badge>
    </div>
    {editable && <div className="mt-4 grid gap-2 sm:grid-cols-2">{speakers.map((speaker) =>
      <div className="flex min-w-0 gap-2" key={speaker.id}>
        <Input aria-label="화자 이름" className="min-w-0" maxLength={100} onChange={(event) => setNames((value) => ({ ...value, [speaker.id]: event.target.value }))} value={names[speaker.id] ?? speaker.display_name} />
        <Button disabled={rename.isPending || !(names[speaker.id] ?? "").trim()} onClick={() => rename.mutate({ speakerId: speaker.id, displayName: (names[speaker.id] ?? speaker.display_name).trim() })} size="sm" variant="outline">저장</Button>
      </div>)}</div>}
    {rename.isError && <p className="mt-3 text-sm text-rose-600">{rename.error.message}</p>}
    <ol className="mt-5 space-y-3">{segments.slice(0, visibleCount).map((segment) =>
      <li className="rounded-xl bg-slate-50 p-4" key={segment.id}>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold tabular-nums text-indigo-600">[{segmentTime(segment.start_seconds)}–{segmentTime(segment.end_seconds)}]</span>
          <span className="font-bold text-slate-700">{segment.speaker_name}</span>
        </div>
        <p className="mt-2 break-words text-sm leading-7 text-slate-700">{segment.text}</p>
      </li>)}</ol>
    {visibleCount < segments.length && <Button className="mt-4 w-full" onClick={() => setVisibleCount((value) => value + 100)} variant="outline">발언 더 보기 ({segments.length - visibleCount}개 남음)</Button>}
  </CardContent></Card>;
}

export function MeetingDetailPage() {
  const { id = "" } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<MeetingTab>("summary");
  const [editing, setEditing] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const meetingQuery = useQuery({ queryKey: queryKeys.meeting(id), queryFn: () => apiService.getMeeting(id), staleTime: 2 * 60_000 });
  const meeting = meetingQuery.data;
  const teamQuery = useQuery({ queryKey: queryKeys.team(meeting?.team_id ?? "pending"), queryFn: () => apiService.getTeam(meeting!.team_id), enabled: Boolean(meeting), staleTime: 5 * 60_000 });
  const [draft, setDraft] = useState({ title: "", date: "", transcript: "", summary: "", discussions: "", decisions: "", followUps: "" });

  useEffect(() => {
    if (searchParams.get("tab") === "transcript") setTab("transcript");
  }, [searchParams]);

  useEffect(() => {
    if (meeting) setDraft({
      title: meeting.title,
      date: meeting.meeting_at.slice(0, 10),
      transcript: meeting.transcript_edited,
      summary: meeting.summary,
      discussions: itemsToText(meeting.key_discussions),
      decisions: itemsToText(meeting.decisions),
      followUps: itemsToText(meeting.follow_ups),
    });
  }, [meeting]);

  const save = useMutation({
    mutationFn: async () => {
      if (!meeting) throw new Error("회의록을 찾을 수 없습니다.");
      const updated = await apiService.updateMeeting(id, { title: draft.title.trim(), meeting_at: `${draft.date}T09:00:00+09:00`, version: meeting.version });
      const withTranscript = await apiService.saveTranscript(id, draft.transcript.trim() || updated.transcript_edited);
      if (!meeting.summary) return withTranscript;
      return apiService.updateNotes(id, {
        summary: draft.summary.trim(),
        key_discussions: textToItems(draft.discussions, meeting.key_discussions),
        decisions: textToItems(draft.decisions, meeting.decisions),
        follow_ups: textToItems(draft.followUps, meeting.follow_ups),
        version: withTranscript.version,
      });
    },
    onMutate: () => setSaveStatus("saving"),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.meeting(id), updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.meetings(updated.team_id) });
      setSaveStatus("saved");
      setEditing(false);
    },
    onError: () => setSaveStatus("error"),
  });
  const remove = useMutation({
    mutationFn: () => apiService.deleteMeeting(id),
    onSuccess: () => {
      if (meeting) void queryClient.invalidateQueries({ queryKey: queryKeys.meetings(meeting.team_id) });
      navigate(meeting ? `/t/${meeting.team_id}/meetings` : "/teams", { replace: true });
    },
  });
  const analyze = useMutation({
    mutationFn: () => apiService.startAnalysis(id),
    onSuccess: (job) => navigate(`/meetings/${id}/processing?job=${job.id}`),
  });

  if (meetingQuery.isLoading) return <LoadingState label="회의록을 불러오는 중입니다" />;
  if (meetingQuery.isError || !meeting) return <ErrorState message={meetingQuery.error?.message ?? "회의록을 찾을 수 없습니다."} onRetry={() => meetingQuery.refetch()} />;
  const canManage = meeting.is_mine || ["owner", "admin"].includes(teamQuery.data?.my_role ?? "member");
  const canEdit = canManage && meeting.processing_status !== "analyzing";

  function downloadText() {
    const current = meeting;
    if (!current) return;
    const body = `${current.title}\n${formatMeetingDate(current.meeting_at)}\n\n[요약]\n${current.summary || "정리 전"}\n\n[회의 전문]\n${current.transcript_edited}`;
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${current.title}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return <><PageHeader back title={meeting.title} description={`${formatMeetingDate(meeting.meeting_at)} · ${meeting.created_by.name}`} action={<StatusBadge status={meeting.processing_status} />} />
    <div className="mb-4 flex flex-wrap gap-2">{meeting.is_shared_with_me && <Badge className="bg-violet-50 text-violet-700"><LockKeyhole className="h-3.5 w-3.5" />공유받은 회의록 · {canEdit ? "관리자 편집 가능" : "읽기 전용"}</Badge>}</div>
    <MockBanner message="회의록 저장, 파일에서 전문 가져오기와 내용 정리는 실제 서버 기능입니다. 팀원 공유 화면은 아직 Mock 상태입니다." />
    <div className="my-5 grid grid-cols-4 gap-2"><Button disabled={!canEdit} onClick={() => setEditing((value) => !value)} variant={editing ? "secondary" : "outline"}><Edit3 className="h-4 w-4" /><span className="hidden sm:inline">편집</span></Button><Button asChild={canEdit} disabled={!canEdit} variant="outline">{canEdit ? <Link to={`/meetings/${id}/share`}><Share2 className="h-4 w-4" /><span className="hidden sm:inline">공유</span></Link> : <span><Users className="h-4 w-4" /></span>}</Button><Button onClick={downloadText} variant="outline"><Download className="h-4 w-4" /><span className="hidden sm:inline">TXT</span></Button><Button disabled={!canEdit} onClick={() => setDeleteOpen(true)} variant="danger"><Trash2 className="h-4 w-4" /><span className="hidden sm:inline">삭제</span></Button></div>
    {editing && <Card className="mb-5"><CardContent className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-bold text-slate-700">회의 제목<Input className="mt-2" maxLength={100} onChange={(event) => setDraft((value) => ({ ...value, title: event.target.value }))} value={draft.title} /></label><label className="text-sm font-bold text-slate-700">회의 날짜<Input className="mt-2" onChange={(event) => setDraft((value) => ({ ...value, date: event.target.value }))} type="date" value={draft.date} /></label></CardContent></Card>}
    {saveStatus !== "idle" && <div className="mb-3 text-right"><InlineSavingState state={saveStatus} /></div>}
    {analyze.error && <p className="mb-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{analyze.error.message}</p>}
    <MeetingTabs counts={{ actions: meeting.action_items.length }} onChange={setTab} value={tab}>
      {tab === "summary" && (meeting.summary ? (editing ? <Card><CardContent className="space-y-4"><p className="text-xs leading-5 text-slate-500">각 목록은 한 줄에 한 항목씩 입력하세요. 수정해도 처음 생성된 내용은 별도로 유지됩니다.</p><label className="block text-sm font-bold text-slate-700">핵심 요약<Textarea className="mt-2 min-h-32" onChange={(event) => setDraft((value) => ({ ...value, summary: event.target.value }))} value={draft.summary} /></label><label className="block text-sm font-bold text-slate-700">주요 논의사항<Textarea className="mt-2 min-h-28" onChange={(event) => setDraft((value) => ({ ...value, discussions: event.target.value }))} value={draft.discussions} /></label><label className="block text-sm font-bold text-slate-700">결정사항<Textarea className="mt-2 min-h-28" onChange={(event) => setDraft((value) => ({ ...value, decisions: event.target.value }))} value={draft.decisions} /></label><label className="block text-sm font-bold text-slate-700">후속 논의사항<Textarea className="mt-2 min-h-28" onChange={(event) => setDraft((value) => ({ ...value, followUps: event.target.value }))} value={draft.followUps} /></label><Button className="w-full" disabled={save.isPending || !draft.summary.trim()} onClick={() => save.mutate()}><Save className="h-4 w-4" />{save.isPending ? "저장 중..." : "정리 내용 저장"}</Button></CardContent></Card> : <div className="space-y-3"><Card className="border-indigo-100 bg-gradient-to-br from-indigo-50 to-violet-50 shadow-none"><CardContent><div className="flex items-center justify-between gap-3"><h3 className="flex items-center gap-2 text-sm font-bold text-indigo-950"><Sparkles className="h-4 w-4" />핵심 요약</h3><Badge className="bg-white/80 text-indigo-700">자동 정리 기반 편집본</Badge></div><p className="mt-3 text-sm leading-7 text-slate-700">{meeting.summary}</p></CardContent></Card><SectionCard items={meeting.key_discussions} title="주요 논의사항" /><SectionCard items={meeting.decisions} title="결정사항" tone="emerald" /><SectionCard items={meeting.follow_ups} title="후속 논의사항" tone="violet" /></div>) : <Card className="border-dashed shadow-none"><CardContent className="flex min-h-64 flex-col items-center justify-center text-center"><span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><Sparkles className="h-7 w-7" /></span><h3 className="mt-4 font-bold text-slate-900">회의 내용을 정리해 보세요</h3><p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">{meeting.transcript_edited ? "회의 내용을 살펴보고 요약, 결정사항과 액션아이템을 정리합니다." : "먼저 회의 전문을 입력하고 저장해야 정리할 수 있습니다."}</p>{canManage && <Button className="mt-5" disabled={!meeting.transcript_edited || analyze.isPending || meeting.processing_status === "analyzing"} onClick={() => analyze.mutate()}><Sparkles className="h-4 w-4" />{analyze.isPending ? "정리 요청 중..." : meeting.processing_status === "analyzing" ? "정리 중..." : "회의록 정리하기"}</Button>} {!canManage && <p className="mt-4 text-xs text-slate-500">읽기 전용 회의록은 작성자 또는 팀 관리자만 정리할 수 있습니다.</p>}</CardContent></Card>)}
      {tab === "transcript" && (editing || meeting.transcript_segments.length === 0) && <Card><CardContent><div className="mb-4 flex items-center justify-between"><h3 className="font-bold text-slate-900">전체 회의 내용</h3><Badge className="bg-emerald-50 text-emerald-700">실제 저장</Badge></div>{editing ? <><Textarea className="min-h-[26rem]" onChange={(event) => setDraft((value) => ({ ...value, transcript: event.target.value }))} value={draft.transcript} /><Button className="mt-4 w-full" disabled={save.isPending || !draft.title.trim() || !draft.transcript.trim()} onClick={() => save.mutate()}><Save className="h-4 w-4" />{save.isPending ? "저장 중..." : "변경사항 저장"}</Button></> : <div className="max-h-[34rem] overflow-y-auto whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-4 text-sm leading-7 text-slate-700">{meeting.transcript_edited || "저장된 회의 전문이 없습니다."}</div>}</CardContent></Card>}
      {tab === "actions" && <div className="space-y-3">{meeting.action_items.length ? meeting.action_items.map((item) => <ActionItemCard editable={false} item={item} key={item.id} />) : <Card className="shadow-none"><CardContent><p className="text-center text-sm text-slate-400">{meeting.summary ? "정리된 액션아이템이 없습니다." : "회의록을 정리하면 액션아이템이 표시됩니다."}</p></CardContent></Card>}</div>}
      {tab === "transcript" && !editing && meeting.transcript_segments.length > 0 && <DiarizedTranscript editable={canEdit} meetingId={id} segments={meeting.transcript_segments} speakers={meeting.transcript_speakers} />}
    </MeetingTabs>
    {remove.error && <p className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{remove.error.message}</p>}
    <ConfirmDialog open={deleteOpen} title="회의록을 삭제할까요?" description="목록에서 숨겨지는 소프트 삭제로 처리됩니다." confirmLabel={remove.isPending ? "삭제 중..." : "삭제"} onClose={() => setDeleteOpen(false)} onConfirm={() => remove.mutate()} />
  </>;
}
