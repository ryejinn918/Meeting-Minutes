import { FlaskConical } from "lucide-react";

export function MockBanner({ message = "개발용 Mock 모드입니다. 변경사항은 서버에 저장되지 않으며 새로고침하면 초기화될 수 있습니다." }: { message?: string }) {
  return (
    <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-800" role="note">
      <FlaskConical aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

