import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO = os.path.join(os.environ["TEMP"], "il_measure")
env = dict(os.environ)
env["APPDATA"] = os.path.join(ISO, "AppData", "Roaming")
env["IMMEDIATELYLAW_PERF"] = os.path.join(ISO, "perf_probe3.log")
log = env["IMMEDIATELYLAW_PERF"]
if os.path.exists(log):
    os.remove(log)

err = open(os.path.join(ISO, "stderr3.txt"), "wb")
p = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py")],
                     env=env, stderr=err, stdout=subprocess.DEVNULL)
for i in range(8):
    time.sleep(1.5)
    alive = p.poll() is None
    print(f"t={i*1.5+1.5:4.1f}s alive={alive} code={p.poll()} logsize="
          f"{os.path.getsize(log) if os.path.exists(log) else 'none'}")
    if not alive:
        break
if p.poll() is None:
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Set-Clipboard -Value '\u300c\ubbfc\ubc95\u300d \uc81c750\uc870'"],
                   check=False, capture_output=True)
    time.sleep(2)
    print("after copy: logsize=", os.path.getsize(log) if os.path.exists(log) else "none")
    print(open(log, encoding="utf-8").read()[-500:])
    p.terminate()
p.wait(8)
err.close()
print("--- stderr ---")
print(open(os.path.join(ISO, "stderr3.txt"), "rb").read()
      .decode("cp949", "replace")[-2000:])
