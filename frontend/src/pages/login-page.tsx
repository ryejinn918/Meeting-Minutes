import { useMutation } from "@tanstack/react-query";
import { ArrowRight, LockKeyhole, Mail } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { Brand } from "@/components/shared/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/features/auth/auth-context";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn, isConfigured } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [validation, setValidation] = useState("");
  const login = useMutation({ mutationFn: () => signIn(email, password), onSuccess: () => navigate((location.state as { from?: string } | null)?.from ?? "/teams", { replace: true }) });
  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!email.includes("@")) return setValidation("올바른 이메일 주소를 입력해 주세요.");
    if (password.length < 6) return setValidation("비밀번호는 6자 이상 입력해 주세요.");
    setValidation(""); login.mutate();
  }
  return (
    <main className="min-h-dvh bg-gradient-to-b from-indigo-50 via-white to-white px-4 py-8 sm:flex sm:items-center">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-8 text-center"><Brand className="justify-center" /><h1 className="mt-7 text-3xl font-extrabold tracking-tight text-slate-950">회의를 실행으로 연결하세요</h1><p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-slate-500">AI가 회의 내용을 정리하고, 팀의 다음 할 일을 한곳에서 관리합니다.</p></div>
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card sm:p-7">
          {!isConfigured && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">Supabase 환경변수를 설정해야 로그인할 수 있습니다.</p>}
          <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
            <label className="block text-sm font-semibold text-slate-700">이메일<div className="relative mt-2"><Mail className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" /><Input autoComplete="email" className="pl-10" onChange={(e) => setEmail(e.target.value)} type="email" value={email} /></div></label>
            <label className="block text-sm font-semibold text-slate-700">비밀번호<div className="relative mt-2"><LockKeyhole className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" /><Input autoComplete="current-password" className="pl-10" onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></div></label>
            {(validation || login.error) && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700" role="alert">{validation || login.error?.message}</p>}
            <Button className="w-full" disabled={login.isPending || !isConfigured} type="submit">{login.isPending ? "로그인 중..." : "로그인"}<ArrowRight className="h-4 w-4" /></Button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-500">아직 계정이 없으신가요? <Link className="font-bold text-indigo-600 hover:underline" to="/signup">회원가입</Link></p>
        </div>
      </div>
    </main>
  );
}
