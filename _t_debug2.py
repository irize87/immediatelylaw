import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO = os.path.join(os.environ["TEMP"], "il_measure")
ISO_APPDATA = os.path.join(ISO, "AppData", "Roaming")
LOG = os.path.join(ISO, "perf_probe2.log")
ERRF = os.path.join(ISO, "stderr2.txt")
for p in (LOG, ERRF):
    if os.path.exists(p):
        os.remove(p)

env = dict(os.environ)
env["APPDATA"] = ISO_APPDATA
env["IMMEDIATELYLAW_PERF"] = LOG

errf = open(ERRF, "wb")
proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py")],
                        env=env, stderr=errf, stdout=subprocess.DEVNULL)
time.sleep(10)
subprocess.run(["powershell", "-NoProfile", "-Command",
                "Set-Clipboard -Value '\u300c\ubbfc\ubc95\u300d \uc81c750\uc870'"],
               check=False, capture_output=True)
time.sleep(5)
proc.terminate()
proc.wait(8)
errf.close()

print("--- stderr file ---")
if os.path.exists(ERRF):
    print(open(ERRF, "rb").read().decode("cp949", "replace")[-2500:])
print("--- perf log ---")
if os.path.exists(LOG):
    print(open(LOG, encoding="utf-8").read()[-1500:])
else:
    print("(no log)")
