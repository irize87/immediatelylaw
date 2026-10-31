# -*- coding: utf-8 -*-
"""개발 전용 성능 계측. 아래 환경변수가 없으면 완전히 꺼지고 아무것도 쓰지 않는다.

활성화: IMMEDIATELYLAW_PERF=<로그 파일 경로>
- 시계는 perf_counter_ns(모노톤)만 쓴다.
- 기록은 요청 id(숫자)·단계명·숫자뿐 — 복사 텍스트·법령명·조문 본문·키를 남기지 않는다.
- 버퍼링 후 라인 단위 append; 장시간 실행 시 최대 크기를 넘기면 기록을 중단한다.
"""
import os
import time

_OUT = os.environ.get("IMMEDIATELYLAW_PERF", "")
_MAX_BYTES = 32 * 1024 * 1024      # 초과 시 기록 중단(장시간 무한 누적 방지)
_t0 = time.perf_counter_ns()
_written = 0
_sink = None

if _OUT:
    try:
        os.makedirs(os.path.dirname(_OUT) or ".", exist_ok=True)
        _sink = open(_OUT, "a", encoding="utf-8", buffering=8192)
    except OSError:
        _sink = None


def enabled() -> bool:
    return _sink is not None


def mark(rid: int, phase: str, **fields):
    """(요청 id, 단계[, 숫자 필드]) 1줄 기록. 오프라인이면 무비용에 가깝다."""
    global _written
    if _sink is None:
        return
    if _written > _MAX_BYTES:
        return
    extra = "".join(f" {k}={v}" for k, v in fields.items())
    line = f"{time.perf_counter_ns() - _t0} rid={rid} {phase}{extra}\n"
    _written += len(line)
    _sink.write(line)
    _sink.flush()   # killing 시 유실 방지 — 측정 브랜치는 매 줄 flush가 더 정확


def flush():
    if _sink is not None:
        _sink.flush()
