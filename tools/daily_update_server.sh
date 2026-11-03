#!/usr/bin/env bash
# 즉시로 데이터 매일 발행 — 발행 서버 전용 cron 스크립트.
#   crontab:  0 18 * * * $HOME/ImmediatelyLaw/tools/daily_update_server.sh
#             서버 타임존은 UTC다. 18:00 UTC = KST 03:00(한국은 서머타임 없어
#             고정 +9). 이 서버의 cron(Debian 3.0pl1)은 CRON_TZ를 지원하지 않아
#             CRON_TZ 줄을 적어도 무시된다 — 반드시 UTC 시각으로 적는다.
# 필요 조건:
#   - $APP/.env: export IMMEDIATELYLAW_OC=<OC키>   (chmod 600)
#   - MIRROR_DIR: 배포 서버 디렉터리(HTTPS 서비스가 이 폴더를 제공)
#   - venv: 발행 전용 $HOME/.venvs/immediatelylaw-publisher(requirements-server.txt
#     버전 고정본). 없거나 깨지면 자동 재생성. 저장소 .venv(미러 서비스용)와 분리.
# 발행 대상은 배포 서버 디렉터리 하나다. GitHub는 소스 코드 공개 전용이며
# 대용량 데이터는 올리지 않는다(2026-10-, 과도한 파일호스팅으로 분류될 수 있음).
set -e
APP="$HOME/ImmediatelyLaw"
MIRROR_DIR="${IMMEDIATELYLAW_MIRROR_DIR:-$HOME/immediatelylaw-mirror}"
# 발행 전용 가상환경 — 저장소 .venv와 분리한다. 저장소 .venv은
# immediatelylaw-mirror.service(443 미러 서비스)가 쓰므로 발행 자가치유가
# 거기를 건드리면 안 된다(2026-11-03 지적). 저장소 바깥에 두면 저장소
# clean/reset 사고와도 무관해진다.
VENV="${IMMEDIATELYLAW_PUB_VENV:-$HOME/.venvs/immediatelylaw-publisher}"
case "$(readlink -f "$VENV" 2>/dev/null)" in
    *ImmediatelyLaw/.venv|*/ImmediatelyLaw/.venv)
        echo "!! VENV가 저장소 .venv를 가리킵니다 — 미러 서비스 보호 위해 거부"; exit 1;;
esac
cd "$APP"

# 실행 환경 자가치유(발행 전용 venv만): '환경 불량'(venv 소멸/모듈 없음)만 재생성하고,
# 코드 오류(문법·로직·이름 변경 등)는 환경을 그대로 두고 중단한다 — 2026-11-03
# 사고 교훈: 코드 버그를 venv 문제로 오판해 환경을 지우면 안 된다.
if ! "$VENV/bin/python" -c "import tools.publisher" >/dev/null 2>&1; then
    out="$("$VENV/bin/python" -c "import tools.publisher" 2>&1 || true)"
    if [ -x "$VENV/bin/python" ] && ! printf '%s' "$out" | grep -qE "No module named|ModuleNotFoundError"; then
        echo "!! $(date -Is) 코드 쪽 임포트 오류로 판단 — venv를 건드리지 않고 중단"
        printf '%s\n' "$out" | tail -6
        exit 1
    fi
    echo "!! $(date -Is) 발행 venv 불량 — 전용 venv 재생성: $VENV"
    rm -rf "$VENV"
    mkdir -p "$(dirname "$VENV")"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q --disable-pip-version-check -r requirements-server.txt
    if ! out2="$("$VENV/bin/python" -c "import tools.publisher" 2>&1 || true)"; then
        echo "!! venv 재생성 후에도 임포트 실패 — 중단"
        printf '%s\n' "$out2" | tail -6
        exit 1
    fi
    echo "== $(date -Is) 발행 venv 준비 완료"
fi

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
    if ! "$VENV/bin/python" -m tools.publisher update; then
        echo "!! update 실패 — 현재 egress IP: \
$(curl -s -m 10 https://checkip.amazonaws.com || echo 알수없음) \
(자세한 원인은 stderr 바로 위 로그 참조)"
        echo "===== $(date -Is) 중단 ====="
        exit 1
    fi
    "$VENV/bin/python" -m tools.publisher package

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
