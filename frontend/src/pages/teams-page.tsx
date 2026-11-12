import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Plus, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function TeamsPage() {
  const teams = useQuery({ queryKey: queryKeys.teams, queryFn: apiService.getTeams, staleTime: 5 * 60_000 });
  return <main className="min-h-dvh bg-slate-50 px-4 py-8"><div className="mx-auto max-w-2xl"><PageHeader title="내 팀" description="작업할 팀을 선택해 주세요." action={<Button asChild size="icon"><Link aria-label="새 팀 만들기" to="/teams/new"><Plus className="h-5 w-5" /></Link></Button>} />
    {teams.isLoading ? <LoadingState label="팀을 불러오는 중입니다" /> : teams.isError ? <ErrorState message={teams.error.message || "팀 목록을 불러오지 못했습니다."} onRetry={() => teams.refetch()} /> : teams.data?.length ? <div className="mt-5 space-y-3">{teams.data.map((team) => <Link className="group block rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500" key={team.id} to={`/t/${team.id}/meetings`}><Card className="transition group-hover:border-indigo-200"><CardContent className="flex items-center gap-4"><span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><UsersRound className="h-6 w-6" /></span><span className="min-w-0 flex-1"><span className="block truncate font-bold text-slate-900">{team.name}</span><span className="mt-1 block truncate text-xs text-slate-500">멤버 {team.member_count}명 · {team.my_role}</span></span><ArrowRight className="h-5 w-5 text-slate-300 group-hover:text-indigo-500" /></CardContent></Card></Link>)}</div> : <div className="mt-5"><EmptyState title="아직 소속된 팀이 없습니다" description="첫 팀을 만들어 회의록 관리를 시작해 보세요." action={<Button asChild><Link to="/teams/new">팀 만들기</Link></Button>} /></div>}
    <Button asChild className="mt-6 w-full" variant="outline"><Link to="/teams/new"><Plus className="h-4 w-4" />새로운 팀 만들기</Link></Button></div></main>;
}
