# Dựng và kiểm tra dashboard

[`../config/dashboard.yaml`](../config/dashboard.yaml) là contract chấm điểm, không phụ thuộc việc bạn dựng dashboard trong Langfuse hay một công cụ local. File này quy định đúng nguồn dữ liệu, phép tổng hợp, đơn vị và threshold cho sáu panel.

Trường `query` trong YAML là pseudocode mô tả phép tính, không phải câu lệnh để copy nguyên vào mọi công cụ. Bạn chuyển cùng logic đó sang cú pháp của công cụ đã chọn.

## Mapping dữ liệu

| Panel | Event/field | Phép tổng hợp |
|---|---|---|
| Latency | `response_sent.latency_ms/ttft_ms` | latency P50/P95/P99 và TTFT P95 |
| Traffic | `request_received` | count, request/phút |
| Errors | `request_received`, `request_failed`, `error_type`, `tool_success` | error rate, breakdown và retrieval success |
| Cost | `response_sent.cost_usd` | tổng theo phút và toàn cửa sổ |
| Tokens | `response_sent.tokens_in/tokens_out` | tổng theo từng field |
| Quality | `response_sent.quality_score` | mean |

Giữ time range mặc định 60 phút, refresh 30 giây và hiển thị threshold/SLO line. Giá trị chính xác nằm trong `config/dashboard.yaml`; không tự đổi contract chỉ để ảnh dashboard đẹp hơn.

## Cách dựng

### Dashboard HTML có sẵn trong repo

Từ môi trường đã cài `requirements.txt`, tạo trang sáu panel:

```bash
python scripts/build_dashboard.py
```

Mở `submission/evidence/dashboard.html` trong trình duyệt. Lệnh dùng 60 phút
tính đến hiện tại; chạy lại sau mỗi load test để cập nhật trang. Với log lịch
sử, chọn chính xác cửa sổ cần chụp:

```bash
python scripts/build_dashboard.py --end 2026-09-29T17:00:00Z
```

Trang thể hiện tên, đơn vị, khoảng thời gian, giá trị tổng hợp và đường đỏ
threshold ở cả sáu panel. Cost và token dùng đường lũy kế trong cửa sổ để
threshold tổng có cùng đơn vị; error breakdown và retrieval success nằm trong
panel Errors. Nếu cửa sổ không có mẫu, trang hiển thị `—` thay vì số 0 giả.
Lưu thêm ảnh màn hình `11-dashboard-overview.png` để đáp ứng evidence chấm điểm.

### Công cụ khác

1. Hoàn thiện logging/PII và chạy API.
2. Chạy `python scripts/load_test.py --concurrency 5` để tạo baseline.
3. Dùng `data/logs.jsonl` làm nguồn chuẩn để tạo đúng sáu panel bằng Streamlit, notebook, Grafana hoặc công cụ tương đương. Langfuse vẫn là nơi mở trace/prompt version để điều tra sâu.
4. Đặt tên panel, đơn vị và threshold giống contract.
5. Chạy validator:

```bash
python scripts/validate_dashboard.py
```

Validator kiểm tra cấu trúc contract; nó không thể chứng minh biểu đồ trong ảnh dùng đúng dữ liệu. Evidence runtime vẫn bắt buộc.

## Cách kiểm tra runtime

1. Lưu ảnh baseline và giá trị P95/error/cost hiện tại.
2. Bật một incident practice, ví dụ `python scripts/inject_incident.py --scenario rag_slow`.
3. Chạy lại load test với cùng input và concurrency.
4. Xác nhận panel liên quan thay đổi theo đúng hướng; với `rag_slow`, P95 phải tăng rõ ràng.
5. Lọc log chậm, lấy correlation ID rồi mở trace có cùng ID.
6. Tắt incident bằng `python scripts/inject_incident.py --scenario rag_slow --disable`.

Ảnh dashboard phải nhìn được tên panel, time range, đơn vị và threshold. Báo cáo phải dẫn lại trace ID hoặc log line dùng để giải thích thay đổi.
