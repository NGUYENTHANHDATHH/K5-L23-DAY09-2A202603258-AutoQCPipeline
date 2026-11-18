import sys, pathlib
TOL = 0.002  # overflow_tol trong configs/pipeline.yaml: chỉ báo khi tràn quá mức này
dir_ = sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[1] / "data/raw/labels"  # mặc định: nhãn raw
for f in sorted(pathlib.Path(dir_).glob("*.txt")):
    for n, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        p = ln.split()
        if len(p) != 5: continue
        try: x, y, w, h = map(float, p[1:])
        except ValueError: continue
        if max(-(x - w/2), x + w/2 - 1, -(y - h/2), y + h/2 - 1) > TOL:
            print(f"{f.name}, dòng {n}: box tràn ảnh (mép ngoài khoảng [0,1])")
