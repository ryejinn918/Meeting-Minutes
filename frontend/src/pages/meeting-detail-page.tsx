import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Edit3, LockKeyhole, Save, Share2, Sparkles, Trash2, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { MeetingTabs, type MeetingTab } from "@/components/shared/meeting-tabs";
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
import type { DiscussionItem, MeetingAttendee, MeetingType, SaveStatus, TranscriptSegment, TranscriptSpeaker } from "@/types/api";

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
  attendees,
  latestBatchId,
}: {
  meetingId: string;
  speakers: TranscriptSpeaker[];
  segments: TranscriptSegment[];
  editable: boolean;
  attendees: MeetingAttendee[];
  latestBatchId: string | null;
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
  const editSegment = useMutation({
    mutationFn: ({ segmentId, speakerId, scope }: { segmentId: string; speakerId: string; scope: "single" | "following" }) =>
      apiService.editSegmentSpeaker(meetingId, segmentId, speakerId, scope),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.meeting(meetingId) }),
  });
  const undo = useMutation({
    mutationFn: () => apiService.undoSpeakerEdit(meetingId, latestBatchId ?? ""),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.meeting(meetingId) }),
  });

  return <Card className="mt-3 shadow-none"><CardContent>
    <div className="flex items-center justify-between gap-3">
      <h3 className="font-bold text-slate-900">화자별 발언</h3>
      <Badge className="bg-indigo-50 text-indigo-700">타임스탬프 포함</Badge>
    </div>
    {editable && <div className="mt-4 grid gap-2 sm:grid-cols-2">{speakers.map((speaker) =>
      <div className="flex min-w-0 flex-wrap gap-2" key={speaker.id}>
        {speaker.candidate_user_id && <span className="self-center text-xs text-slate-500">후보 신뢰도 {Math.round((speaker.candidate_confidence ?? 0) * 100)}%</span>}
        <Input aria-label="화자 이름" className="min-w-0" list="meeting-attendees" maxLength={100} onChange={(event) => setNames((value) => ({ ...value, [speaker.id]: event.target.value }))} value={names[speaker.id] ?? speaker.display_name} />
        <Button disabled={rename.isPending || !(names[speaker.id] ?? "").trim()} onClick={() => rename.mutate({ speakerId: speaker.id, displayName: (names[speaker.id] ?? speaker.display_name).trim() })} size="sm" variant="outline">저장</Button>
      </div>)}<datalist id="meeting-attendees">{attendees.map((attendee) => <option key={attendee.id} value={attendee.display_name} />)}</datalist></div>}
    {editable && latestBatchId && <Button className="mt-3" disabled={undo.isPending} onClick={() => undo.mutate()} size="sm" variant="outline">마지막 화자 변경 되돌리기</Button>}
    {rename.isError && <p className="mt-3 text-sm text-rose-600">{rename.error.message}</p>}
    <ol className="mt-5 space-y-3">{segments.slice(0, visibleCount).map((segment) =>
      <li className="rounded-xl bg-slate-50 p-4" key={segment.id}>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold tabular-nums text-indigo-600">[{segmentTime(segment.start_seconds)}–{segmentTime(segment.end_seconds)}]</span>
          <span className="font-bold text-slate-700">{segment.speaker_name}</span>
        </div>
        <p className="mt-2 break-words text-sm leading-7 text-slate-700">{segment.text}</p>
        {editable && <div className="mt-3 flex flex-wrap items-center gap-2"><select aria-label="발언 화자 선택" className="min-h-10 min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 text-xs" defaultValue={segment.speaker_id} id={`segment-speaker-${segment.id}`}>{speakers.map((speaker) => <option key={speaker.id} value={speaker.id}>{speaker.display_name}</option>)}</select><Button disabled={editSegment.isPending} onClick={() => { const element = document.getElementById(`segment-speaker-${segment.id}`) as HTMLSelectElement | null; if (element) editSegment.mutate({ segmentId: segment.id, speakerId: element.value, scope: "single" }); }} size="sm" variant="outline">이 발언만</Button><Button disabled={editSegment.isPending} onClick={() => { const element = document.getElementById(`segment-speaker-${segment.id}`) as HTMLSelectElement | null; if (element) editSegment.mutate({ segmentId: segment.id, speakerId: element.value, scope: "following" }); }} size="sm" variant="outline">이후 같은 화자</Button></div>}
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
  const [draft, setDraft] = useState({ title: "", date: "", topic: "", location: "", meetingType: "general" as MeetingType, transcript: "", summary: "", discussions: "", decisions: "", followUps: "" });
  const [attendeeIds, setAttendeeIds] = useState<string[]>([]);
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    if (searchParams.get("tab") === "transcript") setTab("transcript");
  }, [searchParams]);

  useEffect(() => {
    if (meeting) {
      setDraft({
        title: meeting.title,
        date: meeting.meeting_at.slice(0, 10),
        topic: meeting.topic,
        location: meeting.location,
        meetingType: meeting.meeting_type,
        transcript: meeting.transcript_edited,
        summary: meeting.summary,
        discussions: itemsToText(meeting.key_discussions),
        decisions: itemsToText(meeting.decisions),
        followUps: itemsToText(meeting.follow_ups),
      });
      setAttendeeIds(
        meeting.attendees.flatMap((attendee) => attendee.user_id ? [attendee.user_id] : []),
      );
    }
  }, [meeting]);

  const save = useMutation({
    mutationFn: async () => {
      if (!meeting) throw new Error("회의록을 찾을 수 없습니다.");
      const externalAttendees = meeting.attendees.flatMap((attendee) =>
        attendee.user_id || !attendee.external_name
          ? []
          : [{
              external_name: attendee.external_name,
              external_organization: attendee.external_organization ?? undefined,
            }],
      );
      const updated = await apiService.updateMeeting(id, { title: draft.title.trim(), meeting_at: `${draft.date}T09:00:00+09:00`, topic: draft.topic.trim(), location: draft.location.trim(), meeting_type: draft.meetingType, attendees: [...attendeeIds.map((user_id) => ({ user_id })), ...externalAttendees], metadata_confirmed: true, version: meeting.version });
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
      queryClient.removeQueries({ queryKey: queryKeys.meeting(id) });
      if (meeting) void queryClient.invalidateQueries({ queryKey: queryKeys.meetings(meeting.team_id) });
      navigate(meeting ? `/t/${meeting.team_id}/meetings` : "/teams", { replace: true });
    },
  });
  const analyze = useMutation({
    mutationFn: () => apiService.startAnalysis(id),
    onSuccess: (job) => navigate(`/meetings/${id}/processing?job=${job.id}`),
  });
  const correct = useMutation({
    mutationFn: () => apiService.correctTranscript(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.meeting(id) }),
  });
  const answerQuestion = useMutation({
    mutationFn: ({ questionId, answer, status }: { questionId: string; answer: string | null; status: "answered" | "dismissed" }) => apiService.answerQuestion(id, questionId, answer, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.meeting(id) }),
  });
  const review = useMutation({
    mutationFn: (status: "review_required" | "approved" | "rejected") => apiService.reviewMeeting(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.meeting(id) }),
  });

  if (meetingQuery.isLoading) return <LoadingState label="회의록을 불러오는 중입니다" />;
  if (meetingQuery.isError || !meeting) return <ErrorState message={meetingQuery.error?.message ?? "회의록을 찾을 수 없습니다."} onRetry={() => meetingQuery.refetch()} />;
  const canManage = meeting.is_mine || ["owner", "admin"].includes(teamQuery.data?.my_role ?? "member");
  const canEdit = canManage && meeting.processing_status !== "analyzing";
  const canDelete = canManage && !["transcribing", "analyzing"].includes(meeting.processing_status);

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
    <Card className="mt-5 shadow-none"><CardContent><div className="grid gap-3 text-sm sm:grid-cols-2"><div><p className="text-xs font-semibold text-slate-400">회의 주제</p><p className="mt-1 text-slate-700">{meeting.topic || "미입력"}</p></div><div><p className="text-xs font-semibold text-slate-400">회의 유형</p><p className="mt-1 text-slate-700">{{ general: "일반 회의", project: "프로젝트 회의", interview: "인터뷰", workshop: "워크숍" }[meeting.meeting_type]}</p></div><div><p className="text-xs font-semibold text-slate-400">참석자</p><p className="mt-1 text-slate-700">{meeting.attendees.map((item) => item.display_name).join(", ") || "미입력"}</p></div></div></CardContent></Card>
    <div className="my-5 grid grid-cols-4 gap-2"><Button disabled={!canEdit} onClick={() => setEditing((value) => !value)} variant={editing ? "secondary" : "outline"}><Edit3 className="h-4 w-4" /><span className="hidden sm:inline">편집</span></Button><Button asChild={canEdit} disabled={!canEdit} variant="outline">{canEdit ? <Link to={`/meetings/${id}/share`}><Share2 className="h-4 w-4" /><span className="hidden sm:inline">공유</span></Link> : <span><Users className="h-4 w-4" /></span>}</Button><Button onClick={downloadText} variant="outline"><Download className="h-4 w-4" /><span className="hidden sm:inline">TXT</span></Button><Button disabled={!canDelete} onClick={() => setDeleteOpen(true)} title={canDelete ? "회의록 삭제" : "진행 중인 작업이 끝난 뒤 삭제할 수 있습니다"} variant="danger"><Trash2 className="h-4 w-4" /><span className="hidden sm:inline">삭제</span></Button></div>
    {editing && <Card className="mb-5"><CardContent className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-bold text-slate-700">회의 제목<Input className="mt-2" maxLength={100} onChange={(event) => setDraft((value) => ({ ...value, title: event.target.value }))} value={draft.title} /></label><label className="text-sm font-bold text-slate-700">회의 날짜<Input className="mt-2" onChange={(event) => setDraft((value) => ({ ...value, date: event.target.value }))} type="date" value={draft.date} /></label><label className="text-sm font-bold text-slate-700">회의 주제<Input className="mt-2" maxLength={500} onChange={(event) => setDraft((value) => ({ ...value, topic: event.target.value }))} value={draft.topic} /></label><label className="text-sm font-bold text-slate-700">회의 유형<select className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3" onChange={(event) => setDraft((value) => ({ ...value, meetingType: event.target.value as MeetingType }))} value={draft.meetingType}><option value="general">일반 회의</option><option value="project">프로젝트 회의</option><option value="interview">인터뷰</option><option value="workshop">워크숍</option></select></label>{teamQuery.data?.members.length ? <fieldset className="sm:col-span-2"><legend className="text-sm font-bold text-slate-700">참석자</legend><div className="mt-2 grid gap-2 sm:grid-cols-2">{teamQuery.data.members.map((member) => <label className="flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-3 text-sm" key={member.id}><input checked={attendeeIds.includes(member.id)} onChange={(event) => setAttendeeIds((current) => event.target.checked ? [...current, member.id] : current.filter((id) => id !== member.id))} type="checkbox" />{member.name}</label>)}</div></fieldset> : null}</CardContent></Card>}
    {saveStatus !== "idle" && <div className="mb-3 text-right"><InlineSavingState state={saveStatus} /></div>}
    {analyze.error && <p className="mb-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{analyze.error.message}</p>}
    {meeting.questions.length > 0 && <Card className="mb-5 border-amber-200 bg-amber-50/50 shadow-none"><CardContent><h2 className="font-bold text-slate-900">확인이 필요한 내용</h2><p className="mt-1 text-xs text-slate-500">확실하지 않은 핵심 정보만 확인합니다. 답변해도 음성 전사를 다시 실행하지 않아요.</p><div className="mt-4 space-y-3">{meeting.questions.filter((question) => question.status === "pending").map((question) => <div className="rounded-xl bg-white p-3" key={question.id}><p className="text-sm font-semibold text-slate-800">{question.question}</p>{question.evidence && <p className="mt-1 text-xs text-slate-500">근거: {question.evidence}</p>}<div className="mt-3 flex gap-2"><Input aria-label="확인 질문 답변" onChange={(event) => setQuestionAnswers((current) => ({ ...current, [question.id]: event.target.value }))} placeholder="확인한 내용을 입력하세요" value={questionAnswers[question.id] ?? ""} /><Button disabled={answerQuestion.isPending || !(questionAnswers[question.id] ?? "").trim()} onClick={() => answerQuestion.mutate({ questionId: question.id, answer: (questionAnswers[question.id] ?? "").trim(), status: "answered" })} size="sm">저장</Button><Button disabled={answerQuestion.isPending} onClick={() => answerQuestion.mutate({ questionId: question.id, answer: null, status: "dismissed" })} size="sm" variant="outline">건너뛰기</Button></div></div>)}</div></CardContent></Card>}
    {canManage && meeting.summary && <Card className="mb-5 border-indigo-100 shadow-none"><CardContent><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-bold text-slate-900">검토 상태</p><p className="mt-1 text-xs text-slate-500">{meeting.review_status === "approved" ? "승인된 회의록입니다." : meeting.review_status === "review_required" ? "검토 후 승인할 수 있습니다." : meeting.review_status === "rejected" ? "수정 후 다시 검토해 주세요." : "초안 상태입니다."}</p></div><div className="flex flex-wrap gap-2"><Button disabled={review.isPending} onClick={() => review.mutate("review_required")} size="sm" variant="outline">검토 요청</Button><Button disabled={review.isPending || meeting.review_status !== "review_required"} onClick={() => review.mutate("approved")} size="sm">승인</Button><Button disabled={review.isPending || meeting.review_status !== "review_required"} onClick={() => review.mutate("rejected")} size="sm" variant="outline">반려</Button></div></div>{review.isError && <p className="mt-2 text-sm text-rose-600">{review.error.message}</p>}</CardContent></Card>}
    <MeetingTabs counts={{ actions: meeting.action_items.length }} onChange={setTab} value={tab}>
      {tab === "transcript" && canEdit && <Card className="mb-3 border-indigo-100 shadow-none"><CardContent><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-bold text-slate-900">전문 용어와 오타 확인</h3><p className="mt-1 text-xs leading-5 text-slate-500">회의 주제와 팀의 선택 용어집을 참고합니다. 원본과 현재 편집본은 그대로 보존됩니다.</p></div><Button disabled={correct.isPending || !meeting.transcript_edited} onClick={() => correct.mutate()} variant="outline">{correct.isPending ? "확인 중..." : "교정본 만들기"}</Button></div>{correct.isError && <p className="mt-3 text-sm text-rose-600">{correct.error.message}</p>}{meeting.transcript_corrected && <div className="mt-4 rounded-xl bg-slate-50 p-4"><p className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words text-sm leading-7 text-slate-700">{meeting.transcript_corrected}</p><Button className="mt-3" onClick={() => { setDraft((value) => ({ ...value, transcript: meeting.transcript_corrected })); setEditing(true); }} size="sm">교정본을 편집본에 적용</Button></div>}</CardContent></Card>}
      {tab === "summary" && (meeting.summary ? (editing ? <Card><CardContent className="space-y-4"><p className="text-xs leading-5 text-slate-500">각 목록은 한 줄에 한 항목씩 입력하세요. 수정해도 처음 생성된 내용은 별도로 유지됩니다.</p><label className="block text-sm font-bold text-slate-700">핵심 요약<Textarea className="mt-2 min-h-32" onChange={(event) => setDraft((value) => ({ ...value, summary: event.target.value }))} value={draft.summary} /></label><label className="block text-sm font-bold text-slate-700">주요 논의사항<Textarea className="mt-2 min-h-28" onChange={(event) => setDraft((value) => ({ ...value, discussions: event.target.value }))} value={draft.discussions} /></label><label className="block text-sm font-bold text-slate-700">결정사항<Textarea className="mt-2 min-h-28" onChange={(event) => setDraft((value) => ({ ...value, decisions: event.target.value }))} value={draft.decisions} /></label><label className="block text-sm font-bold text-slate-700">후속 논의사항<Textarea className="mt-2 min-h-28" onChange={(event) => setDraft((value) => ({ ...value, followUps: event.target.value }))} value={draft.followUps} /></label><Button className="w-full" disabled={save.isPending || !draft.summary.trim()} onClick={() => save.mutate()}><Save className="h-4 w-4" />{save.isPending ? "저장 중..." : "정리 내용 저장"}</Button></CardContent></Card> : <div className="space-y-3"><Card className="border-indigo-100 bg-gradient-to-br from-indigo-50 to-violet-50 shadow-none"><CardContent><div className="flex items-center justify-between gap-3"><h3 className="flex items-center gap-2 text-sm font-bold text-indigo-950"><Sparkles className="h-4 w-4" />핵심 요약</h3><Badge className="bg-white/80 text-indigo-700">자동 정리 기반 편집본</Badge></div><p className="mt-3 text-sm leading-7 text-slate-700">{meeting.summary}</p></CardContent></Card><SectionCard items={meeting.key_discussions} title="주요 논의사항" /><SectionCard items={meeting.decisions} title="결정사항" tone="emerald" /><SectionCard items={meeting.follow_ups} title="후속 논의사항" tone="violet" /></div>) : <Card className="border-dashed shadow-none"><CardContent className="flex min-h-64 flex-col items-center justify-center text-center"><span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><Sparkles className="h-7 w-7" /></span><h3 className="mt-4 font-bold text-slate-900">회의 내용을 정리해 보세요</h3><p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">{meeting.transcript_edited ? "회의 내용을 살펴보고 요약, 결정사항과 액션아이템을 정리합니다." : "먼저 회의 전문을 입력하고 저장해야 정리할 수 있습니다."}</p>{canManage && <Button className="mt-5" disabled={!meeting.transcript_edited || analyze.isPending || meeting.processing_status === "analyzing"} onClick={() => analyze.mutate()}><Sparkles className="h-4 w-4" />{analyze.isPending ? "정리 요청 중..." : meeting.processing_status === "analyzing" ? "정리 중..." : "회의록 정리하기"}</Button>} {!canManage && <p className="mt-4 text-xs text-slate-500">읽기 전용 회의록은 작성자 또는 팀 관리자만 정리할 수 있습니다.</p>}</CardContent></Card>)}
      {tab === "transcript" && (editing || meeting.transcript_segments.length === 0) && <Card><CardContent><div className="mb-4 flex items-center justify-between"><h3 className="font-bold text-slate-900">전체 회의 내용</h3><Badge className="bg-emerald-50 text-emerald-700">실제 저장</Badge></div>{editing ? <><Textarea className="min-h-[26rem]" onChange={(event) => setDraft((value) => ({ ...value, transcript: event.target.value }))} value={draft.transcript} /><Button className="mt-4 w-full" disabled={save.isPending || !draft.title.trim() || !draft.transcript.trim()} onClick={() => save.mutate()}><Save className="h-4 w-4" />{save.isPending ? "저장 중..." : "변경사항 저장"}</Button></> : <div className="max-h-[34rem] overflow-y-auto whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-4 text-sm leading-7 text-slate-700">{meeting.transcript_edited || "저장된 회의 전문이 없습니다."}</div>}</CardContent></Card>}
      {tab === "actions" && <div className="space-y-3">{meeting.action_items.length ? meeting.action_items.map((item) => <ActionItemCard editable={false} item={item} key={item.id} />) : <Card className="shadow-none"><CardContent><p className="text-center text-sm text-slate-400">{meeting.summary ? "정리된 액션아이템이 없습니다." : "회의록을 정리하면 액션아이템이 표시됩니다."}</p></CardContent></Card>}</div>}
      {tab === "transcript" && !editing && meeting.transcript_segments.length > 0 && <DiarizedTranscript attendees={meeting.attendees} editable={canEdit} latestBatchId={meeting.latest_speaker_edit_batch_id} meetingId={id} segments={meeting.transcript_segments} speakers={meeting.transcript_speakers} />}
    </MeetingTabs>
    {remove.error && <p className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{remove.error.message}</p>}
    <ConfirmDialog keepOpenOnConfirm open={deleteOpen} pending={remove.isPending} title="회의록을 삭제할까요?" description="목록에서 숨겨지는 소프트 삭제로 처리됩니다. 원본 파일은 즉시 제거하지 않고 별도 보존·정리 정책을 따릅니다." confirmLabel={remove.isPending ? "삭제 중..." : "삭제"} onClose={() => setDeleteOpen(false)} onConfirm={() => remove.mutate()} />
  </>;
}
