import { CheckSquare2, Home, Plus, Users } from "lucide-react";
import { NavLink, useLocation, useParams } from "react-router-dom";
import { useEffect } from "react";

import { cn } from "@/lib/cn";

export function BottomNavigation() {
  const { teamId } = useParams();
  const location = useLocation();
  useEffect(() => {
    if (teamId) window.localStorage.setItem("meetflow.activeTeamId", teamId);
  }, [teamId]);
  const activeTeam = teamId ?? window.localStorage.getItem("meetflow.activeTeamId");
  const meetingsPath = activeTeam ? `/t/${activeTeam}/meetings` : "/teams";
  const items = [
    { to: meetingsPath, label: "회의", icon: Home },
    { to: activeTeam ? `/t/${activeTeam}/meetings/new` : "/teams", label: "새 회의", icon: Plus, primary: true },
    { to: "/actions", label: "내 액션", icon: CheckSquare2 },
    { to: activeTeam ? `/t/${activeTeam}/settings` : "/teams", label: "팀", icon: Users },
  ];
  return (
    <nav aria-label="주요 메뉴" className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:left-1/2 lg:max-w-3xl lg:-translate-x-1/2 lg:rounded-t-2xl lg:border-x">
      <div className="grid h-17 grid-cols-4 px-2">
        {items.map(({ to, label, icon: Icon, primary }) => (
          <NavLink key={`${label}-${to}`} to={to} className={({ isActive }) => cn("flex min-w-0 flex-col items-center justify-center gap-1 text-[11px] font-semibold text-slate-400", isActive && location.pathname !== "/teams" && "text-indigo-600")}>
            {({ isActive }) => <><span className={cn("flex h-8 w-10 items-center justify-center rounded-xl", isActive && "bg-indigo-50", primary && "-mt-5 h-12 w-12 rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-200")}><Icon className={cn("h-5 w-5", primary && "h-6 w-6")} /></span><span className="truncate">{label}</span></>}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
