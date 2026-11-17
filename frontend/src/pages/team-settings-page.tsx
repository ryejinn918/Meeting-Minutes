import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Edit3, List, LogOut, MailPlus, ShieldCheck, Trash2, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { PageHeader } from "@/components/shared/page-header";
import { LoadingState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/features/auth/auth-context";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";
import type { MeetingTemplate, MeetingType } from "@/types/api";

const TEMPLATE_SECTIONS: Record<MeetingType, Array<{ key: string; label: string }>> = {
  general: [{ key: "summary", label: "회의 개요" }, { key: "discussions", label: "주요 논의사항" }, { key: "decisions", label: "결정사항" }, { key: "action_items", label: "액션아이템" }],
  project: [{ key: "progress", label: "진행 현황" }, { key: "issues", label: "주요 이슈" }, { key: "decisions", label: "의사결정" }, { key: "action_items", label: "후속 조치" }],
  interview: [{ key: "overview", label: "인터뷰 개요" }, { key: "answers", label: "핵심 답변" }, { key: "insights", label: "주요 인사이트" }],
  workshop: [{ key: "purpose", label: "회의 목적" }, { key: "ideas", label: "제안 아이디어" }, { key: "agreements", label: "합의 내용" }, { key: "action_items", label: "향후 과제" }],
};

function QualitySettings({ teamId, canManage }: { teamId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const options = useQuery({ queryKey: queryKeys.qualityOptions(teamId), queryFn: () => apiService.getQualityOptions(teamId) });
  const [templateForm, setTemplateForm] = useState({ id: "", name: "", type: "general" as MeetingType, rules: "" });
  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.qualityOptions(teamId) });
  const saveTemplate = useMutation({
    mutationFn: () => templateForm.id
      ? apiService.updateTemplate(templateForm.id, { name: templateForm.name.trim(), writing_rules: templateForm.rules.trim(), sections: TEMPLATE_SECTIONS[templateForm.type] })
      : apiService.createTemplate({ organization_id: null, department_id: null, team_id: teamId, name: templateForm.name.trim(), description: "", meeting_type: "project", sections: TEMPLATE_SECTIONS.project, writing_rules: templateForm.rules.trim(), is_default: false }),
    onSuccess: () => { setTemplateForm({ id: "", name: "", type: "general", rules: "" }); void refresh(); },
  });
  const deleteTemplate = useMutation({ mutationFn: (id: string) => apiService.deleteTemplate(id), onSuccess: () => refresh() });
  const editTemplate = (item: MeetingTemplate) => setTemplateForm({ id: item.id, name: item.name, type: item.meeting_type, rules: item.writing_rules });

  return <section className="mt-6 space-y-5"><Card className="shadow-none"><CardContent><h2 className="font-bold text-slate-900">팀 회의록 템플릿</h2><p className="mt-1 text-xs leading-5 text-slate-500">팀의 회의록 작성 규칙을 등록하면 회의 생성 시 선택할 수 있어요.</p>{canManage && <div className="mt-4 space-y-2"><Input onChange={(event) => setTemplateForm((value) => ({ ...value, name: event.target.value }))} placeholder="템플릿 이름" value={templateForm.name} /><Textarea onChange={(event) => setTemplateForm((value) => ({ ...value, rules: event.target.value }))} placeholder="문체와 작성 규칙(선택)" value={templateForm.rules} /><Button disabled={saveTemplate.isPending || !templateForm.name.trim()} onClick={() => saveTemplate.mutate()}>{templateForm.id ? "템플릿 수정" : "템플릿 추가"}</Button>{templateForm.id && <Button onClick={() => setTemplateForm({ id: "", name: "", type: "general", rules: "" })} variant="outline">취소</Button>}</div>}<div className="mt-4 space-y-2">{options.data?.templates.filter((item) => !item.is_builtin).map((item) => <div className="flex items-center gap-2 rounded-xl bg-slate-50 p-3" key={item.id}><div className="min-w-0 flex-1"><p className="font-bold text-slate-800">{item.name}</p><p className="text-xs text-slate-500">버전 {item.version}</p></div>{canManage && <><Button aria-label="템플릿 수정" onClick={() => editTemplate(item)} size="icon" variant="outline"><Edit3 className="h-4 w-4" /></Button><Button aria-label="템플릿 삭제" onClick={() => deleteTemplate.mutate(item.id)} size="icon" variant="danger"><Trash2 className="h-4 w-4" /></Button></>}</div>)}</div></CardContent></Card></section>;
}

export function TeamSettingsPage() {
  const { teamId = "" } = useParams(); const navigate = useNavigate(); const { signOut } = useAuth(); const queryClient = useQueryClient(); const [logoutOpen, setLogoutOpen] = useState(false); const [inviteEmail, setInviteEmail] = useState(""); const [showInvite, setShowInvite] = useState(false); const [inviteSent, setInviteSent] = useState(false);
  const team = useQuery({ queryKey: queryKeys.team(teamId), queryFn: () => apiService.getTeam(teamId) });
  const [projectTopic, setProjectTopic] = useState("");
  const saveProjectTopic = useMutation({
    mutationFn: () => apiService.updateTeam(teamId, { project_topic: projectTopic.trim() }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.team(teamId) }),
  });
  const loadedProjectTopic = team.data?.project_topic ?? "";
  useEffect(() => setProjectTopic(loadedProjectTopic), [loadedProjectTopic]);
  const me = useQuery({ queryKey: queryKeys.me, queryFn: apiService.getMe });
  const canManage = ["owner", "admin"].includes(team.data?.my_role ?? "member");
  const [voiceLabel, setVoiceLabel] = useState("");
  const invite = useMutation({ mutationFn: () => apiService.createInvitation(teamId, inviteEmail.trim()), onSuccess: () => { setInviteEmail(""); setShowInvite(false); setInviteSent(true); window.setTimeout(() => setInviteSent(false), 3000); } });
  const voiceProfile = useMutation({ mutationFn: (consented: boolean) => apiService.registerVoiceProfile(teamId, consented, voiceLabel.trim()) });
  return <><PageHeader action={<Button asChild size="sm" variant="outline"><Link to="/teams"><List className="h-4 w-4" />팀 목록</Link></Button>} title="팀 관리" description={`${team.data?.name ?? "팀"}의 멤버와 내 프로필을 확인하세요.`} />
    <section className="mt-6"><div className="mb-3 flex items-center justify-between"><h2 className="font-bold text-slate-900">팀원</h2><Button disabled={!canManage} onClick={() => setShowInvite((value) => !value)} size="sm" title={canManage ? "가입한 사용자에게 초대 알림 보내기" : "owner/admin만 초대할 수 있습니다"} variant="secondary"><MailPlus className="h-4 w-4" />팀원 초대</Button></div>{showInvite && <Card className="mb-4 shadow-none"><CardContent><p className="text-sm font-semibold text-slate-800">가입한 사용자의 이메일을 입력하세요.</p><p className="mt-1 text-xs text-slate-500">상대방의 알림에서 수락하면 팀원이 됩니다.</p><div className="mt-3 flex gap-2"><Input aria-label="초대할 이메일" className="min-w-0 flex-1" onChange={(event) => setInviteEmail(event.target.value)} placeholder="name@example.com" type="email" value={inviteEmail} /><Button disabled={invite.isPending || !inviteEmail.trim()} onClick={() => invite.mutate()}>{invite.isPending ? "보내는 중..." : "알림 보내기"}</Button></div>{(invite.error) && <p className="mt-2 text-xs text-rose-700">{invite.error.message}</p>}</CardContent></Card>}{inviteSent && <p className="mb-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">초대 알림을 보냈어요.</p>}{team.isLoading ? <LoadingState /> : <Card className="shadow-none"><div className="divide-y divide-slate-100">{team.data?.members.map((member) => <div className="flex min-w-0 items-center gap-3 p-4" key={member.id}><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${member.avatar_color ?? "bg-indigo-500"}`}>{member.name.slice(0, 1)}</span><div className="min-w-0 flex-1"><p className="flex items-center gap-1.5 text-sm font-bold text-slate-800">{member.name}{member.role !== "member" && <ShieldCheck className="h-3.5 w-3.5 text-indigo-500" />}</p><p className="truncate text-xs text-slate-500">{member.email}</p></div><span className="text-[10px] font-bold uppercase text-slate-400">{member.role}</span></div>)}</div></Card>}</section>
    <Card className="mt-5 shadow-none"><CardContent><h2 className="font-bold text-slate-900">팀 프로젝트 주제</h2><p className="mt-1 text-xs leading-5 text-slate-500">팀의 기본 프로젝트나 업무 주제를 입력하면 회의 전사 교정에 참고합니다.</p><div className="mt-3 flex gap-2"><Input aria-label="팀 프로젝트 주제" disabled={!canManage} maxLength={500} onChange={(event) => setProjectTopic(event.target.value)} placeholder="예: 사내 AI 회의록 자동화 프로젝트" value={projectTopic || loadedProjectTopic} /><Button disabled={!canManage || saveProjectTopic.isPending} onClick={() => saveProjectTopic.mutate()}>{saveProjectTopic.isPending ? "저장 중..." : "저장"}</Button></div>{saveProjectTopic.isSuccess && <p className="mt-2 text-xs text-emerald-600">팀 프로젝트 주제를 저장했어요.</p>}{saveProjectTopic.isError && <p className="mt-2 text-xs text-rose-600">{saveProjectTopic.error.message}</p>}</CardContent></Card>
    <QualitySettings canManage={canManage} teamId={teamId} />
    <Card className="mt-5 shadow-none"><CardContent><h2 className="font-bold text-slate-900">화자 확인용 음성 등록</h2><p className="mt-1 text-xs leading-5 text-slate-500">선택 기능입니다. 현재는 동의와 프로필 상태만 저장하며, 자동으로 실명을 확정하지 않습니다.</p><div className="mt-3 flex gap-2"><Input aria-label="음성 프로필 이름" onChange={(event) => setVoiceLabel(event.target.value)} placeholder="예: 내 목소리" value={voiceLabel} /><Button disabled={voiceProfile.isPending} onClick={() => voiceProfile.mutate(true)}>등록 동의</Button><Button disabled={voiceProfile.isPending} onClick={() => voiceProfile.mutate(false)} variant="outline">해제</Button></div>{voiceProfile.isSuccess && <p className="mt-2 text-xs text-emerald-600">음성 프로필 상태를 저장했습니다. 화자 후보는 직접 확인해 주세요.</p>}{voiceProfile.isError && <p className="mt-2 text-xs text-rose-600">{voiceProfile.error.message}</p>}</CardContent></Card>
    <Card className="mt-5 shadow-none"><CardContent><h2 className="font-bold text-slate-900">내 프로필</h2><div className="mt-4 flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><UserRound className="h-5 w-5" /></span><div className="min-w-0"><p className="font-bold text-slate-800">{me.data?.name ?? "사용자"}</p><p className="truncate text-xs text-slate-500">{me.data?.email}</p></div></div><Button className="mt-5 w-full" onClick={() => setLogoutOpen(true)} variant="danger"><LogOut className="h-4 w-4" />로그아웃</Button></CardContent></Card>
    <ConfirmDialog confirmLabel="로그아웃" description="현재 기기의 Supabase 세션을 종료합니다." onClose={() => setLogoutOpen(false)} onConfirm={() => { void signOut().then(() => navigate("/login", { replace: true })); }} open={logoutOpen} title="로그아웃할까요?" />
  </>;
}
