#!/usr/bin/env bash
# 즉시로 데이터 매일 발행 — 발행 서버 전용 cron 스크립트.
#   crontab:  CRON_TZ=Asia/Seoul
#             0 3 * * * $HOME/ImmediatelyLaw/tools/daily_update_server.sh
# 필요 조건:
#   - $APP/.env: export IMMEDIATELYLAW_OC=<OC키>   (chmod 600)
#   - MIRROR_DIR: 배포 서버 디렉터리(HTTPS 서비스가 이 폴더를 제공)
#   - venv: .venv (requests 설치됨)
# 발행 대상은 배포 서버 디렉터리 하나다. GitHub는 소스 코드 공개 전용이며
# 대용량 데이터는 올리지 않는다(2026-10-, 과도한 파일호스팅으로 분류될 수 있음).
set -e
APP="$HOME/ImmediatelyLaw"
MIRROR_DIR="${IMMEDIATELYLAW_MIRROR_DIR:-$HOME/immediatelylaw-mirror}"
cd "$APP"

# OC 키 (env 파일 우선; 없으면 설정 파일의 저장 키 사용)
ENV_FILE="${IMMEDIATELYLAW_ENV:-$APP/.env}"
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    export IMMEDIATELYLAW_OC
fi

LOG="data/daily.log"
{
    echo "===== $(date -Is) 발행 시작 ====="
    if ! .venv/bin/python -m tools.publisher update; then
        echo "!! update 실패 — 현재 egress IP: \
$(curl -s -m 10 https://checkip.amazonaws.com || echo 알수없음) \
(자세한 원인은 stderr 바로 위 로그 참조)"
        echo "===== $(date -Is) 중단 ====="
        exit 1
    fi
    .venv/bin/python -m tools.publisher package

    # dist에는 최신 스냅샷만 유지(과거본 누적 방지). 델타는 publisher가 최근 30개만 유지.
    (cd data/dist && ls -t immediatelylaw-*.db.xz 2>/dev/null |
        tail -n +2 | xargs -r rm -f)

    # ── 발행: 배포 서버 디렉터리(HTTPS 서비스가 이 폴더를 제공) ──
    # GitHub/GitLab에는 데이터를 올리지 않는다(소스 코드만 공개).
    if [ "$(basename "$MIRROR_DIR")" != "즉시로-미러미설정" ]; then
        mkdir -p "$MIRROR_DIR"
        cp -f data/dist/* "$MIRROR_DIR"/ 2>/dev/null || true
        cp -rf web/. "$MIRROR_DIR"/ 2>/dev/null || true
        echo "배포 서버 동기화: $MIRROR_DIR ($(ls "$MIRROR_DIR" | wc -l)개 파일)"
    fi
    echo "===== $(date -Is) 완료 ====="

    # 로그 로테이션(5MB)
    if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 5242880 ]; then
        mv "$LOG" "$LOG.1"
    fi
} >> "$LOG" 2>&1
