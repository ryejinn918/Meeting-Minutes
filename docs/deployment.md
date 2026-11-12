# MeetFlow Vercel + Render 배포 가이드

> 기준일: 2026-11-12
> 대상: Vercel 프론트엔드 + Render Free Web Service + 기존 Supabase 프로젝트
> 이 문서는 서비스 생성과 배포를 안내하며, 저장소 작업만으로 외부 서비스가 자동 생성되지는 않는다.

## 1. 배포 전 확인

다음 세 Migration이 대상 Supabase 프로젝트 `rihvbxobcbwjiqpaciek`에 적용됐는지 확인한다.

- `202611110001_initial_schema.sql`
- `202611110002_ai_worker_grants.sql`
- `202611120001_file_ingestion.sql`
- `202611120002_large_audio_chunking.sql` (대용량 음성 기능 배포 전에 별도 적용)

`meeting-files` Storage bucket은 반드시 private이어야 한다. 공개 버킷으로 전환하지 않는다.

로컬에서 다음 명령이 모두 통과한 변경만 GitHub에 push한다.

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm ci
npm run typecheck
npm run lint
npm run build
```

`.env`, `.env.local`, API key, Supabase secret key가 Git 변경 목록에 없는지 확인한다. Commit/Push는 사용자가 명시적으로 승인한 경우에만 수행한다.

## 2. Render 백엔드

저장소 루트의 `render.yaml`을 Blueprint로 사용할 수 있다. Dashboard에서 직접 Web Service를 만들 때는 다음 값을 사용한다.

| 항목 | 값 |
|---|---|
| Service Type | Web Service |
| Repository | `ryejinn918/Meeting-Minutes` |
| Branch | `main` |
| Root Directory | `backend` |
| Runtime | Python 3 |
| Instance Type | Free |
| Build Command | `pip install .` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Auto Deploy | 배포 검증 중에는 선택 사항, 운영 전 정책 확정 |

Python은 `backend/.python-version`과 `PYTHON_VERSION=3.12.8`로 고정한다. Render가 제공하는 `PORT`는 직접 값을 만들지 않고 Start Command에서 사용한다.

### Render 환경변수

Dashboard의 **Environment**에서 다음 이름을 등록한다. 값은 저장소에 쓰지 않는다.

```dotenv
APP_ENV=production
FRONTEND_ORIGINS=https://<실제-vercel-production-domain>

SUPABASE_URL=https://rihvbxobcbwjiqpaciek.supabase.co
SUPABASE_PUBLISHABLE_KEY=<publishable-key>
SUPABASE_SECRET_KEY=<secret-key>
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWT_MODE=auto
SUPABASE_STORAGE_BUCKET=meeting-files

OPENROUTER_API_KEY=<secret>
OPENROUTER_ANALYSIS_MODEL=deepseek/deepseek-v3.2
AI_MODE=real

OPENAI_API_KEY=<secret>
OPENAI_STT_MODEL=gpt-transcribe
STT_MODE=real
```

필요할 때만 기본값을 조정한다.

```dotenv
OPENAI_TIMEOUT_SECONDS=90
OPENAI_MAX_RETRIES=1
OPENROUTER_TIMEOUT_SECONDS=45
OPENROUTER_MAX_RETRIES=1
AI_STALE_JOB_SECONDS=300
MAX_AUDIO_BYTES=52428800
STT_DIRECT_MAX_BYTES=20000000
STT_CHUNK_SECONDS=600
STT_CHUNK_OVERLAP_SECONDS=2
STT_MAX_CHUNKS=24
STT_MAX_AUDIO_SECONDS=14400
MAX_DOCUMENT_BYTES=10485760
MAX_PDF_PAGES=200
```

운영 모드는 필수 Supabase/AI 설정, 실제 provider 모드, HTTPS CORS origin이 없으면 시작 단계에서 실패하도록 구성되어 있다. 최초 Render 생성 시 Vercel 도메인이 아직 없다면 임시로 본인이 관리하는 HTTPS origin을 넣어 health 배포만 확인하고, Vercel 도메인이 정해지는 즉시 정확한 값으로 교체한다. `*`는 허용하지 않는다.

배포 로그에서 애플리케이션 시작을 확인한 뒤 다음 URL을 연다.

```text
https://<render-service>.onrender.com/health
```

예상 응답:

```json
{"status":"ok","service":"meetflow-api"}
```

## 3. Vercel 프론트엔드

Vercel Dashboard에서 **Add New → Project**를 선택하고 같은 GitHub 저장소를 import한다.

| 항목 | 값 |
|---|---|
| Framework Preset | Vite |
| Root Directory | `frontend` |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Node.js | 20 (`frontend/.nvmrc`) |

`frontend/vercel.json`은 React Router 상세 URL 새로고침을 `index.html`로 rewrite하고, service worker가 오래 캐시되지 않도록 설정한다.

### Vercel 환경변수

**Settings → Environment Variables**에 다음 세 개만 등록한다.

```dotenv
VITE_API_BASE_URL=https://<render-service>.onrender.com
VITE_SUPABASE_URL=https://rihvbxobcbwjiqpaciek.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
VITE_MAX_AUDIO_BYTES=52428800
```

production과 실제로 사용할 preview 환경에 각각 등록한다. 세 값 중 하나라도 없으면 production build가 실패하도록 설정되어 있다.

`VITE_*` 값은 브라우저 번들에 포함된다. 다음 값은 Vercel에 절대 등록하지 않는다.

- `SUPABASE_SECRET_KEY`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- 사용자 access/refresh token

배포 후 production URL을 복사한다. Preview URL은 배포마다 달라질 수 있으므로 운영 인증과 CORS 검증은 고정 production domain을 우선 사용한다.

## 4. CORS 연결

Vercel production URL이 정해지면 Render의 `FRONTEND_ORIGINS`를 정확한 origin으로 수정한다. 경로와 마지막 `/`는 넣지 않는다.

```dotenv
FRONTEND_ORIGINS=https://meetflow-example.vercel.app
```

로컬 프론트엔드에서도 원격 Render를 테스트해야 할 때만 쉼표로 추가한다.

```dotenv
FRONTEND_ORIGINS=https://meetflow-example.vercel.app,http://localhost:5173,http://127.0.0.1:5173
```

FastAPI는 `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS`와 `Authorization`, `Content-Type`, `X-Request-ID`만 허용한다. 와일드카드 origin은 사용하지 않는다. Render 환경변수 변경 후 서비스가 재시작됐는지 확인한다.

## 5. Supabase Auth URL 설정

Supabase Dashboard에서 **Authentication → URL Configuration**을 연다.

1. **Site URL**을 Vercel production URL로 설정한다.
2. **Redirect URLs**에 다음을 유지·추가한다.

```text
http://localhost:5173/**
http://127.0.0.1:5173/**
https://<vercel-production-domain>/**
```

Preview 배포에서 이메일 인증을 시험할 때만 필요한 preview pattern을 추가한다. Supabase의 wildcard 사용은 Auth redirect allowlist에만 제한하며 FastAPI CORS에는 적용하지 않는다.

**Authentication → Providers → Email**에서 이메일 가입과 Confirm email 상태를 확인한다. 개발 중 확인 메일을 꺼 두었다면 실사용 전 다시 켜고, SMTP 발송 한도와 메일 템플릿을 확인한다.

Storage의 `meeting-files` 버킷은 private 상태를 유지한다. 브라우저에는 publishable key와 서버가 발급한 일회성 signed upload 정보만 전달한다.

## 6. Render Free와 BackgroundTasks 한계

현재 STT, 문서 추출, OpenRouter 정리는 FastAPI 프로세스 내부 `BackgroundTasks`로 실행된다. 사용자가 브라우저를 닫거나 다른 화면으로 이동해도 이미 시작한 서버 프로세스가 살아 있는 동안 작업은 계속된다. 그러나 다음 상황은 완료를 보장하지 않는다.

Render 공식 문서 기준으로 Free Web Service는 inbound traffic이 15분 동안 없으면 절전되고, 다음 요청에서 다시 시작하는 데 약 1분이 걸릴 수 있다. 월 750 free instance hours가 workspace에 제공된다. 파일시스템은 ephemeral이므로 restart, redeploy, spin-down 때 로컬 변경이 사라진다. MeetFlow 원본은 Render 디스크가 아니라 Supabase Private Storage에 저장한다.

- Render가 유휴 상태 후 서비스를 절전시키는 경우
- 배포, 장애 또는 인스턴스 교체로 프로세스가 종료되는 경우
- 외부 AI 응답 이후 DB 저장 도중 프로세스가 종료되는 경우

현재 최소 복구 방식:

- 원본 파일은 먼저 Supabase Private Storage에 저장한다.
- 직접 입력/STT/추출 원문과 AI 결과를 분리해 보존한다.
- 작업 상태와 시도 횟수를 `processing_jobs`에 기록한다.
- 동일 회의·작업 유형의 active 작업은 unique index로 중복 시작을 막는다.
- 실패 작업과 `AI_STALE_JOB_SECONDS`보다 오래된 queued/processing 작업은 기존 처리 URL에서 재시도할 수 있다.
- 회의가 이미 `ready`이고 현재 notes가 연결된 경우 분석 worker 재실행은 새 결과를 만들지 않고 기존 작업을 성공 처리한다.
- 최대 시도 횟수는 2회다.

남는 한계:

- 서버 프로세스가 사라지는 순간 자동으로 작업을 이어받는 별도 worker는 없다.
- 여러 테이블의 AI 저장은 단일 DB transaction/RPC가 아니어서 저장 중단 지점에 따라 고아 AI run/notes가 남을 수 있다. 현재 상세 화면은 `current_notes_id`가 가리키는 결과만 사용하므로 기존 원문을 잃지는 않는다.
- 처리 URL을 잃어버린 사용자를 위한 작업 복구 목록 화면은 아직 없다.

따라서 Render Free + `BackgroundTasks`는 데모/MVP에는 사용할 수 있지만 장시간 STT의 안정적인 운영 구성은 아니다. 다음 단계의 최소 개선안은 새 인프라를 추가하기 전에 Supabase 기반 작업 claim RPC와 별도 Render worker/cron 가능성을 검토하는 것이다. 이번 단계에서는 Redis, Celery, 주기적 ping을 추가하지 않는다.

### 중단 시나리오별 결과

| 상황 | 현재 결과 |
|---|---|
| STT 중 서버 종료 | 원본 파일 유지, job은 stale 후 수동 재시도 가능 |
| DeepSeek 중 서버 재시작 | transcript 유지, job은 stale 후 수동 재시도 가능 |
| 모바일 브라우저 종료/화면 이동 | 서버가 살아 있으면 계속 처리, 다시 접속해 DB 결과 조회 가능 |
| Render 절전/재시작 | 실행 중 task 완료 보장 없음, stale 재시도 필요 |
| 결과 저장 직전 종료 | 원본 유지; 부분 AI 행이 남을 수 있으나 현재 결과 포인터로 노출 범위 제한 |

## 7. 스마트폰 파일 업로드 확인

배포 후 실제 iOS Safari와 Android Chrome에서 각각 확인한다.

1. Vercel production URL 접속 및 로그인
2. 팀 선택 → 새 회의록 → 음성파일
3. 휴대폰 파일 앱에서 짧은 MP3/M4A/WAV 선택
4. 파일명·크기 확인 후 업로드
5. 처리 화면을 벗어났다가 다시 열어 상태 확인
6. 전문 탭에서 전사 내용 확인·수정
7. `회의록 정리하기` 실행
8. 요약·결정사항·액션아이템 확인

구현상 모바일 보완:

- 브라우저 MIME 대신 확장자를 기준으로 허용 MIME을 정규화해 iOS/Android 차이를 줄인다.
- 원본 파일명은 메타데이터에만 보존하고 Storage 경로는 UUID를 사용한다.
- Supabase Free에서는 음성 원본을 50MiB로 제한한다. 애플리케이션 하드캡 100MiB는 유료 Storage 한도를 올린 경우에만 사용한다.
- 6MiB 초과 업로드는 resumable TUS를 사용하고, 20MB 초과 음성은 서버에서 FFmpeg로 분할 전사한다.
- signed upload 실패 시 같은 파일을 다시 선택할 수 있도록 중복 해시를 해제한다.
- 가짜 업로드 퍼센트는 표시하지 않는다.

네트워크가 끊기면 현재 업로드는 자동 이어받기하지 않는다. 다시 업로드해야 한다. 서버가 절전 상태면 첫 API 요청이 지연될 수 있으므로 첫 화면에서 즉시 실패로 판단하지 말고 health 응답과 Render 로그를 함께 확인한다.

## 8. 배포 후 E2E 순서

유료 AI 호출은 자동 테스트에서 실행하지 않는다. 배포 후 사용자가 비용 한도를 확인하고 작은 테스트 데이터로 각각 1회 수행한다.

1. `/health` 확인
2. 이메일 가입·확인·로그인·새로고침 세션 유지
3. 팀 생성
4. 직접 입력 회의 저장·수정
5. 작은 TXT 업로드·추출·전문 수정
6. 짧은 한국어 음성 1개 STT
7. 짧은 transcript 1개 OpenRouter 정리
8. 처리 중 화면 이동·복귀
9. 로그아웃 후 보호 API 401
10. 다른 계정에서 비공유 회의 URL 접근 차단
11. `/meetings/<id>` 직접 새로고침 시 Vercel 404가 아닌 앱 표시
12. 스마트폰 홈 화면 설치와 아이콘/standalone 표시 확인

실제 STT와 OpenRouter 성공 여부는 이 검증을 수행하기 전까지 완료로 기록하지 않는다.

현재 manifest와 service worker는 설치 가능한 최소 구성을 갖추고 정적 app shell만 캐시한다. 아이콘은 SVG 한 종류이므로 Android Chrome과 iOS Safari에서 실제 설치 아이콘을 반드시 확인한다. iOS에서 일반 아이콘으로 표시되면 후속 변경으로 192px/512px PNG와 `apple-touch-icon`을 추가한다.

## 9. 공식 문서

- [Render Free 인스턴스](https://render.com/docs/free)
- [Render FastAPI 배포](https://render.com/docs/deploy-fastapi)
- [Vercel monorepo](https://vercel.com/docs/monorepos)
- [Vercel rewrites](https://vercel.com/docs/rewrites)
- [Supabase Auth redirect URL](https://supabase.com/docs/guides/auth/redirect-urls)
- [Supabase Storage upload](https://supabase.com/docs/guides/storage/uploads/standard-uploads)
- [OpenAI File transcription](https://developers.openai.com/api/docs/guides/speech-to-text)
