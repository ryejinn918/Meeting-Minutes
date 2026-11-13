import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Edit3, LogOut, MailPlus, Plus, ShieldCheck, Trash2, UserRound } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { MockBanner } from "@/components/shared/mock-banner";
import { PageHeader } from "@/components/shared/page-header";
import { LoadingState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/features/auth/auth-context";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";
import type { GlossaryTerm, MeetingTemplate, MeetingType } from "@/types/api";

const TEMPLATE_SECTIONS: Record<MeetingType, Array<{ key: string; label: string }>> = {
  general: [{ key: "summary", label: "회의 개요" }, { key: "discussions", label: "주요 논의사항" }, { key: "decisions", label: "결정사항" }, { key: "action_items", label: "액션아이템" }],
  project: [{ key: "progress", label: "진행 현황" }, { key: "issues", label: "주요 이슈" }, { key: "decisions", label: "의사결정" }, { key: "action_items", label: "후속 조치" }],
  interview: [{ key: "overview", label: "인터뷰 개요" }, { key: "answers", label: "핵심 답변" }, { key: "insights", label: "주요 인사이트" }],
  workshop: [{ key: "purpose", label: "회의 목적" }, { key: "ideas", label: "제안 아이디어" }, { key: "agreements", label: "합의 내용" }, { key: "action_items", label: "향후 과제" }],
};

function QualitySettings({ teamId, canManage }: { teamId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const options = useQuery({ queryKey: queryKeys.qualityOptions(teamId), queryFn: () => apiService.getQualityOptions(teamId) });
  const [termForm, setTermForm] = useState({ id: "", term: "", preferred: "", aliases: "", description: "" });
  const [templateForm, setTemplateForm] = useState({ id: "", name: "", type: "general" as MeetingType, rules: "" });
  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.qualityOptions(teamId) });
  const saveTerm = useMutation({
    mutationFn: () => termForm.id
      ? apiService.updateGlossaryTerm(termForm.id, { term: termForm.term.trim(), preferred_term: termForm.preferred.trim(), aliases: termForm.aliases.split(",").map((item) => item.trim()).filter(Boolean), description: termForm.description.trim() })
      : apiService.createGlossaryTerm({ organization_id: null, department_id: null, team_id: teamId, term: termForm.term.trim(), preferred_term: termForm.preferred.trim(), aliases: termForm.aliases.split(",").map((item) => item.trim()).filter(Boolean), description: termForm.description.trim() }),
    onSuccess: () => { setTermForm({ id: "", term: "", preferred: "", aliases: "", description: "" }); void refresh(); },
  });
  const deleteTerm = useMutation({ mutationFn: (id: string) => apiService.deleteGlossaryTerm(id), onSuccess: () => refresh() });
  const saveTemplate = useMutation({
    mutationFn: () => templateForm.id
      ? apiService.updateTemplate(templateForm.id, { name: templateForm.name.trim(), writing_rules: templateForm.rules.trim(), sections: TEMPLATE_SECTIONS[templateForm.type] })
      : apiService.createTemplate({ organization_id: null, department_id: null, team_id: teamId, name: templateForm.name.trim(), description: "", meeting_type: templateForm.type, sections: TEMPLATE_SECTIONS[templateForm.type], writing_rules: templateForm.rules.trim(), is_default: false }),
    onSuccess: () => { setTemplateForm({ id: "", name: "", type: "general", rules: "" }); void refresh(); },
  });
  const deleteTemplate = useMutation({ mutationFn: (id: string) => apiService.deleteTemplate(id), onSuccess: () => refresh() });
  const editTerm = (item: GlossaryTerm) => setTermForm({ id: item.id, term: item.term, preferred: item.preferred_term, aliases: item.aliases.join(", "), description: item.description });
  const editTemplate = (item: MeetingTemplate) => setTemplateForm({ id: item.id, name: item.name, type: item.meeting_type, rules: item.writing_rules });

  return <section className="mt-6 space-y-5"><Card className="shadow-none"><CardContent><h2 className="font-bold text-slate-900">팀 전문 용어집</h2><p className="mt-1 text-xs leading-5 text-slate-500">선택 기능입니다. 등록한 용어가 없어도 회의록 생성은 정상 동작합니다.</p>{canManage && <div className="mt-4 grid gap-2 sm:grid-cols-2"><Input onChange={(event) => setTermForm((value) => ({ ...value, term: event.target.value }))} placeholder="전사될 수 있는 표현" value={termForm.term} /><Input onChange={(event) => setTermForm((value) => ({ ...value, preferred: event.target.value }))} placeholder="권장 표기" value={termForm.preferred} /><Input onChange={(event) => setTermForm((value) => ({ ...value, aliases: event.target.value }))} placeholder="별칭(쉼표 구분)" value={termForm.aliases} /><Input onChange={(event) => setTermForm((value) => ({ ...value, description: event.target.value }))} placeholder="설명(선택)" value={termForm.description} /><Button disabled={saveTerm.isPending || !termForm.term.trim() || !termForm.preferred.trim()} onClick={() => saveTerm.mutate()}><Plus className="h-4 w-4" />{termForm.id ? "용어 수정" : "용어 추가"}</Button>{termForm.id && <Button onClick={() => setTermForm({ id: "", term: "", preferred: "", aliases: "", description: "" })} variant="outline">취소</Button>}</div>}<div className="mt-4 space-y-2">{options.data?.glossary_terms.map((item) => <div className="flex min-w-0 items-center gap-2 rounded-xl bg-slate-50 p-3" key={item.id}><div className="min-w-0 flex-1"><p className="truncate text-sm font-bold text-slate-800">{item.term} → {item.preferred_term}</p><p className="truncate text-xs text-slate-500">{item.aliases.join(", ") || "별칭 없음"}</p></div>{canManage && <><Button aria-label="용어 수정" onClick={() => editTerm(item)} size="icon" variant="outline"><Edit3 className="h-4 w-4" /></Button><Button aria-label="용어 삭제" onClick={() => deleteTerm.mutate(item.id)} size="icon" variant="danger"><Trash2 className="h-4 w-4" /></Button></>}</div>)}</div></CardContent></Card>
  <Card className="shadow-none"><CardContent><h2 className="font-bold text-slate-900">팀 회의록 템플릿</h2><p className="mt-1 text-xs leading-5 text-slate-500">공통 기본 템플릿은 항상 제공되며, 팀 규칙이 필요할 때만 추가하세요.</p>{canManage && <div className="mt-4 grid gap-2 sm:grid-cols-2"><Input onChange={(event) => setTemplateForm((value) => ({ ...value, name: event.target.value }))} placeholder="템플릿 이름" value={templateForm.name} /><select className="min-h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm" disabled={Boolean(templateForm.id)} onChange={(event) => setTemplateForm((value) => ({ ...value, type: event.target.value as MeetingType }))} value={templateForm.type}><option value="general">일반 회의</option><option value="project">프로젝트 회의</option><option value="interview">인터뷰</option><option value="workshop">워크숍</option></select><Textarea className="sm:col-span-2" onChange={(event) => setTemplateForm((value) => ({ ...value, rules: event.target.value }))} placeholder="문체와 작성 규칙(선택)" value={templateForm.rules} /><Button disabled={saveTemplate.isPending || !templateForm.name.trim()} onClick={() => saveTemplate.mutate()}>{templateForm.id ? "템플릿 수정" : "템플릿 추가"}</Button>{templateForm.id && <Button onClick={() => setTemplateForm({ id: "", name: "", type: "general", rules: "" })} variant="outline">취소</Button>}</div>}<div className="mt-4 space-y-2">{options.data?.templates.filter((item) => !item.is_builtin).map((item) => <div className="flex items-center gap-2 rounded-xl bg-slate-50 p-3" key={item.id}><div className="min-w-0 flex-1"><p className="truncate text-sm font-bold text-slate-800">{item.name}</p><p className="text-xs text-slate-500">버전 {item.version}</p></div>{canManage && <><Button aria-label="템플릿 수정" onClick={() => editTemplate(item)} size="icon" variant="outline"><Edit3 className="h-4 w-4" /></Button><Button aria-label="템플릿 삭제" onClick={() => deleteTemplate.mutate(item.id)} size="icon" variant="danger"><Trash2 className="h-4 w-4" /></Button></>}</div>)}</div></CardContent></Card></section>;
}

export function TeamSettingsPage() {
  const { teamId = "" } = useParams(); const navigate = useNavigate(); const { signOut } = useAuth(); const [copied, setCopied] = useState(false); const [logoutOpen, setLogoutOpen] = useState(false);
  const team = useQuery({ queryKey: queryKeys.team(teamId), queryFn: () => apiService.getTeam(teamId) });
  const me = useQuery({ queryKey: queryKeys.me, queryFn: apiService.getMe });
  const canManage = ["owner", "admin"].includes(team.data?.my_role ?? "member");
  async function copyInvite() { await navigator.clipboard?.writeText("https://meetflow.example/invite/mock-only"); setCopied(true); window.setTimeout(() => setCopied(false), 1600); }
  return <><PageHeader title="팀 관리" description={`${team.data?.name ?? "팀"}의 멤버와 내 프로필을 확인하세요.`} /><MockBanner message="팀원 목록과 프로필은 실제 데이터입니다. 초대 링크 기능만 아직 Mock입니다." />
    <section className="mt-6"><div className="mb-3 flex items-center justify-between"><h2 className="font-bold text-slate-900">팀원</h2><Button disabled={!canManage} size="sm" title={canManage ? "Mock 팀원 초대" : "owner/admin만 초대할 수 있습니다"} variant="secondary"><MailPlus className="h-4 w-4" />팀원 초대</Button></div>{team.isLoading ? <LoadingState /> : <Card className="shadow-none"><div className="divide-y divide-slate-100">{team.data?.members.map((member) => <div className="flex min-w-0 items-center gap-3 p-4" key={member.id}><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${member.avatar_color ?? "bg-indigo-500"}`}>{member.name.slice(0, 1)}</span><div className="min-w-0 flex-1"><p className="flex items-center gap-1.5 text-sm font-bold text-slate-800">{member.name}{member.role !== "member" && <ShieldCheck className="h-3.5 w-3.5 text-indigo-500" />}</p><p className="truncate text-xs text-slate-500">{member.email}</p></div><span className="text-[10px] font-bold uppercase text-slate-400">{member.role}</span></div>)}</div></Card>}</section>
    <Card className="mt-5 shadow-none"><CardContent><h2 className="font-bold text-slate-900">초대 링크</h2><p className="mt-1 text-xs leading-5 text-slate-500">다음 단계에서 만료되는 실제 초대 링크와 이메일 확인을 연결합니다.</p><div className="mt-3 flex gap-2"><div className="min-w-0 flex-1 truncate rounded-xl bg-slate-100 px-3 py-3 text-xs text-slate-500">meetflow.example/invite/mock-only</div><Button aria-label="Mock 초대 링크 복사" onClick={copyInvite} size="icon" variant="outline"><Copy className="h-4 w-4" /></Button></div>{copied && <p className="mt-2 text-xs font-semibold text-emerald-600">Mock 링크를 복사했습니다. 실제 초대는 전송되지 않았습니다.</p>}</CardContent></Card>
    <QualitySettings canManage={canManage} teamId={teamId} />
    <Card className="mt-5 shadow-none"><CardContent><h2 className="font-bold text-slate-900">내 프로필</h2><div className="mt-4 flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><UserRound className="h-5 w-5" /></span><div className="min-w-0"><p className="font-bold text-slate-800">{me.data?.name ?? "사용자"}</p><p className="truncate text-xs text-slate-500">{me.data?.email}</p></div></div><Button className="mt-5 w-full" onClick={() => setLogoutOpen(true)} variant="danger"><LogOut className="h-4 w-4" />로그아웃</Button></CardContent></Card>
    <ConfirmDialog confirmLabel="로그아웃" description="현재 기기의 Supabase 세션을 종료합니다." onClose={() => setLogoutOpen(false)} onConfirm={() => { void signOut().then(() => navigate("/login", { replace: true })); }} open={logoutOpen} title="로그아웃할까요?" />
  </>;
}
