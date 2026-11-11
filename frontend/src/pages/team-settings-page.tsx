import { useQuery } from "@tanstack/react-query";
import { Copy, LogOut, MailPlus, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { MockBanner } from "@/components/shared/mock-banner";
import { PageHeader } from "@/components/shared/page-header";
import { LoadingState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/features/auth/auth-context";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function TeamSettingsPage() {
  const { teamId = "" } = useParams(); const navigate = useNavigate(); const { signOut } = useAuth(); const [copied, setCopied] = useState(false); const [logoutOpen, setLogoutOpen] = useState(false);
  const team = useQuery({ queryKey: queryKeys.team(teamId), queryFn: () => apiService.getTeam(teamId) });
  const me = useQuery({ queryKey: queryKeys.me, queryFn: apiService.getMe });
  const canManage = ["owner", "admin"].includes(team.data?.my_role ?? "member");
  async function copyInvite() { await navigator.clipboard?.writeText("https://meetflow.example/invite/mock-only"); setCopied(true); window.setTimeout(() => setCopied(false), 1600); }
  return <><PageHeader title="팀 관리" description={`${team.data?.name ?? "팀"}의 멤버와 내 프로필을 확인하세요.`} /><MockBanner message="팀원 목록과 프로필은 실제 데이터입니다. 초대 링크 기능만 아직 Mock입니다." />
    <section className="mt-6"><div className="mb-3 flex items-center justify-between"><h2 className="font-bold text-slate-900">팀원</h2><Button disabled={!canManage} size="sm" title={canManage ? "Mock 팀원 초대" : "owner/admin만 초대할 수 있습니다"} variant="secondary"><MailPlus className="h-4 w-4" />팀원 초대</Button></div>{team.isLoading ? <LoadingState /> : <Card className="shadow-none"><div className="divide-y divide-slate-100">{team.data?.members.map((member) => <div className="flex min-w-0 items-center gap-3 p-4" key={member.id}><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${member.avatar_color ?? "bg-indigo-500"}`}>{member.name.slice(0, 1)}</span><div className="min-w-0 flex-1"><p className="flex items-center gap-1.5 text-sm font-bold text-slate-800">{member.name}{member.role !== "member" && <ShieldCheck className="h-3.5 w-3.5 text-indigo-500" />}</p><p className="truncate text-xs text-slate-500">{member.email}</p></div><span className="text-[10px] font-bold uppercase text-slate-400">{member.role}</span></div>)}</div></Card>}</section>
    <Card className="mt-5 shadow-none"><CardContent><h2 className="font-bold text-slate-900">초대 링크</h2><p className="mt-1 text-xs leading-5 text-slate-500">다음 단계에서 만료되는 실제 초대 링크와 이메일 확인을 연결합니다.</p><div className="mt-3 flex gap-2"><div className="min-w-0 flex-1 truncate rounded-xl bg-slate-100 px-3 py-3 text-xs text-slate-500">meetflow.example/invite/mock-only</div><Button aria-label="Mock 초대 링크 복사" onClick={copyInvite} size="icon" variant="outline"><Copy className="h-4 w-4" /></Button></div>{copied && <p className="mt-2 text-xs font-semibold text-emerald-600">Mock 링크를 복사했습니다. 실제 초대는 전송되지 않았습니다.</p>}</CardContent></Card>
    <Card className="mt-5 shadow-none"><CardContent><h2 className="font-bold text-slate-900">내 프로필</h2><div className="mt-4 flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><UserRound className="h-5 w-5" /></span><div className="min-w-0"><p className="font-bold text-slate-800">{me.data?.name ?? "사용자"}</p><p className="truncate text-xs text-slate-500">{me.data?.email}</p></div></div><Button className="mt-5 w-full" onClick={() => setLogoutOpen(true)} variant="danger"><LogOut className="h-4 w-4" />로그아웃</Button></CardContent></Card>
    <ConfirmDialog confirmLabel="로그아웃" description="현재 기기의 Supabase 세션을 종료합니다." onClose={() => setLogoutOpen(false)} onConfirm={() => { void signOut().then(() => navigate("/login", { replace: true })); }} open={logoutOpen} title="로그아웃할까요?" />
  </>;
}
