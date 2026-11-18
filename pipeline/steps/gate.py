"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    n_errors = sum(i.severity == ERROR for i in issues)
    warn_imgs = {i.image for i in issues if i.severity == WARN and i.image in stems and i.image not in reviewed}
    ratio = round(len(warn_imgs) / len(stems), 4) if stems else 0.0
    hold = cfg["gate"]["warn_ratio_hold"]
    if n_errors:
        decision, reasons = "Rework", [f"còn {n_errors} lỗi bắt buộc (ERROR) chưa sửa"]
    elif ratio >= hold:
        decision, reasons = "Hold", [f"{len(warn_imgs)}/{len(stems)} ảnh ({ratio:.1%}) còn cảnh báo chưa người duyệt, >= ngưỡng {hold:.0%}"]
    else:
        decision, reasons = "Release", [f"0 lỗi bắt buộc; {len(warn_imgs)}/{len(stems)} ảnh ({ratio:.1%}) còn cảnh báo, < ngưỡng {hold:.0%}"]
    return dict(decision=decision, n_errors=n_errors, n_warn_images=len(warn_imgs),
                n_images=len(stems), warn_ratio=ratio, reasons=reasons)
