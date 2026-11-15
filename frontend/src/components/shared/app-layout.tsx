import { Bell, Check, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";

import { BottomNavigation } from "@/components/shared/bottom-navigation";
import { Brand } from "@/components/shared/brand";
import { Button } from "@/components/ui/button";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";

export function AppLayout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const notifications = useQuery({ queryKey: queryKeys.notifications, queryFn: apiService.getNotifications, refetchInterval: 30000 });
  const accept = useMutation({ mutationFn: apiService.acceptNotification, onSuccess: async ({ team_id }) => { await queryClient.invalidateQueries({ queryKey: queryKeys.notifications }); await queryClient.invalidateQueries({ queryKey: queryKeys.teams }); if (team_id) navigate(`/t/${team_id}/meetings`); } });
  const decline = useMutation({ mutationFn: apiService.declineNotification, onSuccess: () => { void queryClient.invalidateQueries({ queryKey: queryKeys.notifications }); } });
  const unread = notifications.data?.filter((item) => !item.read_at).length ?? 0;
  return (
    <div className="min-h-dvh bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
          <Brand />
          <div className="relative"><Button aria-label="알림" onClick={() => setOpen((value) => !value)} size="icon" variant="ghost"><Bell className="h-5 w-5" />{unread > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">{unread}</span>}</Button>{open && <div className="absolute right-0 top-12 z-50 w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 bg-white p-3 shadow-xl"><p className="px-2 pb-2 text-sm font-bold text-slate-800">알림</p>{notifications.isLoading ? <p className="px-2 py-4 text-xs text-slate-500">알림을 불러오는 중이에요.</p> : notifications.data?.filter((item) => !item.read_at).length ? <div className="space-y-2">{notifications.data.filter((item) => !item.read_at).map((item) => <div className="rounded-xl bg-slate-50 p-3" key={item.id}><p className="text-sm font-semibold text-slate-800">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.body}</p><div className="mt-2 flex gap-2"><Button className="flex-1" disabled={accept.isPending} onClick={() => accept.mutate(item.id)} size="sm"><Check className="h-3.5 w-3.5" />수락</Button><Button onClick={() => decline.mutate(item.id)} size="sm" variant="outline"><X className="h-3.5 w-3.5" />거절</Button></div></div>)}</div> : <p className="px-2 py-4 text-xs text-slate-500">새 알림이 없어요.</p>}</div>}</div>
        </div>
      </header>
      <main className="mx-auto min-w-0 max-w-3xl px-4 pb-28 pt-6 sm:px-6 sm:pt-8"><Outlet /></main>
      <BottomNavigation />
    </div>
  );
}
