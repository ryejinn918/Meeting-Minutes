import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function InvitationPage() {
  const { token = "" } = useParams(); const navigate = useNavigate(); const queryClient = useQueryClient();
  const accept = useMutation({ mutationFn: () => apiService.acceptInvitation(token), onSuccess: (result) => { void queryClient.invalidateQueries({ queryKey: queryKeys.teams }); window.setTimeout(() => navigate(`/t/${result.team_id}/meetings`, { replace: true }), 800); } });
  const decline = useMutation({ mutationFn: () => apiService.declineInvitation(token), onSuccess: () => window.setTimeout(() => navigate("/teams", { replace: true }), 600) });
  return <main className="min-h-dvh bg-slate-50 px-4 py-8"><div className="mx-auto max-w-lg"><PageHeader title="팀 초대" description="초대받은 이메일 계정으로 로그인했는지 확인해 주세요." /><Card className="mt-5"><CardContent className="text-center">{accept.isSuccess ? <><CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" /><p className="mt-3 font-bold">팀에 참여했어요.</p></> : decline.isSuccess ? <><CheckCircle2 className="mx-auto h-10 w-10 text-slate-500" /><p className="mt-3 font-bold">초대를 거절했어요.</p></> : <><p className="text-sm text-slate-600">초대를 수락하면 이 팀의 구성원 목록에 추가됩니다. 기존 비공개 회의록은 자동으로 공개되지 않습니다.</p><Button className="mt-5 w-full" disabled={accept.isPending || decline.isPending || !token} onClick={() => accept.mutate()}>{accept.isPending ? "수락 중..." : "초대 수락"}</Button><Button className="mt-2 w-full" disabled={accept.isPending || decline.isPending || !token} onClick={() => decline.mutate()} variant="ghost">{decline.isPending ? "거절 중..." : "초대 거절"}</Button></>}{(accept.error || decline.error) && <p className="mt-3 text-sm text-rose-700">{(accept.error || decline.error)?.message}</p>}</CardContent></Card></div></main>;
}
