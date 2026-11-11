import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Brand } from "@/components/shared/brand";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/features/auth/auth-context";

export function SignupPage() {
  const navigate = useNavigate();
  const { signUp, isConfigured } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [validation, setValidation] = useState("");
  const [confirmationSent, setConfirmationSent] = useState(false);
  const signup = useMutation({
    mutationFn: () => signUp(form.name, form.email, form.password),
    onSuccess: ({ needsEmailConfirmation }) => {
      if (needsEmailConfirmation) setConfirmationSent(true);
      else navigate("/teams", { replace: true });
    },
  });
  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) return setValidation("이름을 입력해 주세요.");
    if (!form.email.includes("@")) return setValidation("올바른 이메일 주소를 입력해 주세요.");
    if (form.password.length < 8) return setValidation("비밀번호는 8자 이상 입력해 주세요.");
    if (form.password !== form.confirm) return setValidation("비밀번호가 일치하지 않습니다.");
    setValidation(""); signup.mutate();
  }
  const update = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }));
  return (
    <main className="min-h-dvh bg-gradient-to-b from-violet-50 via-white to-white px-4 py-8">
      <div className="mx-auto w-full max-w-md"><Brand /><h1 className="mt-8 text-3xl font-extrabold text-slate-950">MeetFlow 시작하기</h1><p className="mt-2 text-sm text-slate-500">팀의 회의를 더 명확한 실행 계획으로 바꿔보세요.</p>
        <div className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-card sm:p-7">
          {!isConfigured && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">Supabase 환경변수를 설정해야 가입할 수 있습니다.</p>}
          {confirmationSent && <p className="rounded-xl bg-emerald-50 p-3 text-sm leading-6 text-emerald-800">확인 이메일을 보냈습니다. 이메일 인증 후 로그인해 주세요.</p>}
          <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
            <label className="block text-sm font-semibold text-slate-700">이름<Input className="mt-2" onChange={(e) => update("name", e.target.value)} placeholder="김민지" value={form.name} /></label>
            <label className="block text-sm font-semibold text-slate-700">이메일<Input className="mt-2" onChange={(e) => update("email", e.target.value)} placeholder="name@company.com" type="email" value={form.email} /></label>
            <label className="block text-sm font-semibold text-slate-700">비밀번호<Input className="mt-2" onChange={(e) => update("password", e.target.value)} placeholder="8자 이상" type="password" value={form.password} /></label>
            <label className="block text-sm font-semibold text-slate-700">비밀번호 확인<Input className="mt-2" onChange={(e) => update("confirm", e.target.value)} type="password" value={form.confirm} /></label>
            {(validation || signup.error) && <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700" role="alert">{validation || signup.error?.message}</p>}
            <Button className="w-full" disabled={signup.isPending || !isConfigured || confirmationSent} type="submit">{signup.isPending ? "처리 중..." : "계정 만들기"}</Button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-500">이미 계정이 있나요? <Link className="font-bold text-indigo-600" to="/login">로그인</Link></p>
        </div>
      </div>
    </main>
  );
}
