import { currentUser, mockMembers } from "@/features/teams/mock-teams";
import type { Meeting } from "@/types/api";

const phaseBDefaults = {
  topic: "",
  location: "",
  meeting_type: "general" as const,
  purpose: "",
  project_name: "",
  template_id: null,
  metadata_confirmed_at: null,
  attendees: [],
  transcript_corrected: "",
  questions: [],
  latest_speaker_edit_batch_id: null,
};

const transcript = `김민지: 이번 주에는 로그인 화면과 팀 선택 흐름을 먼저 완성하겠습니다. 모바일 화면을 기준으로 작업하고 데스크톱에서도 자연스럽게 확장되도록 구성할게요.

이서연: 로그인 기능은 목요일까지 프론트엔드 Mock 흐름을 마무리하고, 다음 단계에서 Supabase Auth로 교체하는 것으로 하죠.

박지훈: AI 분석 API는 Provider Adapter 형태로 준비하겠습니다. API 키 없이도 UI 검증이 가능하도록 Mock 응답을 먼저 연결하겠습니다.

최유진: 모바일 UI는 375px 화면에서 카드와 하단 내비게이션을 점검하겠습니다. 공유 화면은 팀원 체크박스 방식으로 단순하게 유지하면 좋겠습니다.

김민지: 좋습니다. 이번 단계에서는 실제 저장이나 권한 검증은 하지 않고, Mock이라는 안내를 모든 관련 화면에 표시하겠습니다.`;

export const initialMeetings: Meeting[] = [
  {
    ...phaseBDefaults,
    id: "meeting-weekly-project",
    team_id: "team-ai-innovation",
    title: "주간 프로젝트 회의",
    meeting_at: "2026-11-10T09:30:00+09:00",
    created_by: currentUser,
    processing_status: "ready",
    is_mine: true,
    is_shared_with_me: false,
    summary: "MeetFlow 1단계에서는 모바일 중심 UI와 Mock 사용자 흐름을 완성하고, 실제 Supabase 및 AI 연동은 다음 단계에서 진행하기로 했습니다.",
    transcript_original: transcript,
    transcript_edited: transcript,
    transcript_speakers: [],
    transcript_segments: [],
    key_discussions: [
      { id: "discussion-1", text: "모바일 우선 레이아웃과 하단 내비게이션을 먼저 구현합니다." },
      { id: "discussion-2", text: "외부 API 없이도 전체 사용자 흐름을 확인할 수 있는 Mock 계층을 구성합니다." },
      { id: "discussion-3", text: "공유 기능은 같은 팀의 특정 멤버를 선택하는 읽기 전용 방식으로 제한합니다." },
    ],
    decisions: [
      { id: "decision-1", text: "이번 단계에서는 실제 인증, 파일 업로드 및 AI 호출을 구현하지 않습니다." },
      { id: "decision-2", text: "모든 Mock 수정은 브라우저 메모리에만 반영합니다." },
    ],
    follow_ups: [
      { id: "follow-up-1", text: "Supabase 프로젝트 생성 후 Auth와 RLS 정책을 연결합니다." },
      { id: "follow-up-2", text: "OpenAI와 OpenRouter 키 등록 후 실제 응답 품질을 검증합니다." },
    ],
    action_items: [
      { id: "action-1", description: "로그인 기능 개발", assignee_id: "user-seoyeon", assignee_name: "이서연", due_date: "2026-11-12", status: "in_progress" },
      { id: "action-2", description: "AI 분석 API 연결", assignee_id: "user-jihoon", assignee_name: "박지훈", due_date: null, status: "todo" },
      { id: "action-3", description: "모바일 UI 검토", assignee_id: "user-yujin", assignee_name: "최유진", due_date: "2026-11-13", status: "todo" },
    ],
    shared_member_ids: ["user-seoyeon", "user-jihoon"],
    ai_generated_at: "2026-11-10T10:20:00+09:00",
    version: 1,
  },
  {
    ...phaseBDefaults,
    id: "meeting-ai-schedule",
    team_id: "team-ai-innovation",
    title: "AI 서비스 개발 일정 논의",
    meeting_at: "2026-11-07T14:00:00+09:00",
    created_by: mockMembers[1],
    processing_status: "ready",
    is_mine: false,
    is_shared_with_me: true,
    summary: "AI 기능을 순차 파이프라인으로 구현하고 실제 모델 연동 전 Mock 데이터로 화면을 검증하기로 했습니다.",
    transcript_original: transcript,
    transcript_edited: transcript,
    transcript_speakers: [],
    transcript_segments: [],
    key_discussions: [{ id: "discussion-4", text: "STT와 분석 Provider를 독립적인 adapter로 구성합니다." }],
    decisions: [{ id: "decision-3", text: "초기 MVP에서는 LangGraph를 사용하지 않습니다." }],
    follow_ups: [{ id: "follow-up-3", text: "대표 한국어 회의 음성으로 전사 품질을 확인합니다." }],
    action_items: [
      { id: "action-4", description: "Provider 인터페이스 검토", assignee_id: "user-minji", assignee_name: "김민지", due_date: "2026-11-14", status: "todo" },
    ],
    shared_member_ids: ["user-minji"],
    ai_generated_at: "2026-11-07T14:45:00+09:00",
    version: 1,
  },
  {
    ...phaseBDefaults,
    id: "meeting-new-feature",
    team_id: "team-ai-innovation",
    title: "신규 기능 기획 회의",
    meeting_at: "2026-11-11T11:00:00+09:00",
    created_by: currentUser,
    processing_status: "analyzing",
    is_mine: true,
    is_shared_with_me: false,
    summary: "분석 중인 회의입니다.",
    transcript_original: transcript,
    transcript_edited: transcript,
    transcript_speakers: [],
    transcript_segments: [],
    key_discussions: [],
    decisions: [],
    follow_ups: [],
    action_items: [],
    shared_member_ids: [],
    ai_generated_at: null,
    version: 1,
  },
];
