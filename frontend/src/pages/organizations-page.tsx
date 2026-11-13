import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function OrganizationsPage() {
  const queryClient = useQueryClient();
  const organizations = useQuery({
    queryKey: queryKeys.organizations,
    queryFn: apiService.getOrganizations,
    staleTime: 5 * 60_000,
  });
  const [selectedId, setSelectedId] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [departmentName, setDepartmentName] = useState("");

  useEffect(() => {
    if (!selectedId && organizations.data?.[0]) setSelectedId(organizations.data[0].id);
  }, [organizations.data, selectedId]);

  const organization = useQuery({
    queryKey: queryKeys.organization(selectedId || "pending"),
    queryFn: () => apiService.getOrganization(selectedId),
    enabled: Boolean(selectedId),
    staleTime: 5 * 60_000,
  });
  const createOrganization = useMutation({
    mutationFn: () => apiService.createOrganization(organizationName.trim()),
    onSuccess: (created) => {
      setOrganizationName("");
      setSelectedId(created.id);
      void queryClient.invalidateQueries({ queryKey: queryKeys.organizations });
    },
  });
  const createDepartment = useMutation({
    mutationFn: () => apiService.createDepartment(selectedId, departmentName.trim()),
    onSuccess: () => {
      setDepartmentName("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization(selectedId) });
    },
  });

  function submitOrganization(event: FormEvent) {
    event.preventDefault();
    if (organizationName.trim().length >= 2) createOrganization.mutate();
  }

  function submitDepartment(event: FormEvent) {
    event.preventDefault();
    if (departmentName.trim().length >= 2) createDepartment.mutate();
  }

  return <main className="min-h-dvh bg-slate-50 px-4 py-8"><div className="mx-auto max-w-2xl">
    <PageHeader back title="조직 및 부문" description="회사와 부문을 만들고 팀의 소속 범위를 관리하세요." />
    <Card className="mt-5"><CardContent><form className="flex flex-col gap-3 sm:flex-row" onSubmit={submitOrganization}>
      <label className="min-w-0 flex-1 text-sm font-semibold text-slate-700">새 조직 이름<Input className="mt-2" maxLength={100} onChange={(event) => setOrganizationName(event.target.value)} placeholder="예: 회사 또는 사업 조직" value={organizationName} /></label>
      <Button className="sm:self-end" disabled={createOrganization.isPending || organizationName.trim().length < 2} type="submit"><Plus className="h-4 w-4" />조직 만들기</Button>
    </form>{createOrganization.isError && <p className="mt-3 text-sm text-rose-600">{createOrganization.error.message}</p>}</CardContent></Card>

    {organizations.isLoading ? <LoadingState label="조직을 불러오는 중입니다" /> : organizations.isError ? <ErrorState message={organizations.error.message} onRetry={() => organizations.refetch()} /> : organizations.data?.length ? <div className="mt-5 grid gap-3 sm:grid-cols-2">{organizations.data.map((item) => <button className={`rounded-2xl border bg-white p-4 text-left transition ${selectedId === item.id ? "border-indigo-400 ring-2 ring-indigo-100" : "border-slate-200"}`} key={item.id} onClick={() => setSelectedId(item.id)} type="button"><span className="flex items-center gap-2 font-bold text-slate-900"><Building2 className="h-4 w-4 text-indigo-600" />{item.name}</span><span className="mt-2 block text-xs text-slate-500">{item.my_role === "org_admin" ? "조직 관리자" : "구성원"}</span></button>)}</div> : <div className="mt-5"><EmptyState title="등록된 조직이 없습니다" description="기존 팀과 회의록은 그대로 유지됩니다. 새 조직을 만든 뒤 부문과 팀을 연결할 수 있어요." /></div>}

    {selectedId && <Card className="mt-5 shadow-none"><CardContent>
      {organization.isLoading ? <LoadingState /> : organization.isError ? <ErrorState message={organization.error.message} onRetry={() => organization.refetch()} /> : organization.data && <>
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold text-slate-900">{organization.data.name}</h2><p className="mt-1 text-xs text-slate-500">등록된 부문 {organization.data.departments.length}개</p></div><Building2 className="h-5 w-5 text-indigo-500" /></div>
        {organization.data.departments.length ? <ul className="mt-4 space-y-2">{organization.data.departments.map((department) => <li className="rounded-xl bg-slate-50 px-4 py-3" key={department.id}><p className="text-sm font-bold text-slate-800">{department.name}</p><p className="mt-1 text-xs text-slate-500">{department.my_role === "department_admin" ? "부문 관리자" : "소속 정보 없음"}</p></li>)}</ul> : <p className="mt-4 text-sm text-slate-500">아직 등록된 부문이 없습니다.</p>}
        {organization.data.my_role === "org_admin" && <form className="mt-5 flex gap-2" onSubmit={submitDepartment}><Input aria-label="새 부문 이름" maxLength={100} onChange={(event) => setDepartmentName(event.target.value)} placeholder="새 부문 이름" value={departmentName} /><Button disabled={createDepartment.isPending || departmentName.trim().length < 2} type="submit">추가</Button></form>}
        {createDepartment.isError && <p className="mt-3 text-sm text-rose-600">{createDepartment.error.message}</p>}
      </>}
    </CardContent></Card>}
    <Button asChild className="mt-6 w-full"><Link to="/teams/new">조직·부문에 팀 만들기</Link></Button>
  </div></main>;
}
