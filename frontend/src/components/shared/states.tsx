import { AlertCircle, Inbox, LoaderCircle, LockKeyhole, SearchX } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function LoadingState({ label = "불러오는 중입니다" }: { label?: string }) {
  return <div className="flex min-h-48 flex-col items-center justify-center gap-3 text-sm text-slate-500"><LoaderCircle className="h-7 w-7 animate-spin text-indigo-500" /><span>{label}</span></div>;
}

export function EmptyState({ title, description, action, searched = false }: { title: string; description: string; action?: ReactNode; searched?: boolean }) {
  const Icon = searched ? SearchX : Inbox;
  return <Card className="border-dashed shadow-none"><CardContent className="flex min-h-56 flex-col items-center justify-center text-center"><span className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-500"><Icon className="h-6 w-6" /></span><h2 className="font-bold text-slate-900">{title}</h2><p className="mt-1 max-w-xs text-sm leading-6 text-slate-500">{description}</p>{action && <div className="mt-5">{action}</div>}</CardContent></Card>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <Card className="border-rose-200 bg-rose-50 shadow-none"><CardContent className="text-center"><AlertCircle className="mx-auto h-7 w-7 text-rose-600" /><p className="mt-3 text-sm font-medium text-rose-800">{message}</p>{onRetry && <Button className="mt-4" onClick={onRetry} variant="outline">다시 시도</Button>}</CardContent></Card>;
}

export function ForbiddenState() {
  return <EmptyState title="접근 권한이 없습니다" description="선택된 팀원에게만 공유된 회의록입니다. 작성자에게 공유를 요청해 주세요." action={<Button asChild><a href="/teams">팀 목록으로</a></Button>} />;
}

export function UnauthorizedState() {
  return <EmptyState title="로그인이 필요합니다" description="이 화면을 보려면 먼저 로그인해 주세요." action={<Button asChild><a href="/login">로그인하기</a></Button>} />;
}

export function NotFoundState() {
  return <EmptyState title="페이지를 찾을 수 없습니다" description="주소가 잘못되었거나 이동된 페이지입니다." action={<Button asChild><a href="/teams">홈으로 이동</a></Button>} />;
}

export function InlineSavingState({ state }: { state: "saving" | "saved" | "error" }) {
  const content = state === "saving" ? [LoaderCircle, "저장 중", "text-indigo-600"] : state === "saved" ? [CheckCircle, "저장 완료", "text-emerald-600"] : [AlertCircle, "저장 실패", "text-rose-600"];
  const Icon = content[0] as typeof LoaderCircle;
  return <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${content[2]}`}><Icon className={`h-3.5 w-3.5 ${state === "saving" ? "animate-spin" : ""}`} />{content[1] as string}</span>;
}

function CheckCircle(props: React.ComponentProps<typeof LoaderCircle>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}><path d="M20 6 9 17l-5-5" /></svg>;
}

export function SecurityNote({ children }: { children: ReactNode }) {
  return <div className="flex items-start gap-2 rounded-xl bg-slate-100 p-3 text-xs leading-5 text-slate-600"><LockKeyhole className="mt-0.5 h-4 w-4 shrink-0" />{children}</div>;
}
