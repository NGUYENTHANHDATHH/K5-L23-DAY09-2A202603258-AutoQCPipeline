# Báo cáo Day 09 — Nguyễn Thành Đạt, 2A202603258

## 1. Kết luận trước

**HOLD** (`08_summary.json`, mã thoát 10). Vào 224 ảnh, intake loại 22 (hỏng, quá nhỏ, trùng, rò rỉ test), còn **202 ảnh** đi qua QC và nằm trong bản xuất nháp `submission/export/clean_v1` (202 file nhãn; **chưa phát hành**). Lỗi bắt buộc còn **0**, nhưng **38/202 ảnh (18.8%)** còn cảnh báo chưa người duyệt, vượt ngưỡng 10%: hàng đợi duyệt có 125 ảnh mà ngân sách chỉ 80.

## 2. Lỗi và phân việc

Từ `02_error_list_v1` (211 issue trên 149 ảnh; mẫu số 224 ảnh quét) và `03_fixes.csv` (35 thay đổi).

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
| --- | ---: | --- | --- |
| `DUP_IMAGE_EXACT` / `DUP_IMAGE_NEAR` | 8 / 4 ảnh | máy (loại ở intake) | Trùng làm lệch phân bố và đếm hai lần; giữ ảnh đầu tiên |
| `LEAK_TEST` | 5 ảnh | máy (loại ở intake) | Ảnh test lọt vào train làm mAP trên test bị thổi phồng |
| `CORRUPT_IMAGE` / `BAD_SIZE` | 2 / 3 ảnh | máy (loại ở intake) | Không mở được / cạnh ngắn < 250 px: không dùng để train được |
| `BAD_CLASS_ID` / `BAD_FORMAT` / `BOX_ZERO` / `DUP_BOX` | 6 / 3 / 4 / 7 dòng | máy (`drop_line`, 20 dòng) | Dòng hỏng không có thông tin đáng tin để sửa; box lặp là thừa |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy (`clip_box`, 8 dòng) | Cắt về [0,1] giữ được vật, chỉ bỏ phần ngoài ảnh |
| `BAD_CLASS_NAME` | 2 tên / `data.yaml` | máy (`rename_classes`) | `Person`/`Bus` sai hoa thường; danh sách lớp cố định trong dự án |
| `MISSING_LABEL_FILE` | 6 ảnh | **người** (`needs_label`) | Máy không bịa nhãn; file rỗng sẽ bị hiểu nhầm là "ảnh nền" |
| `POSSIBLE_MISSING` / `LOOSE_BOX` / `FALSE_POS` / `WRONG_CLASS` | 52 / 24 / 27 / 18 ảnh | **người** | Model lớn chỉ là ý kiến thứ hai, cũng có thể sai |
| `EMPTY_LABEL` / `BOX_TINY` / `BOX_HUGE` / `CLASS_RARE` | 12 ảnh / 6 dòng / 3 dòng / 4 | **người** | Có thể hợp lệ (ảnh nền, người ở xa): chỉ cảnh báo |

**Hàng đợi:** điểm ưu tiên = tổng trọng số cảnh báo (`review.weights`) × (1 + conf của model). Vì vậy đầu hàng là 6 ảnh `NEEDS_LABEL` (10.0) và các ảnh có nhiều loại cảnh báo nặng cùng lúc (vd. `img_0020`: `WRONG_CLASS` + `MISSING` + một dòng đã bị xoá, 11.5). Ngân sách 80 ảnh duyệt đến mức ưu tiên 3.34; ảnh đầu tiên không được duyệt là `img_0210` (3.33). Người xem được **94/123 cảnh báo ngữ nghĩa** (trên 74/103 ảnh) của `04_error_list_v2`. Sau khi người thay nhãn, 25 ảnh đã duyệt vẫn còn cảnh báo của model ở v3: đó là báo động giả của chính model, không tính vào gate.

## 3. Calibration (2 ngưỡng)

| Tham số                 | Khởi đầu | Đã chọn        | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
| ----------------------- | -------- | -------------- | -------------------------------- | ---------------- |
| `duplicates.phash_dist` | 2        | 10             | DUP_IMAGE_NEAR 1.00 / 0.50 (3/6) → 1.00 / 0.67 (4/6); EXACT giữ 1.00 / 1.00 (3/3) | Ngưỡng này **xoá ảnh** nên ưu tiên precision. 10–14 cho kết quả y hệt trên calib và raw; 16 bắt thêm 1 cặp calib nhưng trên raw gộp nhầm 8 ảnh khác nhau (xem dưới); 20 làm EXACT tụt còn 1/3. Chọn 10: mép dưới của vùng an toàn. |
| `second_opinion.conf`   | 0.25     | 0.6            | MISSING 0.50 / 1.00 → 0.57 / 1.00 (8/8); WRONG_CLASS 0.56 / 0.83 → 0.62 / 0.83 (5/6); LOOSE_BOX 0.29 / 0.40 → 0.20 / 0.20 (1/5); FALSE_POS không đổi 0.31 / 1.00 (dùng `fp_conf`) | Mức cao nhất mà MISSING và WRONG_CLASS **chưa mất recall**; hàng đợi raw giảm 137 → 113 ảnh có cảnh báo. 0.7 làm MISSING tụt 7/8, 0.8 tụt 6/8. Cái giá: LOOSE_BOX recall giảm (calib chỉ 5 ca), và gate ra **Hold** (38/202 = 18.8% ảnh còn cảnh báo > 10%). |

**Chỗ calibration đánh lừa:** trên calib, `phash_dist` từ 2 đến 16 đều cho precision 1.00 và 16 có recall NEAR cao nhất (5/6), nên nhìn bảng sweep sẽ chọn 16. Chạy trên raw ở 16 thì số ảnh bị báo trùng/rò rỉ (không kể trùng byte) tăng 9 → 18. Đo lại 18 cặp bằng thước khác (dhash, tương quan ảnh xám 32×32): 10 cặp thật (9 cặp đã bắt ở mức 10, thêm `img_0084`) có tương quan ≥ 0.82, còn 8 cặp mới ở đúng phash 16 có tương quan ≤ 0.50 (vd. `img_0017` ảnh ngang 640×480 bị coi là trùng `test/test_071.jpg` ảnh dọc 400×600, tương quan −0.28). Tức là ở 16 pipeline sẽ xoá 8 ảnh tốt (6 bị gắn nhầm LEAK_TEST), chỉ để đổi lấy 1 cặp thật (`img_0084`/`img_0074`, phash 16, tương quan 0.82). Cặp này là **điểm mù đã biết**: nó nằm ở cùng khoảng cách với ảnh khác nhau nên không ngưỡng phash nào tách được. Tương tự, `second_opinion.conf = 0.8` sẽ cho **Release** (16/202 = 7.9%), nhưng trên calib bỏ sót 2/8 box thiếu: một Release nhờ hạ recall là Release giả, nên tôi không chọn.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Gate chặn đúng.** `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`: không có người duyệt nên 6/6 ảnh `MISSING_LABEL_FILE` vẫn chưa có nhãn → `kết luận: REWORK — còn 6 lỗi bắt buộc (ERROR) chưa sửa`, **mã thoát 20**, dòng log `KHÔNG xuất: còn lỗi bắt buộc (Rework)` và thư mục `work/exp_nb` không được tạo. Với ngân sách 80 (lần chạy chính), cả 6 ảnh này ở đầu hàng đợi (ưu tiên 10.0, `NEEDS_LABEL`), được người gán nên còn 0 lỗi bắt buộc → gate chuyển sang xét cảnh báo và ra Hold (38/202 = 18.8%).

**(b) Điểm mù** (bằng chứng từ calib, nơi có đáp án; ngưỡng đã chọn):
1. **Ảnh trùng biến đổi mạnh.** Bỏ sót 2/6 cặp gần trùng của calib: `calib_037` (mức biến đổi 3) và `calib_038` (mức 4). Trên raw, cặp `img_0084`/`img_0074` (tương quan ảnh xám 0.82, nhiều khả năng là bản cắt) có phash 16, đúng bằng khoảng cách của 8 cặp ảnh khác nhau, nên không ngưỡng phash nào tách được (xem mục 3).
2. **Gán thêm một nhãn sai lớp chồng lên nhãn đúng.** `calib_009` dòng 6 bị đổi truck→bus, nằm chồng dòng 4 (car) trên cùng chiếc xe (IoU 0.95). Model lớn nói car (conf 0.72) nên quy tắc "nhãn cùng lớp đã phủ vật → im lặng" bỏ qua, còn `DUP_BOX` chỉ so cùng lớp. Box bus sai lọt qua. Model lớn cũng không phân biệt chắc truck/bus/car: nó gọi chính chiếc xe này là car.
3. **Box lỏng khi model không thấy vật.** `POSSIBLE_LOOSE_BOX` bỏ sót 4/5 ca. `calib_006` model không có dự đoán nào; `calib_012` chỉ có dự đoán conf 0.15 và 0.12 < `conf` 0.6, nên không có dự đoán tin cậy để so. Ba ảnh này vẫn vào hàng đợi nhờ `POSSIBLE_FALSE_POS` (box phình ×1.5 làm IoU < 0.3), nhưng `calib_024` thì không có cờ ngữ nghĩa nào: box phình ×1.54 lọt hoàn toàn.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Colab T4, `yolo26n.pt`, 20 epoch, batch 16, imgsz 640, seed 0 và 1. Cùng val (`gold_val`, 40 ảnh) và cùng test (100 ảnh, 387 box). Chỉ khác dữ liệu train: `raw` 224 ảnh nhãn gốc, `clean` 202 ảnh của `clean_v1` (`manifest_sha1` và `config_sha1` trong `results/*.json` khớp bản export và config đã nộp). Bảng do `scripts/summarize_results.py` sinh:

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

**So với nhiễu:** chênh mAP50 (clean − raw) = **−0.025**, đúng bằng độ lệch chuẩn giữa 2 seed của clean (0.025). Hai seed clean cách nhau 0.035 (0.718 và 0.683), lớn hơn cả khoảng cách giữa seed tốt của clean và raw (0.726 − 0.718 = 0.008). Với 2 seed và 100 ảnh test, **chưa kết luận được** clean tốt hơn hay kém hơn raw. Điều trung thực có thể nói là: số liệu này **không** cho thấy làm sạch giúp tăng mAP.

**Theo lớp:** person gần như bằng nhau (raw 0.813/0.832, clean 0.816/0.830). Chênh lớn nhất ở truck: raw 0.657/0.640, clean 0.590/0.486, dù clean có **nhiều** box truck hơn (41 so với 32). Test chỉ có 24 box truck và 27 box bus, nên một vài box đoán sai đã đủ làm AP lớp đó dao động mạnh.

**Giả thuyết và cách kiểm:**
1. **Rò rỉ test thổi phồng raw.** `raw` còn 5 ảnh trùng ảnh test (`LEAK_TEST`: test_009, 033, 039, 044, 085), `clean` đã loại. Model raw đã "thấy" 5% ảnh test lúc train. *Kiểm:* đánh giá cả hai model trên test bỏ 5 ảnh đó; nếu khoảng cách thu hẹp thì một phần lợi thế của raw là giả.
2. **Nhãn truck/car của clean vẫn bẩn.** 38 ảnh chưa được người duyệt vẫn giữ nhãn máy, và `POSSIBLE_WRONG_CLASS` có điểm mù car/truck (mục 4, điểm mù 2; CVAT tìm thêm 3 ảnh nhầm truck mà pipeline không cờ). *Kiểm:* train thêm biến thể `oracle` (nhãn người, cùng ảnh với clean) làm chặn trên; nếu oracle cũng không hơn raw thì vấn đề nằm ở dữ liệu ít và test nhỏ, không phải ở nhãn.
3. **Ít dữ liệu hơn và nhiễu lớn.** Clean ít hơn 22 ảnh (−10%), và độ lệch giữa seed (đến 0.035 mAP50) cùng cỡ với hiệu ứng cần đo. *Kiểm:* chạy ≥ 5 seed mỗi biến thể và so khoảng tin cậy.

**Việc tiếp theo:** chạy lại với ≥ 5 seed và thêm biến thể `oracle`, đánh giá trên test bỏ 5 ảnh rò rỉ, rồi mới kết luận về tác dụng của làm sạch.

## 6. Quyết định và ghi chú AI

**(a) Quyết định: HOLD, không phát hành `clean_v1`.** Để thành Release cần người duyệt thêm ít nhất 18 trong 38 ảnh còn cảnh báo (xuống < 10% = dưới 21/202), theo thứ tự `05_review_queue.csv` từ `img_0210`. Không đi đường tắt bằng cách nâng `second_opinion.conf` lên 0.8: cách đó cho Release nhưng bỏ sót 2/8 box thiếu trên calib (mục 3). Các sửa tay trong CVAT (mục thưởng bên dưới) chưa nằm trong bản xuất.

**(b) Ghi chú AI** (Claude Code):
- *Prompt chính:* script kiểm box tràn theo đủ 4 ý của `docs/PROMPTING.md`; với 4 module, yêu cầu viết theo docstring + test có sẵn và giải thích từng dòng.
- *Cách kiểm:* đọc từng dòng (không xoá/ghi đè ngoài `ds`, ngưỡng lấy từ `cfg`), `pytest` 79/79, chạy `autofix` trên **bản sao** `data/raw` (lần 2 không sửa gì thêm), đối chiếu với calib và với lỗi tự thấy ở `img_0030`.
- *Một lần AI sai:* script `check_overflow.py` đầu tiên chết với `IndexError` khi chạy không tham số (AI chỉ thử với tham số). AI cũng khẳng định sai rằng cache không có dự đoán cho `img_0030` (vì tra khoá không có đuôi `.jpg`); tôi phát hiện khi chạy `second_opinion` trên raw.

**Thưởng — CVAT.** Task 25 ảnh (20 ảnh đầu `05_review_queue.csv` + 5 ảnh có `BOX_TINY`), nhãn import YOLO 1.1 từ `work/run/ds` sau `make run`. Lọc `width < 20` / `height < 20` và `label=="truck"`, sửa tay rồi export YOLO 1.1 và so từng box với nhãn pipeline (cùng box = IoU ≥ 0.9). Ảnh chụp: [bộ lọc width < 20](width_20.png), [lọc truck](label_truck.png), [thuộc tính can_review](can_review.png).

Kết quả so sánh (export CVAT vs pipeline): **13/25 ảnh** thay đổi, 131 box giữ nguyên, **31 box xoá** (30 box < 20 px + 1 truck 193×210 px ở img_0127), **2 box đổi lớp** truck → car (img_0078, img_0135), 0 box thêm.

| Ảnh | Box < 20 px xoá trong CVAT | `BOX_TINY` của pipeline (< 12 px, v3) |
|---|---|---|
| img_0020 / 0030 / 0053 / 0135 | 3 / 3 / 1 / 2 person (rộng 15–19 px) | 0 |
| img_0026 | 6 person | 1 (11×30 px) |
| img_0051 | 3 person | 1 (9×44 px) |
| img_0069 | 2 person | 1 (11×32 px) |
| img_0161 | 3 person | 3 |
| img_0183 | 1 person | 1 |
| img_0031 / 0078 / 0219 | 3 / 2 / 1 xe (cao 13–19 px) | 0 |

- Lọc < 20 px: **30 box / 13 ảnh**; `BOX_TINY` (ngưỡng 12 px của dự án) chỉ báo **7 box / 5 ảnh**, và cả 7 đều nằm trong 30 box CVAT xoá. 23 box còn lại rộng/cao 12–19 px: hợp lệ theo guideline 12 px, chỉ bị loại theo ngưỡng 20 px của slide. Ngưỡng là quy tắc dự án, không phải sự thật: xoá theo 20 px là bỏ luôn người ở xa (vd. 16×53 px có diện tích 848 px² > `min_area_px` 600).
- Nhầm lớp thấy bằng mắt: img_0078 và img_0135 (truck → car), img_0127 (1 truck sai, xoá). Pipeline **không** gắn `POSSIBLE_WRONG_CLASS` cho ảnh nào trong 3 ảnh này: img_0078 chỉ có `FALSE_POS`/`MISSING`, img_0127 `LOOSE_BOX`/`MISSING`, img_0135 không có cờ ngữ nghĩa nào (vào hàng đợi vì `NEEDS_LABEL`). Đây là bằng chứng thêm cho điểm mù 2 ở mục 4: nhầm car/truck mà model lớn cũng nhầm.
- `can_review`: người gán bật cờ này cho box mình không chắc (vật bị che, quá nhỏ, khó phân lớp) để người duyệt xem lại. Pipeline làm việc tương tự bằng các cảnh báo WARN (`BOX_TINY`, `POSSIBLE_*`) đưa ảnh vào `05_review_queue.csv` thay vì tự sửa.
- Các sửa trong CVAT chỉ nằm trong CVAT. `submission/export/clean_v1` vẫn là kết quả của pipeline, không chứa các sửa tay này.
