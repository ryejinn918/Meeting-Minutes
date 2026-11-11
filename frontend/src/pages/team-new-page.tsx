import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function TeamNewPage() {
  const navigate = useNavigate(); const queryClient = useQueryClient(); const [name, setName] = useState(""); const [error, setError] = useState("");
  const create = useMutation({ mutationFn: () => apiService.createTeam(name.trim()), onSuccess: (team) => { void queryClient.invalidateQueries({ queryKey: queryKeys.teams }); navigate(`/t/${team.id}/meetings`); } });
  function submit(event: FormEvent) { event.preventDefault(); if (name.trim().length < 2) return setError("팀 이름을 2자 이상 입력해 주세요."); setError(""); create.mutate(); }
  return <main className="min-h-dvh bg-slate-50 px-4 py-8"><div className="mx-auto max-w-lg"><PageHeader back title="새 팀 만들기" description="함께 회의록을 관리할 팀 공간을 만드세요." /><Card className="mt-5"><CardContent><form onSubmit={submit}><label className="text-sm font-semibold text-slate-700">팀 이름<Input className="mt-2" maxLength={50} onChange={(e) => setName(e.target.value)} placeholder="예: AI Innovation Team" value={name} /></label>{(error || create.error) && <p className="mt-3 text-sm text-rose-600">{error || create.error?.message}</p>}<Button className="mt-6 w-full" disabled={create.isPending} type="submit">{create.isPending ? "팀 생성 중..." : "팀 만들기"}</Button></form></CardContent></Card></div></main>;
}
