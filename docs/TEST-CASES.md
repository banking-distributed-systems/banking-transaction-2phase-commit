# Test Case Guide - V-Bank 2PC

> **Phiên bản:** 2.0
> **Ngày cập nhật:** 18/03/2026
> **Dự án:** V-Bank 2PC - Banking Transaction with Two-Phase Commit

---

## Table of Contents

1. [Tổng quan](#1-tổng-quan)
2. [Test Cases cơ bản](#2-test-cases-cơ-bản)
3. [Test Toxics](#3-test-toxics)
4. [Test Scenarios](#4-test-scenarios)
5. [Hướng dẫn chi tiết](#5-hướng-dẫn-chi-tiết)
6. [Kịch bản 2PC](#6-kịch-bản-2pc)

---

## 1. Tổng quan

### 1.1 Mục đích

Test Case Guide này hướng dẫn chi tiết cách sử dụng script `test_toxiproxy.py` để test các kịch bản khác nhau trong hệ thống V-Bank 2PC.

### 1.2 Yêu cầu

Trước khi chạy test, cần đảm bảo:

1. **Docker** đang chạy
2. **Toxiproxy** đã khởi động:
   ```bash
   docker run -d -p 8474:8474 -p 8666:8666 --name toxiproxy ghcr.io/shopify/toxiproxy
   ```
3. **Backend** đã khởi động:
   ```bash
   cd backend
   python app.py
   ```
4. **Databases** đã khởi động:
   ```bash
   docker-compose up -d
   ```

### 1.3 Chạy Script

```bash
cd D:\Program\banking-transaction-2phase-commit
python test_toxiproxy.py
```

---

## 2. Test Cases cơ bản

### 2.1 Menu Test Cases

```
1. Health Check         - Kiểm tra kết nối
2. Get Accounts         - Lấy danh sách tài khoản
3. Login               - Đăng nhập
4. Transfer (bình thường)  - Chuyển tiền
5. Transfer với Toxics  - Chuyển tiền với network issue
```

### 2.2 Chi tiết từng Test

#### Test 1: Health Check

**Mục đích:** Kiểm tra kết nối cơ bản đến backend qua proxy

**Cách chạy:**
1. Chọn `A` để tạo proxy (nếu chưa có)
2. Chọn `1` để chạy Health Check

**Kết quả mong đợi:**

**Thành công:**
```
============================================================
TEST 1: Health Check
============================================================
✅ SUCCESS
Status: 200
Time: 0.05s
       Latency: Chưa cấu hình
       Timeout: Chưa cấu hình
{
  "status": "ok"
}
```

**Thất bại (Timeout):**
```
============================================================
TEST 1: Health Check
============================================================
❌ CLIENT TIMEOUT
Time: 30.02s
→ Client chờ vượt quá 30s
       Latency: Chưa cấu hình
       Timeout: 1000ms
```

**Thất bại (Connection Closed):**
```
============================================================
TEST 1: Health Check
============================================================
💣 CONNECTION CLOSED
Time: 2.51s
→ Proxy đã đóng connection (timeout toxic)
       Latency: Chưa cấu hình
       Timeout: 3000ms
```

---

#### Test 2: Get Accounts

**Mục đích:** Lấy danh sách tài khoản

**Cách chạy:**
1. Chọn `2`

**Kết quả mong đợi:**
```json
{
  "accounts": [
    {"account_number": "102938475612", "name": "Nguyen Van A", "balance": 100000},
    {"account_number": "203847569801", "name": "Le Thi B", "balance": 50000}
  ]
}
```

---

#### Test 3: Login

**Mục đích:** Test chức năng đăng nhập

**Cách chạy:**
1. Chọn `3`

**Dữ liệu test:**
```json
{
  "phone": "0901234567",
  "password": "123456"
}
```

---

#### Test 4: Transfer (bình thường)

**Mục đích:** Test chuyển tiền 2PC trong điều kiện bình thường

**Cách chạy:**
1. Chọn `4`

**Dữ liệu test:**
```json
{
  "from_account_number": "102938475612",
  "to_account_number": "203847569801",
  "amount": 10000,
  "description": "Test qua proxy"
}
```

**Kết quả mong đợi:**
```json
{
  "status": "success",
  "transaction_id": "VB...",
  "message": "Transfer thành công"
}
```

---

#### Test 5: Transfer với Toxics

**Mục đích:** Test chuyển tiền với network issues đang active

**Cách chạy:**
1. Thêm toxic (latency, timeout,...)
2. Chọn `5`

**Lưu ý:** Test này chỉ hoạt động khi có toxic đang active

---

## 3. Test Toxics

### 3.1 Menu Toxics

```
C. Thêm Latency (nhập ms)          - Network delay
D. Thêm Timeout (nhập ms)          - Backend timeout
L. Thêm Limit Data (Packet Loss)    - Response bị cắt
K. Thêm Close Stream (Server chết)  - Hard failure
B. Thêm Bandwidth (Slow network)    - Network chậm
P. Thêm Slicer (Random packet loss) - Packet loss ngẫu nhiên
F. Thêm CẢ Latency + Timeout        - Cả hai
E. Xóa tất cả Toxics               - Reset về normal
S. Xem thông tin Proxy & Toxics    - Xem trạng thái
```

### 3.2 Chi tiết từng Toxic

#### C. Thêm Latency

**Mục đích:** Mô phỏng network chậm

**Tham số:**
- `latency`: Thời gian delay (milliseconds)

**Ví dụ:**
```
Nhập latency (ms) (default: 1000): 5000
→ Response sẽ bị chậm 5 giây
```

**Tác động:**
- Request vẫn thành công (nếu < client timeout)
- Response bị delay

---

#### D. Thêm Timeout

**Mục đích:** Mô phỏng server không phản hồi

**Tham số:**
- `timeout`: Thời gian chờ tối đa (milliseconds)

**⚠️ QUAN TRỌNG:**
- Timeout phải **nhỏ hơn** thời gian backend xử lý để gây lỗi
- Backend xử lý khoảng 2 giây
- Nên dùng timeout < 2000ms để test timeout

**Ví dụ:**
```
Nhập timeout (ms) (default: 5000): 1000
→ Server chưa kịp phản hồi đã bị timeout
```

**Tác động:**
- Client nhận `ConnectionError` (KHÔNG phải Timeout exception)
- Connection bị đóng ngay lập tức

---

#### L. Thêm Limit Data (Packet Loss)

**Mục đích:** Mô phỏng response bị cắt

**Tham số:**
- `bytes`: Số bytes tối đa

**Ví dụ:**
```
Nhập số bytes giới hạn (default: 100): 50
→ Response bị cắt sau 50 bytes
```

**Tác động:**
- JSON parse error
- Response không hoàn chỉnh

**Cách xử lý:**
```python
try:
    data = res.json()
except ValueError:
    print("⚠️ Response bị cắt!")
    print(f"Raw: {res.text[:200]}")
```

---

#### K. Thêm Close Stream (Server chết)

**Mục đích:** Mô phỏng server crash/hard failure

**Tham số:** Không có

**Tác động:**
- Connection bị đóng ngay lập tức
- Client nhận `RemoteDisconnected`
- Dùng để test Kịch bản 4 (Partial Commit)

---

#### B. Thêm Bandwidth (Slow Network)

**Mục đích:** Mô phỏng network chậm thật

**Tham số:**
- `rate`: Tốc độ (bytes/giây)

**Ví dụ:**
```
Nhập bandwidth (bytes/giây) (default: 1024): 512
→ Download 512 bytes/giây
```

**Tác động:**
- Response được trả về chậm rãi
- Không phải delay cố định như latency

---

#### P. Thêm Slicer (Random Packet Loss)

**Mục đích:** Mô phỏng network instability

**Tham số:**
- `size`: Kích thước trung bình mỗi slice

**Tác động:**
- Response bị cắt ngẫu nhiên
- Realistic hơn limit_data

---

## 4. Test Scenarios

### 4.1 Menu Scenarios

```
R. Test Retry Logic (timeout → retry)              - Test retry khi fail
W. Test Fallback Data (API fail → dùng dự phòng) - Test fallback data
1. Scenario: Timeout → Retry → Success            - Auto scenario
2. Scenario: Partial Commit (Bank B chết)        - Auto scenario
```

### 4.2 Chi tiết

#### R. Test Retry Logic

**Mục đích:** Test cơ chế retry khi request thất bại

**Cách chạy:**
1. Thêm timeout toxic (D)
2. Chọn `R`
3. Nhập số retries và delay

**Kết quả:**
```
🔄 Attempt 1/3
❌ TIMEOUT sau 5.02s
⏳ Chờ 1s trước khi retry...

🔄 Attempt 2/3
❌ TIMEOUT sau 5.01s
⏳ Chờ 1s trước khi retry...

🔄 Attempt 3/3
❌ TIMEOUT sau 5.01s

❌ THẤT BẠI sau 3 attempts!
```

---

#### W. Test Fallback Data

**Mục đích:** Test cơ chế fallback khi API fail

**Cách chạy:**
1. Chọn `W`

**Kết quả:**
```
📊 Test 1: Gọi API bình thường...
✅ API Response:
   Status: 200
   Time: 0.05s

📊 Test 2: Fallback với dữ liệu mẫu (khi API fail)...
✅ Fallback Data (mock):
[
  {"account_number": "102938475612", "name": "Nguyen Van A", "balance": 100000},
  {"account_number": "203847569801", "name": "Le Thi B", "balance": 50000}
]
```

---

#### 1. Scenario: Timeout → Retry → Success

**Mục đích:** Tự động test kịch bản timeout rồi retry

**Cách chạy:**
1. Chọn `1`
2. Nhập timeout value và số retries
3. Script sẽ:
   - Thêm timeout toxic
   - Gọi API với retry
   - Xóa toxic
   - Hiển thị kết quả

---

#### 2. Scenario: Partial Commit (Bank B chết)

**Mục đích:** Test Kịch bản 4 của 2PC

**Cách chạy:**
1. Chọn `2`
2. Script sẽ:
   - Kiểm tra số dư trước
   - Thêm close_stream toxic (Bank B "chết")
   - Thử transfer (sẽ fail)
   - Xóa toxic
   - Kiểm tra số dư sau
   - Giải thích kết quả

**Kết quả:**
```
📊 KẾT QUẢ:
   → A không bị trừ tiền (rollback)
   → B không nhận được tiền
   → Giao dịch bị hủy (partial commit failure)
```

---

## 5. Hướng dẫn chi tiết

### 5.1 Test Flow hoàn chỉnh

#### Bước 1: Khởi động Services

```bash
# 1. Khởi động Docker
docker-compose up -d

# 2. Khởi động Toxiproxy
docker run -d -p 8474:8474 -p 8666:8666 --name toxiproxy ghcr.io/shopify/toxiproxy

# 3. Khởi động Backend
cd backend
python app.py
```

#### Bước 2: Chạy Script

```bash
python test_toxiproxy.py
```

#### Bước 3: Tạo Proxy

```
Chọn: A
→ Tạo proxy vbank_api
```

#### Bước 4: Kiểm tra Services

```
Chọn: 7
→ Kiểm tra Backend, Toxiproxy, Proxy
```

#### Bước 5: Chạy Test

```
1. Health Check (1)
2. Get Accounts (2)
3. Transfer (4)
```

#### Bước 6: Thêm Toxic và Test

```
C. Thêm Latency → 5000ms
1. Health Check → Xem kết quả delay

E. Xóa tất cả Toxics

D. Thêm Timeout → 1000ms
1. Health Check → Xem kết quả timeout

E. Xóa tất cả Toxics
```

### 5.2 Best Practices

1. **Luôn xóa toxic sau khi test**
   - Chọn `E` để xóa tất cả
   - Tránh ảnh hưởng test khác

2. **Kiểm tra services trước khi test**
   - Chọn `7` để kiểm tra
   - Đảm bảo mọi thứ đang chạy

3. **Test theo thứ tự**
   - Test cơ bản trước (1-5)
   - Rồi mới test với toxics
   - Cuối cùng là scenarios

4. **Ghi lại kết quả**
   - Chụp màn hình kết quả
   - So sánh với expected results

---

## 6. Kịch bản 2PC

### 6.1 Các Kịch bản Lỗi 2PC

| Kịch bản | Mô tả | Toxic dùng |
|-----------|--------|-------------|
| KB 1 | TC sập sau PREPARE | Timeout |
| KB 2 | TC sập ở PREPARING | Timeout |
| KB 3 | TC sập đang COMMITTING | Close Stream |
| KB 4 | Bank A commit, Bank B fail | Close Stream |
| KB 5 | Timeout ở Phase 1 | Timeout |

### 6.2 Mapping Test Cases

#### Kịch bản 4: Partial Commit Failure

**Mục đích:** Bank A commit thành công, Bank B fail

**Cách test:**
1. `K` - Thêm Close Stream
2. `4` - Chạy Transfer
3. `E` - Xóa toxic
4. Kiểm tra số dư

**Kết quả mong đợi:**
- Bank A: Không thay đổi (rollback)
- Bank B: Không thay đổi (fail)
- Transaction: FAILED

---

#### Kịch bản 5: Timeout ở Phase 1

**Mục đích:** Bank B không phản hồi trong thời gian quy định

**Cách test:**
1. `D` - Thêm Timeout
2. Nhập giá trị < 2000ms
3. `4` - Chạy Transfer

**Kết quả mong đợi:**
- Client nhận ConnectionError
- Transaction: TIMEOUT
- Bank A: Rollback

---

### 6.3 Quick Reference

| Mục đích | Menu | Tham số |
|-----------|------|---------|
| Test bình thường | 1-5 | Không |
| Network delay | C | latency (ms) |
| Server timeout | D | timeout (ms) |
| Packet loss | L | bytes |
| Server crash | K | - |
| Slow network | B | rate (bytes/s) |
| Reset | E | - |

---

## Phụ lục

### A. Error Messages

| Message | Ý nghĩa |
|---------|----------|
| `✅ SUCCESS` | Request thành công |
| `❌ CLIENT TIMEOUT` | Client timeout (vượt REQUEST_TIMEOUT) |
| `💣 CONNECTION CLOSED` | Proxy đóng connection (timeout toxic) |
| `❌ UNKNOWN ERROR` | Lỗi không xác định |

### B. Status Codes

| Code | Ý nghĩa |
|------|----------|
| 200 | OK |
| 400 | Bad Request |
| 500 | Internal Server Error |
| 502 | Bad Gateway |

### C. Cấu hình mặc định

```python
API_TIMEOUT = 5           # Timeout cho API Toxiproxy
REQUEST_TIMEOUT = 30      # Timeout cho Client request
DEFAULT_LATENCY = 1000   # 1 giây
DEFAULT_TIMEOUT = 5000   # 5 giây
```

---

## Tài liệu liên quan

- [Toxiproxy Documentation](./TOXIPROXY.md)
- [2PC Protocol](./2PC-PROTOCOL.md)
- [Error Handling](./ERROR-HANDLING.md)
- [Architecture](./ARCHITECTURE.md)

---

> **Ngày cập nhật:** 18/03/2026
> **Phiên bản:** 2.0
> **Tác giả:** V-Bank Development Team
