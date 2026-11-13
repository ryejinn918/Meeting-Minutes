import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function TeamNewPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [organizationId, setOrganizationId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const organizations = useQuery({
    queryKey: queryKeys.organizations,
    queryFn: apiService.getOrganizations,
    staleTime: 5 * 60_000,
  });
  const organization = useQuery({
    queryKey: queryKeys.organization(organizationId || "pending"),
    queryFn: () => apiService.getOrganization(organizationId),
    enabled: Boolean(organizationId),
    staleTime: 5 * 60_000,
  });
  const create = useMutation({
    mutationFn: () => apiService.createTeam({
      name: name.trim(),
      organization_id: organizationId || undefined,
      department_id: departmentId || undefined,
    }),
    onSuccess: (team) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.teams });
      navigate(`/t/${team.id}/meetings`);
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim().length < 2) return setError("팀 이름을 2자 이상 입력해 주세요.");
    if (organizationId && !departmentId) return setError("팀이 속할 부문을 선택해 주세요.");
    setError("");
    create.mutate();
  }

  const departments = organization.data?.departments.filter(
    (item) => item.my_role === "department_admin" || organization.data?.my_role === "org_admin",
  ) ?? [];

  return <main className="min-h-dvh bg-slate-50 px-4 py-8"><div className="mx-auto max-w-lg">
    <PageHeader back title="새 팀 만들기" description="함께 회의록을 관리할 팀 공간을 만드세요." />
    <Card className="mt-5"><CardContent><form className="space-y-4" onSubmit={submit}>
      <label className="block text-sm font-semibold text-slate-700">팀 이름<Input className="mt-2" maxLength={50} onChange={(event) => setName(event.target.value)} placeholder="예: 프로젝트 운영팀" value={name} /></label>
      <label className="block text-sm font-semibold text-slate-700">조직<select className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" onChange={(event) => { setOrganizationId(event.target.value); setDepartmentId(""); }} value={organizationId}><option value="">조직 미지정(기존 방식)</option>{organizations.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      {organizationId && <label className="block text-sm font-semibold text-slate-700">부문<select className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm" onChange={(event) => setDepartmentId(event.target.value)} value={departmentId}><option value="">부문 선택</option>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      <p className="text-xs leading-5 text-slate-500">기존 팀은 자동으로 조직에 배정되지 않습니다. 조직 범위 팀은 조직 또는 부문 관리자만 만들 수 있어요.</p>
      {(error || create.error) && <p className="text-sm text-rose-600">{error || create.error?.message}</p>}
      <Button className="w-full" disabled={create.isPending || Boolean(organizationId && !departmentId)} type="submit">{create.isPending ? "팀 생성 중..." : "팀 만들기"}</Button>
    </form></CardContent></Card>
  </div></main>;
}
