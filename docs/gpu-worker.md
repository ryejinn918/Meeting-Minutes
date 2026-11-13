# MeetFlow WhisperX GPU 워커

GPU 워커는 외부 포트를 열지 않고 Render API로 아웃바운드 HTTPS 요청만 보냅니다. Supabase secret/service-role 키는 워커에 저장하지 않습니다. OpenAI 전사가 운영 기본값이며, 화면에서 `WhisperX`를 명시적으로 선택한 작업만 워커 큐에 들어갑니다.

## 환경변수

Render 백엔드에는 `GPU_WORKER_TOKEN_HASHES`(원문 토큰의 SHA-256 hex, 회전 시 쉼표로 병행), `GPU_WORKER_LEASE_SECONDS=120`, `GPU_WORKER_DOWNLOAD_TTL_SECONDS=300`을 등록합니다.

토큰은 최소 32바이트의 암호학적 난수로 생성합니다. 원문은 Windows 사용자 환경변수 `MEETFLOW_WORKER_TOKEN`에만 등록하고, Render에는 원문의 SHA-256 hex digest만 등록합니다. 회전 순서는 **새 digest 추가 → Windows 원문 교체 및 워커 재시작 → claim/heartbeat 확인 → 기존 digest 제거**입니다. digest는 64자리 소문자 hex여야 하며 원문 토큰이나 `HF_TOKEN`을 로그, `.env.example`, Git에 기록하지 않습니다.

Windows 사용자 또는 워커 전용 실행 환경에는 다음을 등록합니다.

- `MEETFLOW_API_BASE_URL`: Render HTTPS 기본 URL
- `MEETFLOW_WORKER_TOKEN`: 원문 워커 토큰. Git과 프로젝트 `.env`에 기록하지 않음
- `MEETFLOW_WORKER_ID`: 워커에 고정한 UUID
- `MEETFLOW_WORKER_NAME=RTX 4090`
- `HF_TOKEN`: 기존 Windows 사용자 환경변수
- `WHISPERX_MODEL=large-v3`
- `WHISPERX_BATCH_SIZE=8`
- `WHISPERX_ASR_CACHE_DIR`: faster-whisper Hub 캐시 루트
- `WHISPERX_ALIGNMENT_CACHE_DIR`: 한국어 alignment Hub 캐시 루트
- `PYANNOTE_MODEL_PATH`: Community-1 snapshot 디렉터리 또는 `config.yaml` 경로
- `WHISPERX_LOCAL_FILES_ONLY=true`: 위 로컬 캐시만 사용하고 모델 다운로드를 금지

오프라인 모드에서는 세 캐시 경로를 모두 지정해야 합니다. 경로가 없거나 Community-1의
`config.yaml`을 찾을 수 없으면 워커는 네트워크 다운로드로 전환하지 않고 해당 작업을
실패 처리합니다. 로컬 Community-1 snapshot을 사용할 때 `HF_TOKEN`은 모델 로딩에
전달되지 않지만, 모델 라이선스와 접근 승인은 계속 준수해야 합니다.

승인 후 `202611130002_phase_c_gpu_worker_collaboration.sql`을 적용하고 전용 Python 3.12 환경에서 `python gpu_worker/worker.py`를 실행합니다. 워커가 꺼져 있으면 작업은 queued로 대기하며 OpenAI로 자동 전환하지 않습니다.

## Migration 적용과 복구

적용 전 Supabase 백업 상태와 현재 적용 목록을 확인하고 `202611130001_phase_b_meeting_quality.sql` 다음에 `202611130002_phase_c_gpu_worker_collaboration.sql`을 적용합니다. 그 뒤 Render 코드와 환경변수를 반영하고 마지막으로 Windows 워커를 시작합니다. Migration은 기존 팀·회의·공유 행을 백필하거나 삭제하지 않으며, 기존 파일의 전사 provider 기본값은 `openai`입니다.

문제가 생기면 먼저 Windows 워커를 중지하고 프론트엔드에서 WhisperX 선택을 노출하지 않은 상태로 애플리케이션 코드를 이전 버전으로 되돌립니다. Phase C 스키마는 additive이므로 긴급 복구 시 테이블·컬럼을 즉시 삭제하지 않고 남겨 두는 것이 안전합니다. 완전 제거가 필요하면 백업 후 Phase C 데이터가 없는지 확인하고, 별도 승인된 후속 Migration에서 RPC/정책/트리거 → `team_invitations`·`gpu_workers` → 추가 컬럼 순으로 제거합니다. 이미 생성된 transcript나 공유 데이터를 수동 삭제하지 않습니다.

완료/실패 제출은 DB RPC 한 transaction으로 처리됩니다. lease 만료 후 제출은 거부되고 다른 워커가 재claim할 수 있으며, 성공 응답이 네트워크에서 유실된 경우에도 `result_transcript_id`를 반환해 중복 transcript를 만들지 않습니다.

WhisperX, 한국어 alignment, pyannote Community-1 다운로드와 RTX 4090 모델 로딩은 완료됐지만 실제 한국어 음성 추론과 휴대폰 E2E는 아직 검증하지 않았습니다.
