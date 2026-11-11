import { useQuery } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { MeetingCard } from "@/components/shared/meeting-card";
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function MeetingsPage() {
  const { teamId = "" } = useParams(); const [search, setSearch] = useState("");
  const meetings = useQuery({ queryKey: queryKeys.meetings(teamId), queryFn: () => apiService.getMeetings(teamId) });
  const team = useQuery({ queryKey: queryKeys.team(teamId), queryFn: () => apiService.getTeam(teamId) });
  const me = useQuery({ queryKey: queryKeys.me, queryFn: apiService.getMe });
  const filtered = meetings.data?.filter((meeting) => meeting.title.toLowerCase().includes(search.toLowerCase())) ?? [];
  return <><section className="mb-6"><p className="text-xs font-bold uppercase tracking-wider text-indigo-600">{team.data?.name ?? "팀 회의록"}</p><div className="mt-2 flex items-end justify-between gap-3"><div><h1 className="text-2xl font-extrabold tracking-tight text-slate-950">안녕하세요, {me.data?.name ?? "팀원"}님 👋</h1><p className="mt-1 text-sm text-slate-500">팀의 최근 회의를 확인해 보세요.</p></div><Button asChild className="shrink-0" size="icon"><Link aria-label="새 회의록" to={`/t/${teamId}/meetings/new`}><Plus className="h-5 w-5" /></Link></Button></div></section>
    <label className="relative mt-5 block"><Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" /><Input className="pl-10" onChange={(e) => setSearch(e.target.value)} placeholder="회의록 검색" value={search} /></label>
    <div className="mt-6 flex items-center justify-between"><h2 className="font-bold text-slate-900">최근 회의록</h2><span className="text-xs text-slate-400">{filtered.length}개</span></div>
    <div className="mt-3 space-y-3">{meetings.isLoading ? <LoadingState /> : meetings.isError ? <ErrorState message="회의록을 불러오지 못했습니다." onRetry={() => meetings.refetch()} /> : filtered.length ? filtered.map((meeting) => <MeetingCard key={meeting.id} meeting={meeting} />) : <EmptyState searched={Boolean(search)} title={search ? "검색 결과가 없습니다" : "아직 회의록이 없습니다"} description={search ? "다른 검색어를 입력해 보세요." : "첫 회의록을 만들어 팀의 논의를 기록해 보세요."} action={!search && <Button asChild><Link to={`/t/${teamId}/meetings/new`}>새 회의록 만들기</Link></Button>} />}</div></>;
}
