import inspect
import immediatelylaw.app as m
import immediatelylaw.watcher as w

cls = [n for n in dir(m) if inspect.isclass(getattr(m, n))
       and getattr(m, n).__module__ == m.__name__]
print("classes in app.py:", cls)
for n in cls:
    c = getattr(m, n)
    if hasattr(c, "_on_citation"):
        s = inspect.getsource(c._on_citation)
        print(f"{c.__name__}._on_citation has resolve_start mark:",
              "resolve_start" in s)
        print("first 5 lines:")
        print("\n".join(s.splitlines()[:5]))
s = inspect.getsource(w.ClipboardWatcher._handle)
print("watcher emits rid:", '"rid"' in s)
