import { Bell } from "lucide-react";
import { Outlet } from "react-router-dom";

import { BottomNavigation } from "@/components/shared/bottom-navigation";
import { Brand } from "@/components/shared/brand";
import { Button } from "@/components/ui/button";

export function AppLayout() {
  return (
    <div className="min-h-dvh bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
          <Brand />
          <Button aria-label="알림 (Mock)" size="icon" variant="ghost"><Bell className="h-5 w-5" /></Button>
        </div>
      </header>
      <main className="mx-auto min-w-0 max-w-3xl px-4 pb-28 pt-6 sm:px-6 sm:pt-8"><Outlet /></main>
      <BottomNavigation />
    </div>
  );
}

