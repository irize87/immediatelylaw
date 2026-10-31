import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["IMMEDIATELYLAW_PERF"] = os.path.join(
    os.environ["TEMP"], "il_measure", "perf_minitest.log")

from PySide6.QtCore import QObject, QCoreApplication, QTimer, Signal
from immediatelylaw import watcher as wmod

hits = []


class FakeClip(QObject):
    dataChanged = Signal()
    def __init__(self, t):
        super().__init__()
        self.t = t
    def text(self):
        return self.t


def slot(payload):
    hits.append(payload)
    from immediatelylaw import perf
    perf.mark(payload.get("rid") or 0, "resolve_start", group=1)
    perf.mark(payload.get("rid") or 0, "resolve_end", found=1)


app = QCoreApplication([])
cfg = {"clipboard_paused": False, "last_law": ""}
clip = FakeClip("「민법」 제750조")
w = wmod.ClipboardWatcher(clip, cfg)
w.citation.connect(slot)
clip.dataChanged.emit()
QTimer.singleShot(600, app.quit)
app.exec()
print("slot hits:", len(hits), "| rid:", [h.get("rid") for h in hits])
print("perf env:", os.environ.get("IMMEDIATELYLAW_PERF"))
log = os.environ["IMMEDIATELYLAW_PERF"]
print("--- log ---")
print(open(log, encoding="utf-8").read() if os.path.exists(log) else "(empty)")
