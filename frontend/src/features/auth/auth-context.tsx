import type { AuthError, Session, User as SupabaseUser } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { isSupabaseConfigured, supabase } from "@/lib/supabase";

interface SignupResult {
  needsEmailConfirmation: boolean;
}

interface AuthContextValue {
  session: Session | null;
  user: SupabaseUser | null;
  isLoading: boolean;
  isConfigured: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<SignupResult>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function requireClient() {
  if (!supabase) throw new Error("Supabase 환경변수가 설정되지 않았습니다.");
  return supabase;
}

function authErrorMessage(error: AuthError): string {
  const messages: Record<string, string> = {
    invalid_credentials: "이메일 또는 비밀번호가 올바르지 않습니다.",
    email_not_confirmed: "이메일 인증을 완료한 뒤 로그인해 주세요.",
    user_already_exists: "이미 가입된 이메일입니다.",
    weak_password: "더 안전한 비밀번호를 사용해 주세요.",
    over_email_send_rate_limit: "이메일 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    signup_disabled: "현재 회원가입이 비활성화되어 있습니다.",
  };
  return messages[error.code ?? ""] ?? "인증 요청을 처리하지 못했습니다. 입력값을 확인해 주세요.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!supabase) {
      setIsLoading(false);
      return;
    }
    let active = true;
    void supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      if (error) setSession(null);
      else setSession(data.session);
      setIsLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((event, nextSession) => {
      setSession(nextSession);
      setIsLoading(false);
      if (event === "SIGNED_OUT") queryClient.clear();
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(() => ({
    session,
    user: session?.user ?? null,
    isLoading,
    isConfigured: isSupabaseConfigured,
    async signIn(email, password) {
      const { error } = await requireClient().auth.signInWithPassword({ email, password });
      if (error) throw new Error(authErrorMessage(error));
    },
    async signUp(name, email, password) {
      const { data, error } = await requireClient().auth.signUp({
        email,
        password,
        options: { data: { display_name: name.trim() } },
      });
      if (error) throw new Error(authErrorMessage(error));
      return { needsEmailConfirmation: data.session === null };
    },
    async signOut() {
      const { error } = await requireClient().auth.signOut();
      if (error) throw new Error(authErrorMessage(error));
    },
  }), [isLoading, session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Context hooks intentionally share this module with the provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth는 AuthProvider 안에서 사용해야 합니다.");
  return value;
}
