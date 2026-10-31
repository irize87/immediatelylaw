import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO_APPDATA = os.path.join(os.environ["TEMP"], "il_measure", "AppData", "Roaming")
LOG = os.path.join(os.environ["TEMP"], "il_measure", "perf_probe.log")
ERR = os.path.join(os.environ["TEMP"], "il_measure", "stderr.txt")
for p in (LOG, ERR):
    if os.path.exists(p):
        os.remove(p)

env = dict(os.environ)
env["APPDATA"] = ISO_APPDATA
env["IMMEDIATELYLAW_PERF"] = LOG
proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py")],
                        env=env, stderr=subprocess.PIPE)
time.sleep(9)
subprocess.run(["powershell", "-NoProfile", "-Command",
                "Set-Clipboard -Value '\u300c\ubbfc\ubc95\u300d \uc81c750\uc870'"],
               check=False)
time.sleep(4)
proc.terminate()
err = proc.stderr.read().decode("utf-8", "replace")
open(ERR, "w", encoding="utf-8").write(err)
print("=== stderr (last 3000) ===")
print(err[-3000:] if err else "(no stderr)")
print("=== perf log ===")
if os.path.exists(LOG):
    print(open(LOG, encoding="utf-8").read()[-2000:])
print("=== clipboard now ===")
print(subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                     capture_output=True, text=True).stdout.strip())
