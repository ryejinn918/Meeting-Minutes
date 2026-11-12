import { CalendarDays, ChevronRight, LockKeyhole, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatMeetingDate } from "@/lib/format";
import { apiService } from "@/lib/api-service";
import { queryKeys } from "@/lib/query-keys";
import type { MeetingListItem } from "@/types/api";

export function MeetingCard({ meeting }: { meeting: MeetingListItem }) {
  const queryClient = useQueryClient();
  const prefetchDetail = () => {
    void queryClient.prefetchQuery({
      queryKey: queryKeys.meeting(meeting.id),
      queryFn: () => apiService.getMeeting(meeting.id),
      staleTime: 2 * 60_000,
    });
  };
  return (
    <Link className="group block rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2" onFocus={prefetchDetail} onPointerEnter={prefetchDetail} onTouchStart={prefetchDetail} to={`/meetings/${meeting.id}`}>
      <Card className="transition group-hover:-translate-y-0.5 group-hover:border-indigo-200 group-hover:shadow-lg">
        <CardContent>
          <div className="flex min-w-0 items-start gap-3">
            <div className="min-w-0 flex-1">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <StatusBadge status={meeting.processing_status} />
                {meeting.is_mine ? <Badge className="bg-slate-100 text-slate-600">내가 작성</Badge> : <Badge className="bg-violet-50 text-violet-700"><LockKeyhole className="h-3 w-3" />공유받음</Badge>}
              </div>
              <h2 className="break-words text-base font-bold leading-6 text-slate-950">{meeting.title}</h2>
              <div className="mt-3 space-y-1.5 text-xs text-slate-500">
                <p className="flex items-center gap-1.5"><CalendarDays className="h-3.5 w-3.5" />{formatMeetingDate(meeting.meeting_at)}</p>
                <p className="flex items-center gap-1.5"><UserRound className="h-3.5 w-3.5" />{meeting.created_by.name}</p>
              </div>
            </div>
            <ChevronRight className="mt-1 h-5 w-5 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-indigo-500" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
import { useQueryClient } from "@tanstack/react-query";
