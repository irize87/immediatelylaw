import collections
import itertools

c = collections.Counter()
rids = collections.defaultdict(list)
path = r"C:\Users\irize\AppData\Local\Temp\il_measure\perf_before.log"
for ln in open(path, encoding="utf-8"):
    if ln.startswith("#"):
        continue
    p = ln.split()
    if len(p) >= 3:
        c[p[2]] += 1
        rids[p[1]].append(p[2])
print("phases:", c.most_common())
print("distinct rids:", len(rids))
for r, ph in itertools.islice(sorted(rids.items(), key=lambda kv: int(kv[0][3:])), 6):
    print(r, ph)
