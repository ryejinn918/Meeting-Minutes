import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, LockKeyhole, Share2, UserRoundCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { MemberSelector } from "@/features/sharing/member-selector";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState, LoadingState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/features/auth/auth-context";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function SharePage() {
  const { id = "" } = useParams(); const navigate = useNavigate(); const { user } = useAuth(); const [query, setQuery] = useState(""); const [selected, setSelected] = useState<string[]>([]); const [saved, setSaved] = useState(false);
  const meeting = useQuery({ queryKey: queryKeys.meeting(id), queryFn: () => apiService.getMeeting(id) });
  const team = useQuery({ queryKey: queryKeys.team(meeting.data?.team_id ?? "unknown"), queryFn: () => apiService.getTeam(meeting.data!.team_id), enabled: Boolean(meeting.data) });
  useEffect(() => { if (meeting.data) setSelected(meeting.data.shared_member_ids); }, [meeting.data]);
  const save = useMutation({ mutationFn: () => apiService.replaceMeetingShares(id, selected), onSuccess: () => { setSaved(true); window.setTimeout(() => navigate(`/meetings/${id}`), 700); } });
  if (meeting.isLoading || team.isLoading) return <LoadingState />; if (meeting.isError || team.isError || !meeting.data) return <ErrorState message="공유 정보를 불러오지 못했습니다." />;
  const selectableMembers = (team.data?.members ?? []).filter((member) => member.id !== user?.id);
  return <><PageHeader back title="회의록 공유" description={meeting.data.title} /><Card className="mt-5 border-indigo-100 bg-indigo-50/50 shadow-none"><CardContent className="flex gap-3"><LockKeyhole className="h-5 w-5 shrink-0 text-indigo-600" /><div><p className="text-sm font-bold text-indigo-950">공유받은 팀원은 읽기 전용입니다</p><p className="mt-1 text-xs leading-5 text-indigo-700">회의록을 열람할 수 있지만 내용을 수정하거나 다시 공유할 수 없습니다.</p></div></CardContent></Card>
    <div className="my-5 flex items-center justify-between"><div><h2 className="font-bold text-slate-900">공유할 팀원</h2><p className="mt-1 text-xs text-slate-500">같은 팀의 멤버만 선택할 수 있습니다.</p></div><span className="rounded-full bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-700">{selected.length}명 선택</span></div>
    <MemberSelector members={selectableMembers} onQueryChange={setQuery} onToggle={(memberId) => { setSaved(false); setSelected((current) => current.includes(memberId) ? current.filter((idValue) => idValue !== memberId) : [...current, memberId]); }} query={query} selectedIds={selected} />
    {saved && <p className="mt-4 flex items-center justify-center gap-2 text-sm font-semibold text-emerald-600"><CheckCircle2 className="h-4 w-4" />공유 대상을 저장했어요.</p>}
    <div className="sticky bottom-20 mt-6 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-xl backdrop-blur"><Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}><Share2 className="h-4 w-4" />{save.isPending ? "공유 저장 중..." : "공유하기"}</Button>{selected.length > 0 && <Button className="mt-2 w-full" onClick={() => setSelected([])} variant="ghost"><UserRoundCheck className="h-4 w-4" />모든 선택 취소</Button>}</div>
  </>;
}
