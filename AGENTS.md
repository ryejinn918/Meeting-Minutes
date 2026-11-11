# MeetFlow 개발 규칙

이 파일은 저장소 전체에 적용한다. 하위 디렉터리에 더 구체적인 `AGENTS.md`가 생기면 해당 범위에서는 하위 규칙을 함께 따른다. 구현 전 `docs/architecture.md`를 읽고, 설계 변경이 필요하면 코드와 같은 변경에서 문서도 갱신한다.

## 1. 목표와 범위

- 목표는 2일 안에 동작하고 검증 가능한 모바일 PWA MVP를 만드는 것이다.
- 우선순위는 보안/데이터 보존 → 핵심 수직 흐름 → 모바일 사용성 → 부가 기능 순이다.
- 실시간 자막, LangGraph, 별도 AI 서버, 벡터 DB, 복잡한 RBAC 등 설계 문서의 제외 범위를 임의로 추가하지 않는다.
- 요청과 무관한 대규모 리팩터링, 의존성 교체, 추상화 확대를 피한다.
- 기존 사용자 변경을 보존하고 관련 파일만 수정한다. 알 수 없는 변경을 되돌리지 않는다.

## 2. 저장소 경계

- 단일 저장소에서 `frontend/`, `backend/`, `supabase/`, `docs/`를 분리한다.
- 프론트엔드는 React/Vite/TypeScript, 백엔드는 FastAPI/Pydantic, DB/Auth/Storage는 Supabase를 사용한다.
- AI pipeline은 FastAPI 내부 모듈이다. STT와 분석 provider adapter를 분리하되 별도 서버를 만들지 않는다.
- 핵심 도메인 로직을 범용 `utils`에 넣지 않는다. API route는 얇게 유지하고 service/repository에 책임을 둔다.
- 같은 기능과 타입을 중복 구현하지 않는다. API 계약은 Pydantic/OpenAPI를 기준으로 유지한다.

## 3. 작업 방식

1. 변경 전 관련 파일, 현재 git diff, 기존 테스트와 명령을 확인한다.
2. 가장 작은 동작 단위로 구현하고 불필요한 새 의존성을 추가하지 않는다.
3. 의존성이 꼭 필요하면 목적, 유지보수 상태, 번들/런타임 비용을 확인하고 lockfile을 함께 갱신한다.
4. DB 변경은 재현 가능한 새 migration으로 작성한다. 이미 공유된 migration을 수정하지 않는다.
5. 기능 변경에는 성공 경로뿐 아니라 인증 실패, 권한 거부, 잘못된 입력, 외부 API 실패를 고려한다.
6. 관련 lint/typecheck/test/build를 실행하고 실제 실행한 명령과 결과만 보고한다. 실행하지 않은 검증을 통과했다고 표현하지 않는다.
7. API/DB/환경변수/아키텍처가 바뀌면 문서와 `.env.example`도 같은 변경에서 갱신한다.

## 4. 보안과 권한

- 클라이언트의 `user_id`, `created_by`, role, Storage 경로를 인증 근거로 신뢰하지 않는다.
- FastAPI는 모든 보호 endpoint에서 Supabase JWT의 signature, issuer, audience, expiry를 검증하고 `sub`를 사용자 ID로 사용한다.
- 데이터와 파일 접근은 FastAPI 서버 권한 검사와 PostgreSQL RLS를 모두 통과하도록 설계한다.
- service/secret key로 RLS를 우회하는 코드는 먼저 명시적 authorization 함수를 호출해야 한다. 이 경로에는 타 팀/비공유 사용자 거부 테스트를 작성한다.
- 모든 애플리케이션 테이블과 private Storage object에 RLS를 적용한다. 사용자가 바꿀 수 있는 JWT user metadata를 권한 근거로 쓰지 않는다.
- 원본 파일은 private bucket에 보관한다. 서버가 object 경로를 만들고, 다운로드는 권한 검사 후 짧은 signed URL 또는 서버 stream으로 제공한다.
- API key, service key, access/refresh token, 초대 원문 token, 회의 전문을 코드·git·일반 로그·오류 응답에 남기지 않는다.
- 실제 비밀은 `.env`와 배포 플랫폼 secret에만 둔다. `.env.example`에는 빈 값 또는 안전한 예시만 둔다.
- 업로드는 확장자만 보지 말고 크기, MIME, magic bytes, 허용 형식을 검사한다. 파일명을 경로로 직접 사용하지 않는다.
- CORS는 알려진 frontend origin만 허용한다. 운영 환경에서 `*`와 credentials를 함께 사용하지 않는다.

## 5. 데이터와 AI 불변 조건

- 업로드 원본, STT/직접 입력 원문, AI 생성 결과, 사용자 편집본을 구분해 저장한다.
- 이후 단계가 실패해도 이미 저장한 파일이나 transcript를 삭제하거나 덮어쓰지 않는다.
- AI는 transcript에 없는 사실을 만들지 않으며 제안/추정을 결정으로 표현하지 않는다.
- 담당자와 기한이 불명확하면 `null`이다. 문자열 `"unknown"`, 임의 날짜, 임의 팀원을 넣지 않는다.
- 외부 AI 결과는 신뢰하지 않는다. Pydantic schema로 검증한 뒤에만 DB 편집본으로 변환한다.
- provider SDK 타입과 오류는 adapter 안에 가두고 pipeline에는 내부 result/error 타입만 노출한다.
- 모델 ID, API base URL, timeout, 제한적 재시도 횟수는 설정으로 관리한다. 코드 여러 곳에 model ID를 하드코딩하지 않는다.
- 재시도는 일시 오류와 schema repair에만 제한적으로 적용한다. 인증 오류, quota, 잘못된 파일을 맹목적으로 재시도하지 않는다.
- 처리 단계와 실패를 `processing_jobs`/meeting status에 기록한다. 사용자 오류에는 안전한 메시지와 재시도 가능 여부를 제공한다.
- mock은 `AI_MODE=mock`처럼 명시적으로 선택하고 화면/API 응답에 표시한다. 운영 환경에서 자동 mock fallback을 하지 않는다.

## 6. Backend 규칙

- 지원 Python 버전을 `pyproject.toml`에 고정하고 모든 public 함수/메서드에 현실적인 타입 힌트를 쓴다.
- 설정은 `pydantic-settings` 한 곳에서 읽고 시작 시 필수 환경변수를 검증한다.
- request/response/AI schema를 분리한다. mutable default를 쓰지 않고 timezone-aware datetime을 사용한다.
- route에서 직접 provider SDK나 광범위한 SQL을 호출하지 않는다. `dependency → service → repository/adapter` 경계를 유지한다.
- 비동기 route에서 동기 네트워크/파일 작업으로 event loop를 막지 않는다. 큰 파일 전체를 불필요하게 메모리에 올리지 않는다.
- endpoint는 일관된 status code와 오류 envelope를 사용한다. 예상 가능한 도메인 오류에 stack trace를 응답하지 않는다.
- 목록 endpoint는 pagination과 안정적인 정렬을 사용한다. 사용자 입력 sort column이나 SQL 조각을 직접 연결하지 않는다.
- 업데이트는 가능한 경우 meeting `version`으로 optimistic locking하며 충돌은 `409`로 응답한다.
- 로그에는 request ID, job ID, meeting ID 같은 식별자와 단계만 남긴다. transcript/AI prompt/provider response 본문은 기본적으로 기록하지 않는다.
- 테스트는 최소한 schema 단위 테스트, auth/authorization API 테스트, provider mock pipeline 테스트를 포함한다.

## 7. Frontend 규칙

- TypeScript strict mode를 유지하고 `any`, non-null assertion, 무분별한 type cast를 피한다. 외부 데이터는 runtime/API 경계에서 검증한다.
- 서버 상태는 TanStack Query, 로컬 UI 상태는 component state를 사용한다. 서버 응답을 별도 전역 store에 중복 보관하지 않는다.
- API 호출은 공통 client를 사용해 Bearer token, 오류 변환, base URL을 한 곳에서 처리한다.
- 인증 상태가 확정되기 전에 보호 화면을 렌더링하거나 보호 query를 실행하지 않는다.
- feature별 query key를 중앙화하고 mutation 후 필요한 범위만 invalidate/update한다.
- shadcn/ui primitive를 재사용하되 생성 파일을 무분별하게 복제하지 않는다. 접근 가능한 label, focus, keyboard 동작을 유지한다.
- 모바일 우선으로 작성하고 375px에서 가로 스크롤이 없어야 한다. 고정 폭 대신 `min-w-0`, wrapping, responsive grid를 사용한다.
- 모든 비동기 화면에 loading, empty, error, retry 상태를 제공한다. 저장 중/저장됨/실패 상태를 사용자가 알 수 있게 한다.
- PWA service worker는 app shell/static asset만 cache한다. 인증 API 응답, 회의 데이터, 원본 파일, signed URL을 cache하지 않는다.
- 사용자 텍스트는 기본 escape를 유지하고 임의 HTML을 렌더링하지 않는다.
- 최소 검증은 typecheck, lint, production build와 375px/desktop 핵심 흐름 확인이다.

## 8. Database와 migration 규칙

- 테이블/컬럼은 `snake_case`, PK는 UUID, 시간은 `timestamptz` UTC를 기본으로 한다.
- FK 삭제 동작, unique/check constraint, 주요 조회 인덱스를 migration에 명시한다.
- RLS policy는 명시적인 authenticated 조건과 `using`/`with check`를 모두 검토한다.
- RLS helper의 `security definer`는 비노출 schema, 고정 `search_path`, 최소 execute 권한을 사용한다.
- migration마다 owner/member/non-member/anonymous의 허용 및 거부를 pgTAP 또는 integration test로 검증한다.
- seed에는 가짜 데이터만 넣으며 실제 이메일, API key, 회의 내용을 커밋하지 않는다.
- 운영 데이터에 영향을 주는 destructive migration은 명시적 승인과 복구/백업 계획 없이 실행하지 않는다.

## 9. API와 UI 계약

- base prefix는 `/api/v1`; 오류는 `{error: {code, message, details?, request_id}}` 형식을 따른다.
- 날짜만 의미하면 ISO `YYYY-MM-DD`, 시각이면 UTC ISO 8601을 사용한다. UI에서 사용자 timezone으로 표시한다.
- API enum과 UI label을 분리한다. DB/API에는 안정적인 영문 enum, UI에는 한국어 label을 사용한다.
- 삭제, 공유 변경, 재분석처럼 영향이 큰 작업은 명시적 사용자 행동과 확인을 요구한다.
- 재분석은 기존 AI run과 사용자 편집본을 조용히 덮어쓰지 않는다.
- 다운로드 파일은 안전한 파일명과 올바른 `Content-Type`/`Content-Disposition`을 사용한다.

## 10. Git과 완료 보고

- 생성물, `.env`, 캐시, 업로드 파일, 로컬 DB, coverage, build output을 커밋하지 않는다.
- formatter가 무관한 파일 전체를 바꾸지 않게 변경 범위를 확인한다.
- commit을 요청받으면 작고 의미 있는 단위와 명령형 메시지를 사용한다. 요청 없이 remote push, 배포, migration 운영 적용을 하지 않는다.
- 완료 보고에는 변경 파일, 주요 결정, 실행한 검증과 결과, mock/실제 연동 상태, 남은 위험 또는 다음 단계를 짧게 포함한다.
- 테스트하지 않은 기능, key 없이 호출하지 못한 provider, 적용하지 않은 migration을 완료했다고 보고하지 않는다.

