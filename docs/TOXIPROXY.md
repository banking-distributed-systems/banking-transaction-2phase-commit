# Toxiproxy Documentation

> **Phiên bản:** 2.0
> **Ngày cập nhật:** 18/03/2026
> **Dự án:** V-Bank 2PC - Banking Transaction with Two-Phase Commit

---

## Table of Contents

1. [Tổng quan về Toxiproxy](#1-tổng-quan-về-toxiproxy)
2. [Các loại Toxic](#2-các-loại-toxic)
3. [Kiến trúc hoạt động](#3-kiến-trúc-hoạt-động)
4. [Cấu hình Proxy](#4-cấu-hình-proxy)
5. [Toxiproxy API](#5-toxiproxy-api)
6. [Test Script](#6-test-script)
7. [Test Cases](#7-test-cases)
8. [Kịch bản 2PC với Toxiproxy](#8-kịch-bản-2pc-với-toxiproxy)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Tổng quan về Toxiproxy

### 1.1 Toxiproxy là gì?

**Toxiproxy** là một proxy network được phát triển bởi Shopify, cho phép mô phỏng các tình huống mạng không ổn định một cách có kiểm soát. Trong môi trường production, network có thể gặp nhiều vấn đề như:

- Latency (độ trễ mạng)
- Timeout (hết thời gian chờ)
- Packet Loss (mất gói tin)
- Connection reset (reset kết nối)

Toxiproxy giúp chúng ta **simulate** (mô phỏng) các tình huống này mà không cần can thiệp vào hệ thống thực.

### 1.2 Tại sao cần Toxiproxy trong V-Bank 2PC?

Trong hệ thống **V-Bank 2PC**, giao dịch chuyển tiền giữa hai ngân hàng (Bank A và Bank B) có thể gặp nhiều tình huống lỗi network:

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Client    │────────▶│  Toxiproxy  │────────▶│   Backend   │
│  (V-Bank)   │         │  (Proxy)    │         │  (Server)   │
└─────────────┘         └─────────────┘         └─────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Toxics (Network   │
                    │   Simulations)      │
                    │   - Latency        │
                    │   - Timeout        │
                    │   - Packet Loss    │
                    │   - Close Stream   │
                    └─────────────────────┘
```

### 1.3 Mục đích sử dụng

| Mục đích | Mô tả |
|-----------|-------|
| **Test Failure Scenarios** | Mô phỏng các kịch bản lỗi (timeout, network failure) |
| **2PC Protocol Testing** | Test giao thức Two-Phase Commit trong điều kiện mạng xấu |
| **Resilience Testing** | Test khả năng phục hồi của hệ thống |
| **Performance Testing** | Test hiệu năng với network chậm |

---

## 2. Các loại Toxic

> **⚠️ QUAN TRỌNG:** Đây là các thành phần cốt lõi của Toxiproxy, mỗi loại có cách hoạt động và mục đích khác nhau.

### 2.1 Latency (Độ trễ mạng)

```json
{
  "name": "latency_1234567890",
  "type": "latency",
  "stream": "downstream",
  "attributes": {
    "latency": 5000
  }
}
```

| Thuộc tính | Giá trị | Mô tả |
|------------|---------|--------|
| `type` | `latency` | Loại toxic |
| `stream` | `downstream` | Tác động lên response từ server về client |
| `latency` | `5000` | Độ trễ tính bằng **milliseconds** |

**Nguyên lý hoạt động:**
```
Client ──────▶ Request ──────▶ Server
                (normal)

Server ──────▶ Response ◀───── Client
                +5000ms delay
```

**Trong 2PC:**
- Dùng để mô phỏng **network chậm** giữa các ngân hàng
- Test xem hệ thống có xử lý được delay hay không
- **Không ảnh hưởng** đến timeout (timeout đo ở upstream)

---

### 2.2 Timeout (Hết thời gian chờ)

```json
{
  "name": "timeout_1234567890",
  "type": "timeout",
  "stream": "upstream",
  "attributes": {
    "timeout": 3000
  }
}
```

| Thuộc tính | Giá trị | Mô tả |
|------------|---------|--------|
| `type` | `timeout` | Loại toxic |
| `stream` | `upstream` | **QUAN TRỌNG:** Phải là `upstream` |
| `timeout` | `3000` | Thời gian chờ tính bằng **milliseconds** |

> **⚠️ QUAN TRỌNG NHẤT:**
> - `timeout` toxic chỉ áp dụng cho **upstream** (từ client đến server)
> - Nó đo thời gian server **BẮT ĐẦU** phản hồi
> - **KHÔNG phụ thuộc** vào latency (latency ở downstream)

**Nguyên lý hoạt động:**
```
Client ──────▶ Request ──────▶ Server
                ↓
          [Proxy đợi max 3s
           để server bắt đầu
           phản hồi]
                ↓
        Nếu > 3s: ĐÓNG CONNECTION
        (Client nhận ConnectionError)
```

**Trong 2PC:**
- Dùng để mô phỏng **Bank B không phản hồi** trong Phase 1
- Test xử lý Kịch bản 4, 5 của 2PC
- Kết quả: Client nhận `ConnectionError` (KHÔNG phải `Timeout`)

---

### 2.3 Limit Data (Cắt dữ liệu / Packet Loss)

```json
{
  "name": "limit_data_1234567890",
  "type": "limit_data",
  "stream": "downstream",
  "attributes": {
    "bytes": 100
  }
}
```

| Thuộc tính | Giá trị | Mô tả |
|------------|---------|--------|
| `type` | `limit_data` | Loại toxic |
| `stream` | `downstream` | Tác động lên response |
| `bytes` | `100` | Số bytes tối đa được trả về |

**Nguyên lý hoạt động:**
```
Server ──────▶ Full Response (1000 bytes)
                   │
                   ▼
            [Proxy cắt sau 100 bytes]
                   │
                   ▼
            Client nhận 100 bytes (truncated)
                   │
                   ▼
            ❌ JSON Parse Error
```

**Trong 2PC:**
- Test xử lý khi response bị cắt giữa chừng
- Test khả năng phục hồi khi nhận dữ liệu không hoàn chỉnh
- **Cẩn thận:** Có thể gây crash nếu không handle

---

### 2.4 Close Stream (Server chết / Hard Failure)

```json
{
  "name": "close_stream_1234567890",
  "type": "close_stream",
  "stream": "downstream",
  "attributes": {}
}
```

| Thuộc tính | Giá trị | Mô tả |
|------------|---------|--------|
| `type` | `close_stream` | Loại toxic |
| `stream` | `downstream` | Tác động lên response |
| `attributes` | `{}` | Không cần thuộc tính |

**Nguyên lý hoạt động:**
```
Client ──────▶ Request ──────▶ Server
                   │
                   ▼
            [Proxy ĐÓNG NGAY
             connection]
                   │
                   ▼
            Client nhận:
            RemoteDisconnected
            (Server "chết")
```

**Trong 2PC:**
- **RẤT QUAN TRỌNG** cho Kịch bản 4: Partial Commit
- Mô phỏng Bank B **crash** giữa quá trình commit
- Test cơ chế **compensation/rollback**

---

### 2.5 Bandwidth (Giới hạn băng thông)

```json
{
  "name": "bandwidth_1234567890",
  "type": "bandwidth",
  "stream": "downstream",
  "attributes": {
    "rate": 1024
  }
}
```

| Thuộc tính | Giá trị | Mô tả |
|------------|---------|--------|
| `type` | `bandwidth` | Loại toxic |
| `stream` | `downstream` | Tác động lên response |
| `rate` | `1024` | Tốc độ bytes/giây |

**Nguyên lý hoạt động:**
```
Server ──────▶ Response (1MB)
                   │
                   ▼
            [Proxy giới hạn 1KB/s]
                   │
                   ▼
            Client nhận chậm rãi
            (~16 giây cho 16KB)
```

**Trong 2PC:**
- Test với network chậm thật (không phải delay cố định)
- Test timeout khi bandwidth thấp

---

### 2.6 Slicer (Cắt ngẫu nhiên)

```json
{
  "name": "slicer_1234567890",
  "type": "slicer",
  "stream": "downstream",
  "attributes": {
    "size": 100
  }
}
```

| Thuộc tính | Giá trị | Mô tả |
|------------|---------|--------|
| `type` | `slicer` | Loại toxic |
| `stream` | `downstream` | Tác động lên response |
| `size` | `100` | Kích thước trung bình mỗi slice |

**Nguyên lý hoạt động:**
- Cắt response thành các **packages ngẫu nhiên**
- Realistic hơn `limit_data` (cắt cố định)
- Mô phỏng **network instability** thực tế

---

## 3. Kiến trúc hoạt động

### 3.1 Flow hoạt động

```
┌──────────────────────────────────────────────────────────────────┐
│                        TOXIPROXY ARCHITECTURE                     │
└──────────────────────────────────────────────────────────────────┘

    ┌──────────┐                    ┌──────────┐
    │  Client  │                    │  Server  │
    │  (V-App) │                    │ (Backend)│
    └────┬─────┘                    └────┬─────┘
         │                                 │
         │  1. Request                    │
         ├────────────────────────────────▶│
         │                                 │
         │                    ┌────────────┴────────────┐
         │                    │   PROXY (Port 8666)    │
         │                    │                         │
         │                    │  ┌─────────────────┐   │
         │                    │  │  Toxics Chain   │   │
         │                    │  │                 │   │
         │                    │  │ [Latency] ──▶   │   │
         │                    │  │ [Timeout] ──▶   │   │
         │                    │  │ [LimitData] ──▶ │   │
         │                    │  │ [CloseStream] ─▶│   │
         │                    │  └─────────────────┘   │
         │                    └────────────┬────────────┘
         │                                 │
         │  2. Response (có/ko toxic)      │
         ◀────────────────────────────────┤
         │                                 │
```

### 3.2 Stream: Upstream vs Downstream

```
┌─────────────────────────────────────────────────────────────────┐
│                    UPSTREAM vs DOWNSTREAM                        │
└─────────────────────────────────────────────────────────────────┘

        UPSTREAM (client ──▶ server)
        ═══════════════════════════
        - Request đi từ Client đến Server
        - Đo thời gian Server BẮT ĐẦU phản hồi
        - Dùng cho: timeout toxic

        DOWNSTREAM (server ──▶ client)
        ═════════════════════════════
        - Response đi từ Server về Client
        - Đo thời gian Client NHẬN đủ dữ liệu
        - Dùng cho: latency, limit_data, bandwidth, slicer, close_stream


    Client                    Proxy                  Server
       │                        │                        │
       │──── UPSTREAM ─────────▶│──── UPSTREAM ────────▶│
       │    (Request)           │    (Request)         │
       │                        │                        │
       │◀─── DOWNSTREAM ───────│◀─── DOWNSTREAM ──────│
       │    (Response)          │    (Response)        │
```

### 3.3 Timeout vs Latency (QUAN TRỌNG)

```
┌─────────────────────────────────────────────────────────────────┐
│              TIMEOUT (upstream) vs LATENCY (downstream)         │
└─────────────────────────────────────────────────────────────────┘

    TIMEOUT (upstream):
    ═════════════════

    Client ────▶ [Chờ server BẮT ĐẦU phản hồi] ────▶ Server
                    │
                    │ ⏱ max 3000ms
                    │
                    └─ Nếu quá ──▶ ĐÓNG CONNECTION

    → KHÔNG phụ thuộc latency
    → Chỉ quan tâm: Server có bắt đầu phản hồi hay không?

    LATENCY (downstream):
    ════════════════════

    Server ───▶ [Thêm delay] ────▶ Client
                   │
                   │ ⏱ +3000ms
                   │
                   └─ Client nhận chậm hơn 3000ms

    → Client vẫn nhận đủ dữ liệu
    → Request vẫn "thành công" (chậm)
```

---

## 4. Cấu hình Proxy

### 4.1 Tạo Proxy

```json
POST http://localhost:8474/proxies
Content-Type: application/json

{
  "name": "vbank_api",
  "listen": "0.0.0.0:8666",
  "upstream": "host.docker.internal:5000",
  "enabled": true
}
```

| Thuộc tính | Giá trị | Mô tả |
|------------|---------|--------|
| `name` | `vbank_api` | Tên proxy (duy nhất) |
| `listen` | `0.0.0.0:8666` | Port để client kết nối |
| `upstream` | `host.docker.internal:5000` | Địa chỉ backend thực |
| `enabled` | `true` | Bật/tắt proxy |

### 4.2 Kiểm tra Proxy

```bash
GET http://localhost:8474/proxies/vbank_api
```

Response:
```json
{
  "name": "vbank_api",
  "listen": "0.0.0.0:8666",
  "upstream": "host.docker.internal:5000",
  "enabled": true,
  "toxics": []
}
```

### 4.3 Xóa Proxy

```bash
DELETE http://localhost:8474/proxies/vbank_api
```

---

## 5. Toxiproxy API

### 5.1 Thêm Toxic

```bash
POST http://localhost:8474/proxies/vbank_api/toxics
Content-Type: application/json

{
  "name": "latency_123",
  "type": "latency",
  "stream": "downstream",
  "attributes": {
    "latency": 5000
  }
}
```

### 5.2 Xem Toxics

```bash
GET http://localhost:8474/proxies/vbank_api/toxics
```

### 5.3 Xóa Toxic

```bash
DELETE http://localhost:8474/proxies/vbank_api/toxics/latency_123
```

### 5.4 Xóa tất cả Toxics

```bash
DELETE http://localhost:8474/proxies/vbank_api/toxics
```

---

## 6. Test Script

### 6.1 Giới thiệu

Test script `test_toxiproxy.py` được viết để tự động hóa việc test với Toxiproxy. Script cung cấp:

- Menu tương tác để chọn test
- Tự động thêm/xóa toxics
- Chi tiết lỗi (timeout, connection error,...)
- Auto scenario tests

### 6.2 Chạy Script

```bash
cd D:\Program\banking-transaction-2phase-commit
python test_toxiproxy.py
```

### 6.3 Menu chính

```
CHỌN TEST CASE:
══════════════════════════════════════════════════════════════
1. Health Check
2. Get Accounts
3. Login
4. Transfer (bình thường)
5. Transfer với Toxics hiện tại
---
A. Tạo Proxy
B. Xóa Proxy
C. Thêm Latency (nhập ms)
D. Thêm Timeout (nhập ms)
L. Thêm Limit Data (Packet Loss)
K. Thêm Close Stream (Server chết)
B. Thêm Bandwidth (Slow network)
P. Thêm Slicer (Random packet loss)
F. Thêm CẢ Latency + Timeout
S. Xem thông tin Proxy & Toxics
E. Xóa tất cả Toxics
---
R. Test Retry Logic (timeout → retry)
W. Test Fallback Data (API fail → dùng dự phòng)
---
1. Scenario: Timeout → Retry → Success
2. Scenario: Partial Commit (Bank B chết)
---
T. DEBUG CHUYÊN SÂU Timeout (theo dõi từng bước)
G. Cấu hình giá trị mặc định
7. KIỂM TRA SERVICES
0. Thoát
```

### 6.4 Cấu hình mặc định

```python
API_TIMEOUT = 5           # Timeout cho API Toxiproxy (tạo proxy, thêm toxic)
REQUEST_TIMEOUT = 30      # Timeout cho request từ Client

DEFAULT_LATENCY = 1000    # 1 giây - Network delay
DEFAULT_TIMEOUT = 5000   # 5 giây - Backend timeout
```

---

## 7. Test Cases

### 7.1 Test 1: Health Check

**Mục đích:** Kiểm tra kết nối cơ bản qua proxy

**Cách chạy:**
1. Chọn `A` để tạo proxy
2. Chọn `1` để test Health Check

**Kết quả mong đợi:**
```
============================================================
TEST 1: Health Check
============================================================
✅ SUCCESS
Status: 200
Time: 0.05s
       Latency: Chưa cấu hình
       Timeout: Chưa cấu hình
```

### 7.2 Test 2: Latency (Network chậm)

**Mục đích:** Mô phỏng network delay

**Cách chạy:**
1. Chọn `C` để thêm Latency
2. Nhập `5000` (5 giây)
3. Chọn `1` để test

**Kết quả mong đợi:**
```
✅ SUCCESS
Time: 5.05s
       Latency: 5000ms
       Timeout: Chưa cấu hình
```

### 7.3 Test 3: Timeout (Server không phản hồi)

**Mục đích:** Mô phỏng server không phản hồi

**Cách chạy:**
1. Chọn `D` để thêm Timeout
2. Nhập `1000` (1 giây - nhỏ hơn backend xử lý)
3. Chọn `1` để test

**Kết quả mong đợi:**
```
💣 CONNECTION CLOSED
Time: 1.02s
→ Proxy đã đóng connection (timeout toxic)
       Latency: Chưa cấu hình
       Timeout: 1000ms
```

### 7.4 Test 4: Limit Data (Response bị cắt)

**Mục đích:** Mô phỏng packet loss, response bị cắt

**Cách chạy:**
1. Chọn `L` để thêm Limit Data
2. Nhập `50` bytes
3. Chọn `2` để test Get Accounts

**Kết quả mong đợi:**
```
⚠️ Response bị cắt (truncated), không parse được JSON!
   Raw response (first 500 chars): {"accounts":[...
```

### 7.5 Test 5: Close Stream (Server chết)

**Mục đích:** Mô phỏng server crash

**Cách chạy:**
1. Chọn `K` để thêm Close Stream
2. Chọn `1` để test

**Kết quả mong đợi:**
```
💣 CONNECTION CLOSED
Time: 0.05s
→ Proxy đã đóng connection (timeout toxic)
```

---

## 8. Kịch bản 2PC với Toxiproxy

### 8.1 Kịch bản 4: Partial Commit Failure

**Mô tả:** Bank A commit thành công, nhưng Bank B fail

**Cách chạy:**
1. Chọn `2` để chạy Scenario: Partial Commit

**Flow:**
```
1. Prepare: Client gửi PREPARE đến Bank A và Bank B
           │
2. Bank A: ✅ PREPARE OK (commit)
           │
3. Bank B: ❌ CLOSE STREAM (simulate crash)
           │
4. Commit: Client nhận lỗi từ Bank B
           │
5. Rollback: Client rollback Bank A
             (compensation transaction)
```

### 8.2 Kịch bản 5: Timeout ở Phase 1

**Mô tả:** Bank B không phản hồi trong thời gian quy định

**Cách chạy:**
1. Chọn `D` để thêm Timeout
2. Nhập `1000` (1 giây - nhỏ hơn backend xử lý ~2 giây)
3. Chọn `4` để test Transfer

**Flow:**
```
1. Prepare: Client gửi PREPARE đến Bank B
           │
2. Bank B: ⏳ Đang xử lý... (> 1 giây)
           │
3. Timeout: Proxy đóng connection
           │
4. Rollback: Client rollback Bank A
             (vì Bank B timeout)
```

### 8.3 Scenario: Retry Logic

**Mục đích:** Test retry khi timeout

**Cách chạy:**
1. Chọn `D` để thêm Timeout (ví dụ 2000ms)
2. Chọn `R` để test Retry Logic
3. Nhập số retries (3)
4. Quan sát: Request sẽ fail, retry, có thể thành công sau khi xóa toxic

---

## 9. Troubleshooting

### 9.1 Proxy không hoạt động

**Vấn đề:** Không thể kết nối qua proxy

**Giải pháp:**
```bash
# 1. Kiểm tra Toxiproxy đang chạy
docker ps | findstr toxiproxy

# 2. Xem logs
docker logs toxiproxy

# 3. Kiểm tra proxy trong Toxiproxy
curl http://localhost:8474/proxies
```

### 9.2 Backend không connect được

**Vấn đề:** Proxy không thể kết nối đến backend

**Giải pháp:**
```bash
# 1. Kiểm tra backend đang chạy
curl http://localhost:5000/api/health

# 2. Kiểm tra upstream trong proxy
curl http://localhost:8474/proxies/vbank_api
```

### 9.3 Toxic không hoạt động

**Vấn đề:** Thêm toxic nhưng không thấy hiệu lực

**Giải pháp:**
```bash
# 1. Kiểm tra toxics đã được thêm
curl http://localhost:8474/proxies/vbank_api/toxics

# 2. Xóa tất cả và thêm lại
curl -X DELETE http://localhost:8474/proxies/vbank_api/toxics
```

### 9.4 JSON Parse Error

**Vấn đề:** Response bị cắt, không parse được JSON

**Giải pháp:**
- Đây là behavior bình thường khi dùng `limit_data` toxic
- Xử lý bằng cách thêm try-catch:
```python
try:
    data = res.json()
except ValueError:
    print("⚠️ Response bị cắt!")
    print(f"Raw: {res.text[:200]}")
```

---

## Phụ lục

### A. Docker Commands

```bash
# Khởi động Toxiproxy
docker run -d -p 8474:8474 -p 8666:8666 --name toxiproxy ghcr.io/shopify/toxiproxy

# Dừng Toxiproxy
docker stop toxiproxy

# Xóa Toxiproxy
docker rm toxiproxy
```

### B. Quick Reference

| Action | Command |
|--------|---------|
| Tạo proxy | `POST /proxies` |
| Thêm latency | `POST /proxies/vbank_api/toxics` `{type: "latency", stream: "downstream", latency: 5000}` |
| Thêm timeout | `POST /proxies/vbank_api/toxics` `{type: "timeout", stream: "upstream", timeout: 3000}` |
| Xem toxics | `GET /proxies/vbank_api/toxics` |
| Xóa toxic | `DELETE /proxies/vbank_api/toxics/toxic_name` |
| Xóa all | `DELETE /proxies/vbank_api/toxics` |

---

## Tài liệu tham khảo

- [Toxiproxy GitHub](https://github.com/Shopify/toxiproxy)
- [Toxiproxy Documentation](https://github.com/Shopify/toxiproxy/blob/main/docs.md)
- [V-Bank 2PC Architecture](./ARCHITECTURE.md)
- [2PC Protocol](./2PC-PROTOCOL.md)
- [Error Handling](./ERROR-HANDLING.md)

---

> **Ngày cập nhật:** 18/03/2026
> **Phiên bản:** 2.0
> **Tác giả:** V-Bank Development Team
