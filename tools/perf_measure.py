# 측정 러너: 격리 APPDATA로 소스 앱 실행 → 스크립트 복사 N회 → 앱 종료
# 사용: python tools/perf_measure.py before|after
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISO_APPDATA = os.path.join(os.environ["TEMP"], "il_measure", "AppData", "Roaming")
LOG = os.path.join(os.environ["TEMP"], "il_measure", "perf_%s.log" % sys.argv[1])
if os.path.exists(LOG):
    os.remove(LOG)

env = dict(os.environ)
env["APPDATA"] = ISO_APPDATA
env["IMMEDIATELYLAW_PERF"] = LOG
proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py")], env=env)
time.sleep(9)   # 앱 부트(단일 인스턴스·DB 연결) 대기

INPUTS = [
    "\u300c\ubbfc\ubc95\u300d \uc81c750\uc870",
    "\u300c\ud615\ubc95\u300d \uc81c23\uc870",
    "\u300c\uac1c\uc778\uc815\ubcf4 \ubcf4\ud638\ubc95\u300d \uc81c15\uc870",
]
PS = ("powershell", "-NoProfile", "-Command")


def clip(text):
    subprocess.run([*PS, f"Set-Clipboard -Value '{text}'"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


try:
    for i in range(10):          # 워밍업
        clip(INPUTS[i % 3])
        time.sleep(0.7)
    time.sleep(1.0)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("# MARK measure_start\n")
    for i in range(90):          # 본측정: 3입력 × 30회
        clip(INPUTS[i % 3])
        time.sleep(0.7)
    time.sleep(1.5)
finally:
    proc.terminate()
    try:
        proc.wait(8)
    except subprocess.TimeoutExpired:
        proc.kill()
print("done ->", LOG)
