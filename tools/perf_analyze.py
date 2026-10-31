# -*- coding: utf-8 -*-
"""perf 로그 분석: 이벤트→표시(중앙값/p95/p99) 집계."""
import os
import statistics
import sys


def pctl(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    i = min(len(sorted_vals) - 1, int(round((len(sorted_vals) - 1) * q)))
    return sorted_vals[i]


def analyze(path, label):
    events = {}
    order = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            if line == "# MARK measure_start":
                events, order = {}, []
            continue
        parts = line.split()
        try:
            t, rid, phase = int(parts[0]), int(parts[1].split("=")[1]), parts[2]
        except (ValueError, IndexError):
            continue
        d = events.setdefault(rid, {"order": len(order)})
        if len(order) == d["order"]:
            order.append(rid)
        d[phase] = int(t)

    def spans(phase_a, phase_b, only_after_start=True):
        vals = []
        t0 = min((e.get("clipboard_event", 0) for e in events.values()),
                 default=0)
        for rid in order:
            e = events[rid]
            if phase_a in e and phase_b in e and e[phase_b] >= e[phase_a]:
                if only_after_start and "read_start" not in e:
                    pass
                vals.append((e[phase_b] - e[phase_a]) / 1e6)
        vals.sort()
        return vals

    print(f"== {label} ==")
    n_ev = sum(1 for e in events.values() if "clipboard_event" in e)
    print(f"events={n_ev} "
          f"resolved(sum read→parse_ok)="
          f"{sum(1 for e in events.values() if 'parse_end' in e)}")
    for a, b, name in [
            ("clipboard_event", "read_end", "이벤트→클립보드읽기"),
            ("clipboard_event", "parse_end", "이벤트→파싱"),
            ("clipboard_event", "resolve_end", "이벤트→로컬조회"),
            ("clipboard_event", "html_end", "이벤트→HTML"),
            ("clipboard_event", "show_requested", "이벤트→표시요청"),
            ("clipboard_event", "first_paint", "이벤트→첫페인트")]:
        v = spans(a, b)
        if not v:
            print(f"  {name:14s}: 데이터 없음")
            continue
        print(f"  {name:14s}: n={len(v):3d} "
              f"중앙={statistics.median(v):6.1f}ms "
              f"p95={pctl(v, 0.95):6.1f}ms p99={pctl(v, 0.99):6.1f}ms")
    # 구간 분해(표시요청→첫페인트 = 렌더/레이아웃 비용)
    v = sorted(spans("show_requested", "first_paint") if False else [
        (events[r]["first_paint"] - events[r]["show_requested"]) / 1e6
        for r in order
        if "show_requested" in events[r] and "first_paint" in events[r]
        and events[r]["first_paint"] >= events[r]["show_requested"]])
    if v:
        print(f"  {'표시요청→페인트':14s}: n={len(v):3d} "
              f"중앙={statistics.median(v):6.1f}ms "
              f"p95={pctl(v, 0.95):6.1f}ms")


if __name__ == "__main__":
    analyze(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
