# MeetFlow

> Phase B 준비 상태: 회의 메타데이터, 유형별 기본 템플릿, 조직·부문·팀별 선택형 용어집, 전문 교정 이력, 확인 질문, 구간별 화자 확인 UI를 로컬 코드에 구현했습니다. 신규 Migration은 원격 DB에 적용하기 전 별도 검토와 승인이 필요합니다.

사내 팀용 AI 회의록 관리 모바일 PWA입니다. 현재 **3-B단계**로 직접 입력과 파일 기반 전문 생성, OpenRouter 회의 분석 파이프라인까지 구현되어 있습니다.

## 현재 동작 범위

실제 Supabase 데이터:

- 이메일 회원가입·로그인·로그아웃, 세션 복원, 보호 라우트
- 팀 생성·조회와 팀원 조회
- 직접 입력 회의록 생성, 목록·상세 조회
- 회의 제목·날짜·전문 수정과 소프트 삭제
- FastAPI JWT 검증, 서버 권한 재검사, PostgreSQL RLS
- 직접 입력 전문의 OpenRouter/DeepSeek 구조화 분석 파이프라인
- 분석 작업 상태 저장·폴링·실패 재시도
- AI 원본 실행 기록과 사용자 편집본 분리 저장
- 요약·논의·결정·후속 논의 편집본 저장과 액션아이템 조회

3-B 로컬 구현(새 Migration 적용 필요):

- MP3/M4A/WAV와 TXT/PDF의 Private Storage signed upload
- 파일 크기·MIME·magic bytes·SHA-256 검증
- TXT UTF-8/BOM 및 텍스트 기반 다중 페이지 PDF 추출
- `gpt-4o-transcribe-diarize` 기반 화자 분리·발화 타임스탬프와 비용 없는 Mock STT provider
- 25MB 초과 음성을 FFmpeg로 10분 단위 변환하고 2초 중첩 전사 결과를 순서대로 병합
- 6MB 초과 파일의 Supabase resumable TUS 업로드와 구간별 STT checkpoint
- 추출·전사 작업 상태 저장, 재시도, 완료 후 전문 확인·수정

아직 Mock 또는 비활성 상태:

- 팀원 초대와 회의록 공유 저장
- PDF 다운로드(TXT 브라우저 다운로드는 동작)
- 재분석 결과 비교·적용 및 액션아이템 편집

Mock 화면은 실제 데이터와 섞지 않으며 화면에 상태를 명시합니다.

OpenRouter 실호출은 환경변수와 실제 모델 계정 상태에 따라 비용이 발생하므로 아직 end-to-end 검증을 완료하지 않았습니다. 개발·자동 테스트는 `AI_MODE=mock`을 기준으로 수행했습니다.

실제 OpenAI STT 호출은 비용이 발생하므로 수행하지 않았습니다. 개발·자동 테스트는 `STT_MODE=mock`을 기준으로 수행했습니다.

## 요구사항

- Node.js 20 이상, npm 10 이상
- Python 3.11~3.13
- Supabase 프로젝트

## Supabase 준비

1. Supabase 프로젝트를 만들고 Email/Password Auth를 활성화합니다.
2. [초기 Migration](supabase/migrations/202611110001_initial_schema.sql)을 검토한 후 개발 프로젝트에 적용합니다. 저장소 작업만으로 원격 DB에는 적용되지 않습니다.
3. AI 분석 작업을 사용하려면 [AI worker 권한 Migration](supabase/migrations/202611110002_ai_worker_grants.sql)도 검토·적용합니다. 이 Migration은 서버의 `service_role`에 분석 관련 테이블의 최소 권한만 부여하며 RLS를 비활성화하지 않습니다.
4. 파일 업로드를 사용하려면 [3-B 파일 Migration](supabase/migrations/202611120001_file_ingestion.sql)을 검토·적용합니다. Private `meeting-files` bucket, 파일 메타데이터와 최소 Storage RLS를 생성합니다.
5. 대용량 음성을 사용하려면 [대용량 음성 Migration](supabase/migrations/202611120002_large_audio_chunking.sql)을 추가로 검토·적용합니다. DB 하드캡, Storage 상한, 비공개 chunk checkpoint를 생성합니다.
6. 화자 분리 전사를 사용하려면 [화자 분리 Migration](supabase/migrations/202611120003_diarized_transcripts.sql)을 검토·적용합니다. 발화 구간과 화자 표시명을 저장하며 기존 전문은 그대로 유지합니다.
7. Project URL, publishable key를 확인합니다. secret key는 백엔드에만 보관합니다.
8. Site URL과 Redirect URL에 `http://localhost:5173` 및 실제 Vercel 주소를 등록합니다.

상세 순서와 JWT 방식별 설정은 [Supabase 설정 가이드](docs/supabase-setup.md)를 참고하세요.

## Frontend 실행

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

`frontend/.env`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
VITE_MAX_AUDIO_BYTES=52428800
```

검증:

```powershell
npm run typecheck
npm run lint
npm run build
```

## Backend 실행

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

최소 `backend/.env`:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
SUPABASE_SECRET_KEY=YOUR_SECRET_KEY
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWT_MODE=auto
OPENROUTER_API_KEY=YOUR_OPENROUTER_KEY
OPENROUTER_ANALYSIS_MODEL=deepseek/deepseek-v3.2
AI_MODE=mock
OPENAI_API_KEY=YOUR_OPENAI_KEY
OPENAI_STT_MODEL=gpt-4o-transcribe-diarize
STT_MODE=mock
```

`SUPABASE_JWT_MODE=auto`는 비대칭 JWT면 JWKS를 사용하고 legacy HS256이면 Supabase Auth `/user` endpoint로 검증합니다. 일반 사용자 요청은 사용자 access token으로 PostgREST/RLS를 통과합니다. 인증·권한을 먼저 확인한 백그라운드 분석 저장만 서버의 secret key를 사용하며, 최신 `sb_secret_...` 키는 `apikey` 헤더로만 전송합니다.

`AI_MODE=mock`은 비용 없는 개발 검증용이며 결과에 Mock 표시가 포함됩니다. 실제 OpenRouter 호출은 모델 ID와 키를 설정한 뒤 `AI_MODE=real`로 명시적으로 전환해야 합니다. 운영 환경은 Mock 모드로 시작하지 않습니다.

`STT_MODE=mock`은 실제 음성을 외부로 보내지 않는 개발 검증용입니다. 실제 전사는 `STT_MODE=real`로 명시적으로 전환해야 합니다. 화자 라벨은 조각별 범위로만 유지하며 서로 다른 조각의 동일 라벨을 같은 사람으로 추측하지 않습니다.

현재 개발 DB에 초기 Migration만 적용된 경우 분석 작업은 `processing_jobs` 접근에서 PostgreSQL `42501`로 실패합니다. 원격 적용 전 반드시 대상 프로젝트를 확인한 뒤 다음 순서로 진행합니다.

```powershell
npx supabase migration list
npx supabase db push --remote --dry-run
# 출력에서 202611110002_ai_worker_grants.sql만 예정된 것을 확인한 뒤,
# 사용자 승인 후에만 실제 npx supabase db push 실행
```

검증:

```powershell
Invoke-RestMethod http://localhost:8000/health
pytest
ruff check .
```

## API

비인증 `GET /health`를 제외한 아래 endpoint는 Supabase Bearer token이 필요합니다.

- `GET /api/v1/me`
- `POST/GET /api/v1/teams`
- `GET /api/v1/teams/{team_id}`
- `POST/GET /api/v1/meetings`
- `GET/PATCH/DELETE /api/v1/meetings/{meeting_id}`
- `POST /api/v1/meetings/{meeting_id}/transcript`
- `POST /api/v1/meetings/{meeting_id}/files/upload-url`
- `POST /api/v1/meetings/{meeting_id}/files/{file_id}/complete`
- `GET /api/v1/meetings/{meeting_id}/files`
- `POST /api/v1/meetings/{meeting_id}/process`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/retry`
- `PATCH /api/v1/meetings/{meeting_id}/notes`
- `POST/GET /api/v1/organizations`
- `GET /api/v1/organizations/{organization_id}`
- `POST /api/v1/organizations/{organization_id}/departments`

오류는 `{ "error": { "code", "message", "details?", "request_id" } }` 형식입니다.

## Phase A 조직 계층

조직과 부문을 등록하고 새 팀을 해당 범위에 연결할 수 있습니다. 기존 팀은 데이터 안전을 위해 자동으로 조직에 배정하지 않으며 `조직 미지정` 상태로 계속 사용할 수 있습니다. 회의록 삭제는 소프트 삭제이며 진행 중인 전사·정리 작업이 있거나 version 충돌이 있으면 삭제하지 않습니다.

새 Migration `202611120005_organization_hierarchy_and_safe_delete.sql`은 아직 원격 DB에 적용하지 않습니다. 적용 전 Supabase 대상 프로젝트와 백업 정책을 확인해야 합니다.

## 문서

- [시스템 아키텍처](docs/architecture.md)
- [Supabase 설정 가이드](docs/supabase-setup.md)
- [Vercel + Render 배포 가이드](docs/deployment.md)
- [개발 규칙](AGENTS.md)
