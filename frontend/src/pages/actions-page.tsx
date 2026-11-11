import { MockBanner } from "@/components/shared/mock-banner";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { Card, CardContent } from "@/components/ui/card";

export function ActionsPage() {
  return <><PageHeader title="내 액션아이템" description="나에게 할당된 다음 할 일을 확인하세요." /><MockBanner message="여러 회의록의 내 액션아이템을 모아보는 기능은 아직 준비 중입니다." /><div className="mt-5"><EmptyState title="내 액션아이템 모아보기 준비 중" description="현재는 각 회의록의 액션아이템 탭에서 정리된 업무를 확인할 수 있습니다." /></div><Card className="mt-6 border-dashed shadow-none"><CardContent><p className="text-center text-xs leading-5 text-slate-400">담당자별 액션아이템 조회는 다음 단계에서 연결됩니다.</p></CardContent></Card></>;
}
