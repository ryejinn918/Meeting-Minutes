import { Navigate, Outlet, useLocation } from "react-router-dom";

import { LoadingState } from "@/components/shared/states";
import { useAuth } from "@/features/auth/auth-context";

export function ProtectedRoute() {
  const { isLoading, session } = useAuth();
  const location = useLocation();
  if (isLoading) return <main className="min-h-dvh bg-slate-50 p-6"><LoadingState label="로그인 상태를 확인하는 중입니다" /></main>;
  if (!session) return <Navigate replace state={{ from: location.pathname }} to="/login" />;
  return <Outlet />;
}

export function GuestRoute() {
  const { isLoading, session } = useAuth();
  if (isLoading) return <main className="min-h-dvh bg-slate-50 p-6"><LoadingState label="로그인 상태를 확인하는 중입니다" /></main>;
  return session ? <Navigate replace to="/teams" /> : <Outlet />;
}
