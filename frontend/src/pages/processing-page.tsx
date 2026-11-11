import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Check, LoaderCircle, RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function ProcessingPage() {
  const { id = "" } = useParams();
  const [searchParams] = useSearchParams();
  const jobId = searchParams.get("job") ?? "";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const jobQuery = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => apiService.getJob(jobId),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 1500 : false;
    },
  });
  const retry = useMutation({
    mutationFn: () => apiService.retryJob(jobId),
    onSuccess: (job) => queryClient.setQueryData(queryKeys.job(jobId), job),
  });

  useEffect(() => {
    if (jobQuery.data?.status !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.meeting(id) });
    navigate(`/meetings/${id}`, { replace: true });
  }, [id, jobQuery.data?.status, navigate, queryClient]);

  if (!jobId) {
    return <><PageHeader back title="정리 상태를 찾을 수 없어요" /><p className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-700">회의록으로 돌아가 다시 정리를 시작해 주세요.</p></>;
  }

  const job = jobQuery.data;
  const failed = job?.status === "failed";
  const completed = job?.status === "succeeded";
  const title = failed
    ? "회의록을 정리하지 못했어요."
    : completed
      ? "회의록 정리가 완료됐어요!"
      : !job || job.status === "queued"
        ? "회의록을 정리할 준비를 하고 있어요."
        : "회의록을 정리하고 있어요";
  const description = failed
    ? "잠시 후 다시 시도해 주세요."
    : completed
      ? "회의록에서 정리된 내용을 확인할 수 있어요."
      : "회의 내용을 살펴보고 중요한 내용을 정리하고 있어요.";

  return <><PageHeader back title={title} description="다른 화면으로 이동해도 괜찮아요. 분석이 끝나면 회의록에서 결과를 확인할 수 있어요." />
    <Card className="mt-5 overflow-hidden">
      <div className="h-1.5 w-full bg-gradient-to-r from-indigo-500 to-violet-500" />
      <CardContent aria-live="polite" className="flex min-h-72 flex-col items-center justify-center p-6 text-center" role="status">
        <span aria-hidden="true" className={`flex h-16 w-16 items-center justify-center rounded-3xl ${failed ? "bg-rose-50 text-rose-600" : completed ? "bg-emerald-50 text-emerald-600" : "bg-indigo-50 text-indigo-600"}`}>
          {failed ? <AlertCircle className="h-8 w-8" /> : completed ? <Check className="h-8 w-8" /> : <LoaderCircle className="h-8 w-8 animate-spin" />}
        </span>
        <h2 className="mt-5 font-bold text-slate-900">{title}</h2>
        <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">{description}</p>
        {!failed && !completed && <span aria-hidden="true" className="mt-6 flex items-center gap-2"><span className="h-2 w-2 animate-pulse rounded-full bg-indigo-500" /><span className="h-2 w-2 animate-pulse rounded-full bg-violet-400 [animation-delay:150ms]" /><span className="h-2 w-2 animate-pulse rounded-full bg-indigo-300 [animation-delay:300ms]" /></span>}
      </CardContent>
    </Card>
    {jobQuery.isError && <p className="mt-4 rounded-2xl bg-rose-50 p-4 text-sm text-rose-700">{jobQuery.error.message}</p>}
    {retry.error && <p className="mt-4 rounded-2xl bg-rose-50 p-4 text-sm text-rose-700">{retry.error.message}</p>}
    <div className="mt-5 grid gap-2 sm:grid-cols-2">
      {failed && <Button disabled={!job?.retryable || retry.isPending} onClick={() => retry.mutate()}><RefreshCw className="h-4 w-4" />{retry.isPending ? "요청 중..." : "다시 시도하기"}</Button>}
      <Button asChild variant="outline"><Link to={`/meetings/${id}`}>회의록으로 돌아가기</Link></Button>
    </div>
  </>;
}
