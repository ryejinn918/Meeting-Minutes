# MeetFlow 시스템 아키텍처

> 상태: 3-B단계 Private Storage 및 대용량 분할 STT 구현 기준선
> 최종 갱신: 2026-11-12
> 목표: 1인 + AI 코딩 도구로 2일 안에 검증 가능한 모바일 PWA MVP 완성

## 0. 범위와 전제

저장소에는 Supabase Auth/PostgreSQL, 직접 입력 회의록, OpenRouter 분석과 3-B 파일 수집 코드가 구현되어 있다. `202611120001_file_ingestion.sql`은 저장소에만 작성되어 있으며 승인 전 원격 DB에는 적용하지 않는다. 팀원 초대·공유와 배포는 후속 단계다.

MVP는 업로드된 TXT/PDF/음성 또는 직접 입력한 전문을 저장하고, 음성은 STT로 변환한 다음 LLM 한 번으로 요약·논의·결정·액션아이템·후속 논의를 구조화한다. 결과는 사용자가 수정하고, 같은 팀의 선택된 사용자에게만 공유하며, TXT/PDF로 내보낼 수 있다.

MVP에서 제외한다.

- 실시간 녹음/실시간 자막, 캘린더·Slack 연동, 댓글, 알림 센터
- 다중 조직/SSO/복잡한 RBAC, 공개 링크 공유
- LangGraph, 벡터 검색, 별도 AI 에이전트 서버
- 완전한 화자 식별, 자동 이메일 발송, 오프라인 편집 동기화

## 1. 전체 시스템 아키텍처

```text
React/Vite PWA (Vercel)
  ├─ Supabase Auth: 이메일 가입/로그인, 세션 갱신
  ├─ FastAPI 호출: Authorization: Bearer <Supabase access token>
  └─ 제한적 Storage 업로드: FastAPI가 발급한 signed upload URL만 사용
                 │
                 ▼
FastAPI (Render, 단일 API 서비스)
  ├─ Auth dependency: 비대칭 JWT는 JWKS로 signature/iss/aud/exp 검증, legacy HS256은 Auth /user로 검증
  ├─ Authorization service: 팀 멤버십 + 회의 소유/공유 권한 재검사
  ├─ Meeting/Team/Export API
  ├─ 순차 AI pipeline
  │    1) 파일 추출 또는 OpenAI STT
  │    2) 정규화된 transcript 저장
  │    3) OpenRouter/DeepSeek 구조화 분석
  │    4) Pydantic 검증 및 편집본 생성
  └─ Provider adapters: STTProvider, AnalysisProvider
        │                    │
        ▼                    ▼
Supabase                 외부 AI
  ├─ PostgreSQL + RLS      ├─ OpenAI Audio Transcriptions
  ├─ Private Storage       └─ OpenRouter / DeepSeek
  └─ Auth
```

### 1.1 요청 신뢰 경계

1. 프론트엔드는 Supabase Auth 세션의 access token만 FastAPI에 전달한다.
2. FastAPI는 `user_id`, `created_by`, Storage 경로, 팀 역할을 요청 본문에서 인증 근거로 받지 않는다. 검증된 JWT의 `sub`와 DB 조회 결과로 결정한다.
3. 일반 데이터 접근은 사용자 JWT가 반영된 Supabase 클라이언트를 사용해 RLS를 통과시키고, 백그라운드 처리처럼 서버 비밀키가 필요한 경로는 동일한 권한 검사를 먼저 수행한다.
4. Supabase secret/service-role key, OpenAI key, OpenRouter key는 백엔드에만 둔다. Vite의 `VITE_*` 변수에는 publishable key만 둔다.
5. 원본 파일 버킷은 private이다. 경로는 `team_id/meeting_id/file_id/sanitized-name`으로 서버가 만들며, 다운로드 URL은 권한 확인 후 짧은 만료 시간으로 발급한다.

### 1.2 비동기 처리 전략

MVP는 별도 큐를 추가하지 않고 FastAPI의 프로세스 내 background task를 사용하되 `processing_jobs`를 영속 상태 원장으로 둔다. API는 생성 직후 `202 Accepted`와 `job_id`를 반환하고 UI는 상태를 폴링한다. Render 재시작 시 실행 중 작업이 유실될 수 있으므로 `processing` 장기 체류 작업을 `failed/retryable`로 복구하고 사용자가 재시도할 수 있게 한다. 이 방식은 MVP 타협이며, 다중 인스턴스 또는 신뢰성 요구가 생기면 별도 worker + managed queue로 교체한다.

동일 회의·단계에는 활성 작업이 하나만 존재하도록 부분 unique index 또는 원자적 상태 전이로 중복 실행을 막는다. 외부 호출 전후로 상태를 저장하고, 재시도는 지수 backoff를 적용한 최대 2회로 제한한다.

Render Free 배포에서도 프로세스 내부 `BackgroundTasks`는 서버 재시작을 견디는 durable queue가 아니다. 실패 작업뿐 아니라 설정된 stale 시간보다 오래된 queued/processing 작업을 사용자가 재시도할 수 있게 하며, 이미 현재 notes가 연결된 ready 회의는 worker 재실행 시 결과를 중복 생성하지 않는다. 원본 파일과 transcript는 먼저 영속 저장하므로 task 중단으로 삭제하지 않는다. 처리 URL을 잃은 작업의 자동 재개와 다중 테이블 exactly-once 저장은 아직 보장하지 않으며, 자세한 운영 한계는 `docs/deployment.md`를 따른다.

백그라운드 작업은 요청 사용자의 회의 관리 권한을 사용자 JWT로 먼저 검사한 뒤 서버 secret key를 사용한다. 최신 `sb_secret_...` 키는 JWT가 아니므로 PostgREST의 `apikey` 헤더에만 넣고, legacy service-role JWT일 때만 `Authorization: Bearer`를 사용한다. RLS 우회 여부와 별개로 PostgreSQL GRANT가 필요하므로 `202611110002_ai_worker_grants.sql`에서 분석에 필요한 테이블의 최소 권한만 `service_role`에 부여한다.

## 2. 추천 폴더 구조

```text
/
├─ AGENTS.md
├─ README.md
├─ .gitignore
├─ docs/
│  └─ architecture.md
├─ frontend/
│  ├─ public/
│  │  ├─ icons/
│  │  └─ manifest.webmanifest
│  ├─ src/
│  │  ├─ app/                 # router, providers, query client
│  │  ├─ components/
│  │  │  ├─ ui/               # shadcn/ui 생성물
│  │  │  └─ shared/
│  │  ├─ features/
│  │  │  ├─ auth/
│  │  │  ├─ teams/
│  │  │  ├─ meetings/
│  │  │  ├─ action-items/
│  │  │  └─ sharing/
│  │  ├─ hooks/
│  │  ├─ lib/                 # api client, Supabase client, formatters
│  │  ├─ pages/
│  │  ├─ types/               # API DTO; 가능하면 OpenAPI로 생성
│  │  ├─ styles/
│  │  └─ main.tsx
│  ├─ components.json
│  ├─ package.json
│  ├─ tailwind.config.ts
│  ├─ tsconfig.json
│  └─ vite.config.ts
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  │  ├─ deps.py
│  │  │  └─ routes/           # teams, meetings, files, jobs, exports
│  │  ├─ core/                # settings, security, errors, logging
│  │  ├─ db/                  # Supabase clients/repositories
│  │  ├─ models/              # 내부 domain model
│  │  ├─ schemas/             # Pydantic request/response/AI schema
│  │  ├─ services/            # authorization, meeting, export
│  │  └─ ai/
│  │     ├─ pipeline.py
│  │     ├─ prompts.py
│  │     ├─ retry.py
│  │     ├─ stt/
│  │     │  ├─ base.py
│  │     │  └─ openai_provider.py
│  │     └─ analysis/
│  │        ├─ base.py
│  │        └─ openrouter_provider.py
│  ├─ tests/
│  │  ├─ unit/
│  │  └─ integration/
│  ├─ pyproject.toml
│  └─ .env.example
├─ supabase/
│  ├─ config.toml
│  ├─ migrations/
│  ├─ seed.sql
│  └─ tests/                  # pgTAP RLS 허용/거부 테스트
└─ .github/workflows/ci.yml
```

기능 코드는 feature 또는 service 단위로 한 곳에 둔다. `utils`에 핵심 도메인 로직을 숨기지 않으며, 프론트엔드가 DB 테이블 구조에 직접 결합되지 않도록 FastAPI DTO를 기준으로 한다. Auth 세션 처리만 Supabase JS를 직접 사용한다.

## 3. 데이터베이스 테이블 설계

모든 애플리케이션 테이블은 `uuid` PK, `created_at timestamptz`, 필요한 경우 `updated_at timestamptz`를 가진다. timestamp는 UTC 저장·로컬 표시를 원칙으로 한다. 이메일은 초대 전달에만 쓰고 사용자 식별/권한 판정에는 UUID를 쓴다.

### 3.1 핵심 테이블

| 테이블 | 주요 컬럼 | 제약/목적 |
|---|---|---|
| `profiles` | `id` FK → `auth.users`, `display_name`, `email`, `avatar_url` | 가입 시 trigger로 생성. 팀원 UI용 이메일 cache이며 권한 식별에는 UUID만 사용; Auth 이메일 변경 trigger로 동기화 |
| `teams` | `id`, `name`, `created_by` | 생성자는 아래 membership의 `owner` |
| `team_members` | `team_id`, `user_id`, `role`, `status`, `joined_at` | PK `(team_id,user_id)`; role=`owner/admin/member`, status=`active/removed` |
| `team_invitations` | `team_id`, `email_normalized`, `role`, `token_hash`, `expires_at`, `accepted_at`, `invited_by` | 원문 토큰 저장 금지. 같은 팀·이메일의 활성 초대 unique |
| `meetings` | `id`, `team_id`, `title`, `meeting_at`, `source_type`, `created_by`, `processing_status`, `current_transcript_id`, `current_notes_id`, `version` | status=`draft/uploaded/transcribing/analyzing/ready/failed`; optimistic lock용 `version` |
| `meeting_files` | `id`, `meeting_id`, `storage_bucket`, `storage_path`, `original_name`, `mime_type`, `size_bytes`, `sha256`, `uploaded_by` | Storage 경로는 서버 생성. 한 회의에 원본 여러 개 허용 가능하되 MVP UI는 1개 |
| `meeting_transcripts` | `id`, `meeting_id`, `source`, `original_text`, `edited_text`, `language`, `stt_provider`, `stt_model`, `created_by` | AI/STT 원문은 `original_text`에 불변 보존, 사용자 수정은 `edited_text` |
| `transcript_speakers` | `id`, `transcript_id`, `meeting_id`, `speaker_key`, `provider_label`, `display_name` | 조각 범위의 provider 화자 ID와 사용자가 수정 가능한 표시명을 분리. 서로 다른 조각의 화자를 자동 병합하지 않음 |
| `transcript_segments` | `id`, `transcript_id`, `meeting_id`, `speaker_id`, `segment_index`, `start_seconds`, `end_seconds`, `original_text` | provider가 반환한 발화 순서·시작/종료 시각·원문을 불변 저장 |
| `meeting_ai_runs` | `id`, `meeting_id`, `transcript_id`, `provider`, `model`, `prompt_version`, `schema_version`, `validated_output jsonb`, `usage jsonb`, `error_code`, `completed_at` | AI가 만든 검증 결과와 메타데이터의 이력. 사용자 편집으로 덮어쓰지 않음 |
| `meeting_notes` | `id`, `meeting_id`, `derived_from_run_id`, `summary`, `key_discussions jsonb`, `decisions jsonb`, `follow_ups jsonb`, `updated_by` | 현재 사용자 편집본. 배열 원소는 `{id,text,evidence?}` 형태 |
| `action_items` | `id`, `meeting_id`, `source_run_id`, `description`, `assignee_id`, `assignee_text`, `due_date`, `status`, `evidence`, `sort_order`, `updated_by` | status=`todo/in_progress/done`; 불명확한 담당자/기한은 null. 팀원과 매칭 실패 시 `assignee_text`만 보존 |
| `meeting_shares` | `meeting_id`, `user_id`, `shared_by`, `can_edit` | PK `(meeting_id,user_id)`. MVP는 `can_edit=false` 고정 권장; 생성자와 팀 owner/admin은 별도 권한 |
| `processing_jobs` | `id`, `meeting_id`, `job_type`, `status`, `attempt_count`, `error_code`, `error_message_safe`, `started_at`, `finished_at` | job type=`extract/transcribe/analyze`; status=`queued/processing/succeeded/failed` |
| `processing_job_chunks` | `job_id`, `chunk_index`, `chunk_sha256`, `start_seconds`, `end_seconds`, `transcript_text`, `segments jsonb`, `usage jsonb` | 대용량 STT 구간 checkpoint. authenticated 직접 접근 권한 없이 서버 worker만 사용 |

`meeting_notes`의 JSON 배열에는 단순한 구조화 목록만 두고, 상태·담당자·기한을 갱신하는 액션아이템은 행 단위 권한/갱신이 필요한 별도 테이블로 둔다. `meeting_ai_runs.validated_output`은 감사 및 재생성 비교용 원본이고, `meeting_notes`와 `action_items`가 편집 가능한 현재 상태다.

### 3.2 인덱스와 무결성

- `team_members(user_id, status)`, `meetings(team_id, created_at desc)`, `meeting_shares(user_id, meeting_id)` 인덱스
- `processing_jobs(meeting_id, created_at desc)`와 활성 작업 중복 방지 인덱스
- `action_items(meeting_id, status, sort_order)` 인덱스
- `storage_path` unique, `size_bytes > 0`, `due_date`는 nullable
- `meetings.current_*_id`가 같은 meeting을 가리키는지는 trigger 또는 service transaction으로 보장
- 회의 삭제는 MVP에서 soft delete(`deleted_at`)로 처리하고 Storage 정리는 별도 관리 작업으로 수행

### 3.3 권한 모델과 RLS

회의 공유 정책은 다음으로 확정한다. 작성자는 같은 팀의 멤버를 체크박스로 선택해 공유 대상을 추가하거나 제거한다. 선택된 일반 멤버만 자신의 목록과 직접 URL에서 회의록을 볼 수 있고 TXT/PDF를 다운로드할 수 있으며, MVP에서는 읽기 전용이다. 선택되지 않은 일반 멤버는 목록과 직접 URL 접근이 모두 차단된다. 팀 owner/admin의 관리 권한은 아래 표를 유지한다. 1단계 UI는 이 흐름을 Mock으로만 시연하며 실제 접근 제한을 제공하지 않는다.

| 대상 | 조회 | 생성/수정 | 삭제/관리 |
|---|---|---|---|
| 팀 | active member | owner/admin(팀 정보), 본인 membership 제한 | owner |
| 회의 목록/상세 | 생성자, owner/admin, 또는 `meeting_shares`에 포함된 active member | 생성자 또는 owner/admin; 공유 사용자는 MVP read-only | 생성자 또는 owner/admin |
| 액션아이템 | 회의 조회 가능자 | 회의 편집 가능자 | 회의 편집 가능자 |
| 파일 | 회의 조회 가능자 | 회의 생성자/owner/admin | 회의 생성자/owner/admin |
| 초대 | owner/admin | owner/admin | owner/admin |

RLS는 모든 public 테이블과 `storage.objects`에 활성화한다. 정책은 `auth.uid() is not null`을 명시하고, 사용자가 수정 가능한 `raw_user_meta_data`를 권한 근거로 사용하지 않는다. 팀 멤버십 확인 helper는 노출되지 않는 `private` schema에 두고, 고정 `search_path`를 가진 최소 권한 `security definer` 함수로 구성하며 실행 권한을 제한한다. `storage.objects` 정책은 private bucket 이름과 첫 경로 segment인 `team_id`의 active membership을 모두 확인한다.

FastAPI가 secret/service-role key를 사용할 때 RLS가 우회된다는 점을 전제로 모든 repository 진입 전에 `AuthorizationService.require_*()`를 호출한다. 권한 함수와 RLS의 의미가 달라지지 않도록 동일한 허용/거부 케이스를 통합 테스트한다.

## 4. AI 처리 파이프라인 설계

### 4.1 순차 흐름

```text
입력 검증 → 원본 보존 → 텍스트 확보 → transcript 저장
         → LLM 구조화 분석 → Pydantic 검증 → AI run 불변 저장
         → 편집 가능한 notes/action_items 생성 → ready
```

1. **입력/권한 검증**: 회의 편집 권한, 파일 레코드, MIME magic bytes, 크기, 확장자 allowlist를 확인한다.
2. **원본 보존**: 직접 입력은 곧바로 transcript 원본에, 파일은 private Storage에 보존한다. 이후 단계 실패로 삭제하지 않는다.
3. **전문 생성**:
   - 직접 입력/TXT: UTF-8 디코딩, BOM·개행 정규화
   - PDF: 텍스트 기반 PDF만 추출. 스캔 OCR은 MVP 제외이며 명확한 오류 제공
   - 음성: OpenAI adapter가 `gpt-4o-transcribe-diarize`, `response_format=diarized_json`, `chunking_strategy=auto`로 호출한다. 반환된 발화의 speaker/start/end/text만 저장하며 실제 인물과 자동 연결하지 않는다. 이 모델은 2027-02-26 지원 종료 예정이므로 adapter와 환경변수 교체 지점을 유지한다.
4. **분석**: transcript만 OpenRouter adapter에 전달한다. 2026-11-11 카탈로그 확인 기준 `deepseek/deepseek-v3.2`는 structured outputs(`response_format`)을 지원하며 이를 배포 환경의 `OPENROUTER_ANALYSIS_MODEL`에 pin한다. 모델 ID는 코드에 고정하지 않고 환경변수로 유지하며 배포 전 가용성·가격·context limit을 다시 확인한다.
5. **검증**: provider의 JSON schema/structured output을 사용하더라도 최종 경계는 Pydantic 모델이다. 실패 시 schema 오류를 포함한 짧은 repair prompt로 1회, 일시 오류에 1회까지만 재시도한다.
6. **저장**: 검증된 AI 출력은 `meeting_ai_runs`에 불변 저장하고, 별도 transaction으로 `meeting_notes`/`action_items` 편집본을 만든다.
7. **상태/오류**: 각 단계 전후에 meeting/job 상태를 기록한다. UI에는 안전한 오류 코드와 재시도 행동만 노출하고 provider 원문 오류/키/본문은 로그에 남기지 않는다.

OpenAI 공식 파일 전사 문서상 단일 요청 파일 제한은 25MB다. 원본은 Private Storage에 보존하고 서버는 전체 파일을 메모리에 올리지 않은 채 임시 파일로 스트리밍한다. 20MB를 넘는 음성은 FFmpeg로 mono 16kHz/48kbps MP3, 기본 10분 구간과 2초 중첩으로 변환한다. 각 조각은 20MB 이하인지 다시 검사해 순서대로 전사하고, 정확히 일치하는 경계 단어만 보수적으로 제거한다. 구간 결과는 `processing_job_chunks`에 저장해 서버 재시작 후 같은 job 재시도에서 완료 구간을 재호출하지 않는다. 기본 최대 길이는 4시간(24구간)이다. 참고: [OpenAI File transcription](https://developers.openai.com/api/docs/guides/speech-to-text).

Supabase Free의 공식 Storage 파일 상한은 50MB이므로 기본 배포값은 50MiB다. 애플리케이션과 DB의 절대 하드캡은 100MiB이며, 100MiB를 사용하려면 Supabase 유료 플랜의 global/bucket limit과 프론트·백엔드 환경변수를 함께 올려야 한다. 6MB 초과 브라우저 업로드는 resumable TUS를 사용한다. 참고: [Supabase Storage file limits](https://supabase.com/docs/guides/storage/uploads/file-limits), [Resumable uploads](https://supabase.com/docs/guides/storage/uploads/resumable-uploads).

파일은 서버가 `team_id/meeting_id/file_id/source.ext` 경로와 `meeting_files` 행을 만든 뒤 Supabase signed upload token으로 private bucket에 올린다. complete 요청에서 서버가 원본을 다시 읽어 크기, SHA-256, MIME/확장자와 magic bytes를 검증한 경우에만 `extract` 또는 `transcribe` job을 생성한다. 잘못된 object는 삭제하고, 업로드 후 complete가 호출되지 않은 stale object는 후속 정리 작업 대상으로 기록한다.

### 4.2 Provider Adapter 계약

```python
class STTProvider(Protocol):
    async def transcribe(self, file: BinaryIO, *, filename: str) -> TranscriptResult: ...

class AnalysisProvider(Protocol):
    async def analyze(self, transcript: str) -> MeetingAnalysis: ...
```

adapter 밖의 pipeline은 SDK 응답 타입을 알지 못한다. 결과 모델에는 provider/model/usage/request id를 선택적으로 포함하고, provider 예외는 `AIProviderError(code, retryable, safe_message)`로 변환한다. Mock adapter는 명시적인 `AI_MODE=mock`에서만 사용하며 응답과 UI에 mock 상태를 표시한다. 운영 환경에서는 mock 시작을 거부한다.

### 4.3 구조화 출력 스키마

```text
MeetingAnalysis
├─ summary: str
├─ key_discussions: list[{text, evidence?}]
├─ decisions: list[{text, evidence?}]
├─ action_items: list[{
│    description: str,
│    assignee_name: str | null,
│    due_date: date | null,
│    status: "todo",
│    evidence: str | null
│  }]
└─ follow_ups: list[{text, evidence?}]
```

system prompt에는 다음을 고정한다: 원문 외 사실 금지, 제안/추정을 결정으로 승격 금지, 불명확한 담당자·기한은 null, 날짜 기준이 불충분한 상대 날짜도 null, 원문 언어 유지, 빈 항목은 빈 배열. evidence는 원문의 짧은 근거이며 UI 검증용이지 숨은 추론이 아니다. transcript가 모델 context를 넘으면 무조건 잘라내지 말고 사용자에게 길이 오류를 반환한다. map-reduce 요약은 후속 기능이다.

## 5. FastAPI Endpoint 설계

기본 prefix는 `/api/v1`이다. 모든 보호 endpoint는 Bearer token이 필요하며 오류 형식은 `{ "error": { "code", "message", "details?", "request_id" } }`로 통일한다. 목록은 cursor pagination을 사용한다.

### 5.1 인증/팀

| Method | Path | 목적/응답 |
|---|---|---|
| `GET` | `/health` | 비인증 liveness; 비밀/DB 내용 미노출 |
| `GET` | `/me` | 검증된 사용자 profile 및 팀 목록 |
| `POST` | `/teams` | 팀 생성; 요청에는 `name`만 포함 |
| `GET` | `/teams/{team_id}` | 팀 및 active members |
| `POST` | `/teams/{team_id}/invitations` | owner/admin이 이메일 초대 생성; 개발 환경은 accept URL 반환 가능 |
| `POST` | `/invitations/{token}/accept` | token hash/만료/로그인 이메일 확인 후 membership 생성 |
| `DELETE` | `/teams/{team_id}/members/{member_id}` | owner/admin; 마지막 owner 제거 금지 |

이메일 가입/로그인/비밀번호 재설정은 FastAPI가 재구현하지 않고 Supabase Auth SDK를 사용한다.

### 5.2 회의/파일/처리

| Method | Path | 목적/응답 |
|---|---|---|
| `GET` | `/meetings?team_id=&cursor=&status=` | 접근 가능한 회의 카드 목록 |
| `POST` | `/meetings` | draft 생성; title, team_id, meeting_at, source_type |
| `GET` | `/meetings/{meeting_id}` | transcript/notes/actions/share 대상 포함 상세 |
| `PATCH` | `/meetings/{meeting_id}` | 제목/일시 수정; `version`으로 충돌 감지 |
| `DELETE` | `/meetings/{meeting_id}` | soft delete |
| `POST` | `/meetings/{meeting_id}/transcript` | 직접 입력 원문 생성 또는 edited_text 수정 |
| `POST` | `/meetings/{meeting_id}/files/upload-url` | MIME/size/name 검증 후 1회성 signed upload URL + file_id 반환 |
| `POST` | `/meetings/{meeting_id}/files/{file_id}/complete` | 실제 object metadata 검증 후 업로드 확정 |
| `GET` | `/meetings/{meeting_id}/files` | 권한이 있는 사용자의 파일 메타데이터 조회 |
| `GET` | `/meetings/{meeting_id}/files/{file_id}/download-url` | 현재 권한 재검사 후 짧은 signed URL 반환 |
| `POST` | `/meetings/{meeting_id}/process` | extract/STT/analysis 작업 enqueue; `202 {job_id}`; idempotency key 지원 |
| `POST` | `/meetings/{meeting_id}/reanalyze` | 현재 edited transcript로 새 AI run 생성; 기존 편집본 덮어쓰기 전 확인 필요 |
| `GET` | `/jobs/{job_id}` | 단계, 진행 상태, 안전한 오류, retryable 반환 |
| `POST` | `/jobs/{job_id}/retry` | 실패한 동일 작업 재시도 |

### 5.3 편집/공유/내보내기

| Method | Path | 목적/응답 |
|---|---|---|
| `PATCH` | `/meetings/{meeting_id}/notes` | summary/discussions/decisions/follow-ups 수정 |
| `POST` | `/meetings/{meeting_id}/action-items` | 액션아이템 수동 추가 |
| `PATCH` | `/meetings/{meeting_id}/action-items/{item_id}` | 내용/팀원 담당자/기한/상태 수정 |
| `DELETE` | `/meetings/{meeting_id}/action-items/{item_id}` | 액션아이템 삭제 |
| `PUT` | `/meetings/{meeting_id}/shares` | 접근 가능한 팀원 UUID 집합으로 전체 공유 목록 교체 |
| `GET` | `/meetings/{meeting_id}/export?format=txt|pdf` | 권한 확인 후 attachment stream |

공유 API는 팀 외 사용자, removed member, 요청자 자신을 거부하고 사용자가 보낸 이메일이나 이름을 권한 ID로 신뢰하지 않는다. 내보내기는 현재 편집본을 사용하며 원본 파일 다운로드와 분리한다. PDF는 한글 폰트를 번들/서브셋하여 Render 환경에서도 동일하게 생성해야 한다.

## 6. 화면 구성 및 사용자 흐름

### 6.1 라우트

| 화면 | 경로 | 핵심 상태/행동 |
|---|---|---|
| 로그인/가입 | `/login`, `/signup` | 이메일 인증 안내, 오류, redirect 복원 |
| 팀 선택/생성 | `/teams`, `/teams/new` | 첫 사용자 onboarding |
| 회의 목록 | `/t/:teamId/meetings` | 카드 목록, 처리 badge, 검색은 MVP 선택 |
| 새 회의 | `/t/:teamId/meetings/new` | 직접 입력 또는 TXT/PDF/음성 중 하나, 업로드 진행 |
| 처리 중 | `/meetings/:id/processing` | 단계, 재시도, 화면 이탈 가능 안내 |
| 회의 상세 | `/meetings/:id` | `요약 / 전문 / 액션아이템` 탭, 편집·저장 상태 |
| 공유 | `/meetings/:id/share` | 같은 팀원 체크 목록 |
| 팀 관리 | `/t/:teamId/settings` | 멤버/초대; owner/admin만 관리 기능 노출 |
| 내 액션 | `/actions` | 나에게 할당된 항목; 시간이 부족하면 2차 우선순위 |

375px 기준으로 한 열 레이아웃, 최소 44px 터치 영역, 줄바꿈 가능한 제목/메타데이터를 사용한다. 데스크톱에서는 중앙 `max-width` 컨테이너를 넓힐 뿐 정보 구조를 바꾸지 않는다. 모바일 하단 내비게이션은 회의·새 회의·액션·팀으로 구성하고 safe-area inset을 반영한다.

### 6.2 대표 흐름

1. 가입/로그인 → 팀 생성 또는 초대 수락 → 회의 목록
2. `새 회의` → 제목/소스 선택 → draft가 먼저 생성됨
3. 파일이면 signed URL 업로드 후 complete, 직접 입력이면 transcript 저장
4. 처리 시작 → 단계별 상태 폴링 → 실패 시 원본 유지 및 재시도
5. ready → 요약/전문/액션 탭 검토 → 명시적 저장 또는 debounce + 저장 상태 표시
6. 공유 → 같은 팀의 특정 멤버 선택 → read-only 접근 부여
7. 내보내기 → 현재 편집본 TXT/PDF 다운로드

각 화면은 skeleton/loading, 네트워크 오류+재시도, 권한 없음(403), 데이터 없음 CTA를 구분한다. 낙관적 갱신은 액션 상태처럼 되돌리기 쉬운 작업에만 쓰고, 공유/삭제/AI 재분석은 서버 확정 후 반영한다.

## 7. 개발 단계별 우선순위

### P0 — 첫째 날: 수직 기능 경로

1. monorepo scaffold, 환경변수 schema, lint/typecheck/test 명령
2. Supabase migration: profiles/teams/members/meetings/transcripts/notes/actions/jobs + RLS와 seed
3. Auth 화면, 보호 route, FastAPI JWT 검증/JWKS cache와 권한 dependency
4. 팀 생성 → 회의 draft → 직접 전문 입력 → mock 분석 → 상세/편집의 end-to-end 경로
5. 회의 목록/상세의 모바일 기본 레이아웃과 오류/빈 상태

### P0 — 둘째 날: 필수 외부 연동

1. private Storage signed upload/complete/download와 TXT/PDF 텍스트 추출
2. OpenAI STT adapter와 OpenRouter analysis adapter, Pydantic 검증/재시도/작업 상태
3. 액션아이템 수정, 특정 팀원 공유, 팀 초대 수락
4. TXT/PDF export, PWA manifest/icons/service worker 설치 확인
5. 핵심 RLS 거부 테스트, API auth/권한 테스트, 375px/새로고침/배포 smoke test

### P1 — MVP 안정화

- 내 액션 화면, 초대 이메일 provider, AI usage/cost 관찰성
- 작업 복구 관리 endpoint/cron, rate limit, 파일 악성코드 검사
- 긴 음성 chunking, OCR, 화자 분리

완료 기준은 “화면 존재”가 아니라 실제 테스트 결과다. API 키가 없으면 mock으로 UI 경로만 검증했다고 표시하고 실제 STT/LLM 연동 완료로 보고하지 않는다.

## 8. 외부 서비스에서 직접 설정할 항목

### Supabase

- 프로젝트/리전 생성, 로컬 migration 적용, 모든 public 테이블 RLS 확인
- 이메일/password Auth 활성화, Site URL 및 Vercel preview/production redirect allowlist 설정
- 이메일 확인 여부, SMTP/메일 템플릿, access token 만료 정책 결정
- private `meeting-files` bucket 생성; MIME allowlist와 크기 제한 설정
- publishable key는 프론트엔드, secret/service-role key는 Render secret에만 설정
- Auth signing key/JWKS URL 확인. asymmetric signing key 사용 권장
- Storage signed URL 만료, CORS, 백업/PITR 정책 확인

관련 공식 문서: [Supabase Auth](https://supabase.com/docs/guides/auth), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [Private Storage](https://supabase.com/docs/guides/storage/serving/downloads), [JWT signing keys](https://supabase.com/docs/guides/auth/signing-keys).

### OpenAI / OpenRouter

- 각 API key 생성, 예산/사용 한도와 결제 알림 설정
- `OPENAI_STT_MODEL=gpt-4o-transcribe-diarize`를 설정하고 2027-02-26 이전 교체 계획 수립
- OpenRouter에서 사용 가능한 DeepSeek 모델의 정확한 ID, structured output, context, 가격, 데이터 보존 정책을 확인해 `OPENROUTER_ANALYSIS_MODEL`에 pin
- OpenRouter app attribution header는 선택적으로 설정하고 provider fallback은 MVP에서 끈다(재현성과 데이터 처리 위치 통제)

### Vercel / Render

- Vercel root directory=`frontend`, build/output, SPA rewrite, PWA cache header 설정
- Render root directory=`backend`, build/start command, health path, Python version, single worker 설정
- 양쪽 production/preview 환경변수와 CORS origin을 정확히 분리
- Render 인스턴스 timeout/ephemeral disk/cold start 확인. 업로드 원본을 로컬 디스크에 영구 보관하지 않음

### 제안 환경변수

```dotenv
# frontend/.env.example — 공개 가능 값만
VITE_API_BASE_URL=
VITE_SUPABASE_URL=
VITE_SUPABASE_PUBLISHABLE_KEY=

# backend/.env.example — 값은 비워서 커밋
APP_ENV=development
FRONTEND_ORIGINS=http://localhost:5173
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_STORAGE_BUCKET=meeting-files
OPENAI_API_KEY=
OPENAI_STT_MODEL=gpt-4o-transcribe-diarize
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=90
OPENAI_MAX_RETRIES=1
STT_MODE=mock
OPENROUTER_API_KEY=
OPENROUTER_ANALYSIS_MODEL=deepseek/deepseek-v3.2
AI_MODE=real
MAX_AUDIO_BYTES=52428800
STT_DIRECT_MAX_BYTES=20000000
STT_CHUNK_SECONDS=600
STT_CHUNK_OVERLAP_SECONDS=2
STT_MAX_CHUNKS=24
STT_MAX_AUDIO_SECONDS=14400
SIGNED_URL_TTL_SECONDS=300
```

## 9. 주요 보안 및 기술적 위험

| 위험 | 영향 | MVP 대응 |
|---|---|---|
| service key 사용으로 RLS 우회 | 타 팀 회의/파일 유출 | 서버 권한 service 강제, 가능하면 사용자 JWT 전달, 허용/거부 통합 테스트 |
| Storage 경로 조작/오래 사는 URL | 원본 파일 유출 | 서버 생성 경로, private bucket, 요청 때 권한 재검사, 5분 URL, 짧은 cache control |
| JWT 검증 누락/잘못된 claim 신뢰 | 계정 가장 | JWKS 라이브러리로 signature/iss/aud/exp 검증, `sub`만 ID로 사용, `raw_user_meta_data` 금지 |
| 초대 토큰/이메일 열거 | 무단 팀 가입 | token hash 저장, 만료/1회성/이메일 일치, 일반화된 오류와 rate limit |
| MIME spoofing/악성 PDF/대용량 파일 | 메모리 고갈·파서 취약점·비용 폭증 | magic byte/크기/페이지 제한, streaming, parser timeout, allowlist; 후속 악성코드 검사 |
| 외부 AI로 기밀 회의 전송 | 개인정보/영업비밀 유출 | 사용자 고지/동의, provider 보존 정책 확인, 최소 데이터 전송, 로그/trace 본문 비활성화 |
| prompt injection이 원문에 포함 | 허위 구조화/정보 유출 | transcript를 비신뢰 데이터로 구분, 도구 호출 없음, 고정 schema, 원문 근거, 사람이 검토 |
| 환각·날짜/담당자 오인 | 잘못된 업무 실행 | null 원칙, evidence, 검증 schema, AI 표시, 사용자 편집/승인, 자동 알림 제외 |
| background task 유실/중복 | 작업 영구 대기·중복 비용 | DB job 원장, idempotency, stale 복구/재시도; 성장 시 durable queue 전환 |
| transcript/model context 초과 | 분석 실패/정보 누락 | 사전 token/문자 제한, 잘라내지 않고 오류; 후속 chunking 설계 |
| 동시 편집 마지막 쓰기 승리 | 사용자 수정 유실 | `version` 기반 optimistic locking, 409 후 최신 데이터 병합 안내 |
| signed URL/브라우저/CDN cache | 권한 철회 후 잠시 접근 | 짧은 TTL/cache, 민감 다운로드 proxy 고려, 긴급 시 object 이동/삭제/키 회전 |
| PWA cache에 민감 API 응답 저장 | 공유 기기 정보 노출 | service worker는 app shell만 cache, API/파일/HTML auth 응답은 `no-store` |
| PDF 한글 폰트/배포 런타임 차이 | 깨진 export | 재배포 가능한 라이선스 폰트 번들, 실제 Render smoke test |
| 비용/남용 | API 예산 소진 | 사용자별 동시 작업 제한, 파일 크기 제한, 재시도 제한, usage 저장, provider 예산 알림 |

## 10. 구현 시 먼저 확정할 결정

1. OpenRouter DeepSeek 모델 ID와 structured output 지원 여부를 공식 카탈로그에서 선택·pin한다.
2. 팀 초대 메일을 실제 발송할지, MVP 데모에서는 초대 링크 복사로 제한할지 결정한다.
3. 공유받은 멤버를 read-only로 할지 `can_edit`를 노출할지 결정한다. 2일 MVP 권장은 read-only다.
4. PDF export 라이브러리와 한글 폰트 라이선스를 확정한다.
5. 실제 대표 파일(한국어 회의, 잡음 음성, 표가 있는 PDF)로 크기·시간·비용 상한을 측정한다.
