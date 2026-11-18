"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def _labels(ds, stem):
    """[(số dòng gốc, lớp, box)] các dòng nhãn hợp lệ — giữ số dòng cho POSSIBLE_FALSE_POS."""
    out = []
    for n, ln in ds.read_label_lines(stem) or []:
        try:
            k, *box = parse_yolo_line(ln)
        except ValueError:
            continue                                   # dòng hỏng: label_format báo
        if 0 <= k < len(ds.classes):
            out.append((n, k, box))
    return out


def run(ds, cfg, preds=None):
    c = cfg["second_opinion"]
    preds = get_preds(ds, cfg, "checker") if preds is None else preds
    issues = []
    for p in ds.image_files():
        stem, size = p.stem, ds.image_size(p.stem)
        if stem not in preds or not ds.label_path(stem).exists() or not size:
            continue
        W, H = size
        L = _labels(ds, stem)

        def add(code, msg, line=None, **extra):
            issues.append(Issue("second_opinion", WARN, code, stem, msg, line=line, extra=extra))

        for k, conf, *box in preds[stem]:
            if conf < c["conf"] or box[2] * W * box[3] * H < c["min_area_px"]:
                continue
            cands = [(iou_xywh(box, b), kl) for _, kl, b in L]
            cands = [(iou, kl) for iou, kl in cands if iou >= c["iou_missing"]]
            same = max((iou for iou, kl in cands if kl == k), default=None)
            other = max(((iou, kl) for iou, kl in cands if kl != k), default=None)
            if not cands:
                add("POSSIBLE_MISSING", f"model thấy lớp {k} (conf {conf:.2f}) nhưng không có box nhãn nào", conf=conf, cls=k, box=box)
            elif same is not None:
                if same < c["iou_loose"]:
                    add("POSSIBLE_LOOSE_BOX", f"box lớp {k} lệch/lỏng: IoU {same:.2f} < {c['iou_loose']}", conf=conf, iou=round(same, 4))
            elif other[0] >= c["iou_match"]:
                add("POSSIBLE_WRONG_CLASS", f"nhãn lớp {other[1]}, model nói lớp {k} (IoU {other[0]:.2f})", conf=conf, iou=round(other[0], 4), label_cls=other[1], pred_cls=k)

        strong = [box for _, conf, *box in preds[stem] if conf >= c["fp_conf"]]   # không lọc diện tích
        for n, kl, b in L:
            best = max((iou_xywh(b, r) for r in strong), default=0.0)
            if best < c["iou_missing"]:
                add("POSSIBLE_FALSE_POS", f"box lớp {kl} không khớp vật nào model thấy (IoU tốt nhất {best:.2f})", line=n, iou=round(best, 4))
    return issues
