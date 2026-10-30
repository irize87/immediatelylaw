#!/usr/bin/env bash
# 즉시로 데이터 매일 발행 — 발행 서버 전용 cron 스크립트.
#   crontab:  CRON_TZ=Asia/Seoul
#             0 3 * * * $HOME/ImmediatelyLaw/tools/daily_update_server.sh
# 필요 조건:
#   - $APP/.env: export IMMEDIATELYLAW_OC=<OC키>   (chmod 600)
#   - immediatelylaw-data 저장소에 쓰기 권한 있는 GitHub Deploy Key가
#     ssh-agent나 ~/.ssh/config에 설정되어 있을 것
#   - (선택) MIRROR_DIR: 자체 미러 배포 디렉터리(HTTPS 서비스가 이 폴더를 제공)
#   - venv: .venv (requests 설치됨)
# 발행 채널(GitHub/GitLab/자체 미러)은 서로 독립이다: 하나 실패해도 나머지는 계속.
set -e
APP="$HOME/ImmediatelyLaw"
REPO="git@github.com:nazgregory/immediatelylaw-data.git"
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

    # dist 브랜치에는 최신 스냅샷만(앱 폴백용). 델타는 publisher가 최근 30개만 유지.
    (cd data/dist && ls -t immediatelylaw-*.db.xz 2>/dev/null |
        tail -n +2 | xargs -r rm -f)

    # ── 발행 ① GitHub dist 브랜치(+등록된 추가 원격) — 실패해도 계속 ──
    .venv/bin/python -m tools.push_dist --repo "$REPO" \
        --also gitlab --msg "daily $(date +%F\ %H:%M)" || \
        echo "!! push_dist 이상 종료(미러 채널은 별도 진행)"

    # ── 발행 ② 자체 미러 디렉터리(HTTPS 서비스 제공 폴더) ──
    if [ "$(basename "$MIRROR_DIR")" != "즉시로-미러미설정" ]; then
        mkdir -p "$MIRROR_DIR"
        cp -f data/dist/* "$MIRROR_DIR"/ 2>/dev/null || true
        echo "자체 미러 동기화: $MIRROR_DIR ($(ls "$MIRROR_DIR" | wc -l)개 파일)"
    fi
    echo "===== $(date -Is) 완료 ====="

    # 로그 로테이션(5MB)
    if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 5242880 ]; then
        mv "$LOG" "$LOG.1"
    fi
} >> "$LOG" 2>&1
