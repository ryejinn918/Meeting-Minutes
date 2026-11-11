# MeetFlow Supabase 2-A 설정 가이드

이 문서는 개발용 Supabase 프로젝트를 연결하기 위한 수동 작업을 정리한다. Migration은 저장소에만 작성되어 있으며 운영 또는 원격 DB에 자동 적용되지 않았다.

## 1. 프로젝트와 Auth

1. Supabase 프로젝트를 생성한다.
2. Authentication → Providers에서 Email/Password를 활성화한다.
3. 개발 중 이메일 확인을 사용할지 결정한다. 활성화하면 가입 직후 UI가 확인 이메일 안내를 표시하고, 확인 전 로그인은 차단된다.
4. Authentication → URL Configuration에서 Site URL을 `http://localhost:5173`으로 지정한다.
5. Redirect URLs에 로컬 주소, Vercel preview/production 주소를 각각 등록한다.
6. 운영 이메일을 보낼 경우 SMTP와 메일 템플릿을 별도로 설정한다.

## 2. Migration 적용 순서

현재 Migration은 하나이며 순서는 파일명 기준이다.

1. `supabase/migrations/202611110001_initial_schema.sql`

Supabase CLI는 저장소 루트의 개발 의존성으로 고정되어 있으므로 `npx supabase`로 실행한다. 적용 전 Dashboard의 Project Ref가 `backend/.env`의 `SUPABASE_URL` host와 일치하는지 확인한다.

```powershell
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase db push --dry-run --remote
```

`login`에는 Supabase Personal Access Token이 필요하고, `link`에는 프로젝트 DB 비밀번호를 요청할 수 있다. 두 값은 프로젝트 `.env`에 저장하거나 명령 인자로 남기지 않고 CLI의 숨김 prompt에서 입력한다. `db push --dry-run --remote`는 적용 예정 목록만 확인하며 DB schema를 변경하지 않는다.

dry-run 결과와 대상 Project Ref를 다시 확인한 후에만 실제 적용 명령을 별도로 실행한다.

```powershell
npx supabase db push --remote
```

위 실제 적용 명령은 명시적 승인 전에는 실행하지 않는다. `db reset --remote`, `migration repair`, `--include-seed`는 이 초기 적용 절차에서 사용하지 않는다.

Dashboard SQL Editor를 사용하는 경우 파일 전체를 한 번 실행한다. 중간 일부만 실행하면 enum, trigger, RLS policy 의존 순서가 깨질 수 있다.

적용 후 확인한다.

- `profiles`, `teams`, `team_members`, `meetings`, `meeting_transcripts`, `meeting_notes`, `action_items`
- 미래 연동용 `meeting_shares`, `meeting_ai_runs`, `processing_jobs`
- 모든 public 애플리케이션 테이블의 RLS 활성화
- 신규 Auth 사용자 생성 시 `profiles` 행 생성
- 팀 생성 시 creator의 owner `team_members` 행 생성

## 3. API 키와 JWT

Project URL과 publishable key는 프론트엔드 및 백엔드에 설정한다. secret/service-role key는 백엔드 secret 저장소에만 두고 `VITE_*` 환경변수에 넣지 않는다.

비대칭 signing key 프로젝트는 `${SUPABASE_URL}/auth/v1/.well-known/jwks.json`의 JWKS로 signature, issuer, audience, expiry를 검증한다. legacy HS256 프로젝트는 JWKS에 키가 없으므로 Supabase Auth `GET /auth/v1/user` 검증 경로를 사용한다. `SUPABASE_JWT_MODE=auto`가 JWT header를 보고 두 경로를 선택한다.

## 4. 로컬 연결 확인

1. Frontend의 `.env` 또는 `.env.local`과 Backend `.env`를 작성한다. 둘 다 같은 Supabase 프로젝트를 가리켜야 한다.
2. Backend `GET /health`가 200인지 확인한다.
3. 회원가입 후 `profiles`가 생성됐는지 확인한다.
4. 로그인 → 팀 생성 → 직접 입력 회의록 저장을 수행한다.
5. 새로고침 후 팀과 회의록이 유지되는지 확인한다.
6. 다른 일반 팀 계정으로 공유되지 않은 회의록의 목록 및 직접 URL 접근이 차단되는지 확인한다.
7. 작성자가 아닌 일반 멤버의 PATCH/DELETE가 403 또는 RLS 거부로 실패하는지 확인한다.

실제 프로젝트 URL과 키가 없는 환경에서는 3~7을 검증 완료로 보고하면 안 된다.

## 5. 이번 단계에서 설정하지 않는 항목

- Private Storage bucket 및 파일 정책
- OpenAI/OpenRouter 키
- 실제 팀 초대 메일
- 회의록 공유 API
- Vercel/Render 배포 환경변수

이 항목들은 각각 파일 업로드, AI 분석, 공유, 배포 단계에서 설정한다.
