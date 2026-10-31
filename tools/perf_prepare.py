# 측정용 격리 환경 준비: 가짜 APPDATA에 설정·DB 사본 + 검증끄기
import json
import os
import shutil

REAL = os.path.expandvars(r"%APPDATA%\immediatelylaw")
ISO_ROOT = os.path.join(os.environ["TEMP"], "il_measure")
ISO_APPDATA = os.path.join(ISO_ROOT, "AppData", "Roaming")
ISO = os.path.join(ISO_APPDATA, "immediatelylaw")
os.makedirs(os.path.join(ISO, "data"), exist_ok=True)

shutil.copyfile(os.path.join(REAL, "config.json"),
                os.path.join(ISO, "config.json"))
cfg = json.load(open(os.path.join(ISO, "config.json"), encoding="utf-8"))
cfg.pop("oc_key_enc", None)           # API 키(DPAPI 암호문)는 측정 환경에 복사하지 않음
cfg.pop("oc_key", None)               # 과거 평문 잔재가 있어도 같이 제거
cfg["verify_enabled"] = False          # 측정 중 외부 API 호출 차단
cfg["update_check"] = False            # 측정 중 업데이트 알림 소음 제거
json.dump(cfg, open(os.path.join(ISO, "config.json"), "w",
                    encoding="utf-8"), ensure_ascii=False, indent=1)

for f in ("immediatelylaw.db", "immediatelylaw.db-wal", "immediatelylaw.db-shm"):
    s = os.path.join(REAL, "data", f)
    if os.path.exists(s):
        shutil.copyfile(s, os.path.join(ISO, "data", f))
        print("copied", f, os.path.getsize(s))
print("ISO:", ISO)
