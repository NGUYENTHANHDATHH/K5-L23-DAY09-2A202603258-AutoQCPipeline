"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _clip(ln):
    """Cắt box về [0,1]; trả None nếu sau khi cắt không còn diện tích."""
    k, x, y, w, h = parse_yolo_line(ln)
    x1, y1, x2, y2 = max(0.0, x - w / 2), max(0.0, y - h / 2), min(1.0, x + w / 2), min(1.0, y + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return f"{k} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    errs = [i for i in issues if i.severity == ERROR]
    fixes = []

    # 1) xoá ảnh (trùng / rò rỉ / hỏng / quá nhỏ): làm trước để bỏ qua issue dòng của ảnh đã xoá
    removed = set()
    for i in errs:
        if i.code in REMOVE and i.image not in removed:
            removed.add(i.image)
            p = ds.image_path(i.image)
            if p:
                p.unlink()
            ds.label_path(i.image).unlink(missing_ok=True)
            fixes.append(dict(image=i.image, line=None, action="remove_image", before=p.name if p else i.image, after=f"(đã xoá: {i.code})"))

    # 2) data.yaml sai tên lớp: ghi lại names đúng cfg["classes"], giữ các khoá khác
    if any(i.code == "BAD_CLASS_NAME" for i in errs):
        d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) if ds.yaml_path.exists() else {}
        d = d or {}
        before, d["names"] = d.get("names"), {k: n for k, n in enumerate(cfg["classes"])}
        ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append(dict(image="data.yaml", line=None, action="rename_classes", before=str(before), after=str(d["names"])))

    # 3) ảnh chưa có nhãn: KHÔNG tạo file (rỗng = ảnh nền), chỉ ghi để chuyển người gán
    for i in errs:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            fixes.append(dict(image=i.image, line=None, action="needs_label", before="(không có file)", after="chuyển người gán"))

    # 4) lỗi dòng: gom theo file, quyết định theo số dòng GỐC, ghi lại file MỘT lần
    drop, clip = defaultdict(set), defaultdict(set)
    for i in errs:
        if i.line is None or i.image in removed:
            continue
        if i.code in DROP:
            drop[i.image].add(i.line)
        elif i.code == "BOX_OUT_OF_IMAGE":
            clip[i.image].add(i.line)
    for stem in sorted(set(drop) | set(clip)):
        p = ds.label_path(stem)
        if not p.exists():
            continue
        out = []
        for n, ln in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if n in drop[stem]:                                    # xoá thắng cắt: dòng 2 lỗi chỉ ghi 1 fix
                fixes.append(dict(image=stem, line=n, action="drop_line", before=ln, after=""))
                continue
            if n in clip[stem]:
                try:
                    new = _clip(ln)
                except ValueError:
                    new = None
                if new is None:                                    # nằm hẳn ngoài ảnh: xoá thay vì ghi box rỗng
                    fixes.append(dict(image=stem, line=n, action="drop_line", before=ln, after=""))
                    continue
                fixes.append(dict(image=stem, line=n, action="clip_box", before=ln, after=new))
                ln = new
            out.append(ln)
        p.write_text("".join(l + "\n" for l in out), encoding="utf-8")
    return fixes
