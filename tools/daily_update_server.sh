#!/usr/bin/env bash
# 즉시로 데이터 매일 발행 — 발행 서버 전용 cron 스크립트.
#   crontab:  CRON_TZ=Asia/Seoul
#             0 3 * * * $HOME/ImmediatelyLaw/tools/daily_update_server.sh
# 필요 조건:
#   - ~/ImmediatelyLaw/.env: export IMMEDIATELYLAW_OC=<OC키>   (chmod 600)
#   - GitHub 배포키: (서버에 설정한 Deploy Key 개인키) 가
#     immediatelylaw-data 저장소에 쓰기 권한 있는 Deploy Key로 등록되어 있을 것
#   - venv: .venv (requests 설치됨)
set -e
APP="$HOME/ImmediatelyLaw"
REPO="git@github.com:nazgregory/immediatelylaw-data.git"
cd "$APP"

# OC 키 (env 파일 우선; 없으면 설정 파일의 저장 키 사용)
if [ -f "$APP/.env" ]; then
    # shellcheck disable=SC1090
    . "$APP/.env"
    export IMMEDIATELYLAW_OC
fi

LOG="data/daily.log"
{
    echo "===== $(date -Is) 발행 시작 ====="
    if ! .venv/bin/python -m tools.publisher update; then
        echo "!! update 실패 — 현재 egress IP: \
$(curl -s -m 10 https://checkip.amazonaws.com || echo 알수없음) \
(open.law.go.kr 등록 IP와 대조)"
        echo "===== $(date -Is) 중단 ====="
        exit 1
    fi
    .venv/bin/python -m tools.publisher package

    # dist 브랜치에는 최신 스냅샷만 남긴다(앱은 스냅샷 전체만 사용)
    (cd data/dist && ls -t immediatelylaw-*.db.xz 2>/dev/null |
        tail -n +2 | xargs -r rm -f)
    (cd data/dist && rm -f delta-*.json.xz 2>/dev/null || true)

    .venv/bin/python -m tools.push_dist --repo "$REPO" \
        --msg "daily $(date +%F\ %H:%M)"
    echo "===== $(date -Is) 완료 ====="

    # 로그 로테이션(5MB)
    if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 5242880 ]; then
        mv "$LOG" "$LOG.1"
    fi
} >> "$LOG" 2>&1
