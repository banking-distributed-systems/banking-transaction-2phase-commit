# V-Bank 2PC — Two-Phase Commit Protocol

> **Phiên bản:** 1.0
> **Ngày:** 17/03/2026

---

## 1. Giới thiệu Two-Phase Commit

### 1.1. Mục đích

Two-Phase Commit (2PC) là giao thức phân tán đảm bảo **tính nguyên tử (atomicity)** cho các giao dịch liên quan đến nhiều database. Trong hệ thống V-Bank, 2PC đảm bảo:

- Tiền được trừ từ tài khoản người gửi **VÀ** cộng vào tài khoản người nhận
- Hoặc cả hai đều thành công, hoặc cả hai đều không thay đổi

### 1.2. Các thành phần

| Thành phần | Vai trò | Trong V-Bank |
|------------|---------|--------------|
| **Transaction Coordinator (TC)** | Điều phối toàn bộ giao dịch | Flask Server |
| **Participant** | Thực hiện giao dịch trên mỗi DB | Bank A, Bank B |
| **Resource Manager** | Quản lý XA transaction | MySQL |

---

## 2. Hoạt động của 2PC

### 2.1. Sơ đồ hai pha

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TWO-PHASE COMMIT                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────┐                                              │
│  │     TRANSACTION START    │                                              │
│  │    tx_id = VB0A1B2C3D4  │                                              │
│  │    xid = abc123...       │                                              │
│  └────────────┬────────────┘                                              │
│               │                                                            │
│               ▼                                                            │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │                      PHASE 1: PREPARE                            │    │
│  │                                                                   │    │
│  │    TC ──▶ Gửi PREPARE cho TẤT CẢ participants                  │    │
│  │                                                                   │    │
│  │    ┌──────────────┐          ┌──────────────┐                   │    │
│  │    │   Bank A     │          │   Bank B     │                   │    │
│  │    │              │          │              │                   │    │
│  │    │ XA START    │          │ XA START    │                   │    │
│  │    │ UPDATE bal  │          │ UPDATE bal  │                   │    │
│  │    │ XA END      │          │ XA END      │                   │    │
│  │    │ XA PREPARE  │          │ XA PREPARE  │                   │    │
│  │    │              │          │              │                   │    │
│  │    │ ✓ READY     │          │ ✓ READY     │                   │    │
│  │    └──────────────┘          └──────────────┘                   │    │
│  │                                                                   │    │
│  └────────────────────────┬──────────────────────────────────────────┘    │
│                           │                                               │
│                           │ Cả hai đều READY                             │
│                           ▼                                               │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │                      PHASE 2: COMMIT                             │    │
│  │                                                                   │    │
│  │    TC ──▶ Gửi COMMIT cho TẤT CẢ participants                    │    │
│  │                                                                   │    │
│  │    ┌──────────────┐          ┌──────────────┐                   │    │
│  │    │   Bank A     │          │   Bank B     │                   │    │
│  │    │              │          │              │                   │    │
│  │    │ XA COMMIT   │          │ XA COMMIT   │                   │    │
│  │    │              │          │              │                   │    │
│  │    │ ✓ COMMITTED │          │ ✓ COMMITTED │                   │    │
│  │    └──────────────┘          └──────────────┘                   │    │
│  │                                                                   │    │
│  └────────────────────────┬──────────────────────────────────────────┘    │
│                           │                                               │
│                           ▼                                               │
│  ┌─────────────────────────┐                                              │
│  │     TRANSACTION END      │                                              │
│  │    ✓ SUCCESS             │                                              │
│  └─────────────────────────┘                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2. Chi tiết từng bước

#### Phase 1: PREPARE

```
1. TC tạo xid (XA Transaction ID)
   xid = UUID.generate()

2. TC gửi PREPARE song song cho cả hai Bank:

   Bank A:
   ┌─────────────────────────────────────┐
   │ XA START 'xid'                       │
   │ UPDATE accounts SET balance = ...    │
   │ XA END 'xid'                        │
   │ XA PREPARE 'xid'                    │
   └─────────────────────────────────────┘

   Bank B:
   ┌─────────────────────────────────────┐
   │ XA START 'xid'                       │
   │ UPDATE accounts SET balance = ...    │
   │ XA END 'xid'                        │
   │ XA PREPARE 'xid'                    │
   └─────────────────────────────────────┘

3. Chờ phản hồi với timeout = 10 giây

4. Kết quả:
   - Cả hai READY    → Sang Phase 2
   - Một trong hai FAIL → ROLLBACK tất cả
   - Timeout          → ROLLBACK tất cả (Kịch bản 5)
```

#### Phase 2: COMMIT

```
1. TC gửi XA COMMIT cho Bank A (nguồn) trước
   XA COMMIT 'xid'

2. Log phase = 'COMMIT_A' (Bank A đã commit)

3. TC gửi XA COMMIT cho Bank B (đích)
   XA COMMIT 'xid'

4. Log phase = 'COMMITTED'

5. Lưu hóa đơn vào transaction_log

6. Trả response cho client
```

---

## 3. Trạng thái giao dịch

### 3.1. Transaction State Machine

```
                    ┌─────────────┐
                    │  PREPARING  │
                    │ (Bắt đầu)   │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
     ┌────────────┐ ┌───────────┐  ┌───────────┐
     │ PREPARED   │ │  TIMEOUT  │  │  ABORTED  │
     │(Thành công)│ │ (Quá chậm)│  │ (Lỗi P1)  │
     └─────┬──────┘ └─────┬─────┘  └───────────┘
           │              │
           │              │
           ▼              │
    ┌──────────────┐      │
    │ COMMITTING   │◀─────┘
    │ (Đang commit)│
    └──────┬───────┘
           │
           ├──────────────────────┐
           │                      │
           ▼                      ▼
    ┌───────────┐        ┌────────────┐
    │ COMMIT_A  │        │  ABORTED   │
    │(A đã com) │        │            │
    └─────┬─────┘        └────────────┘
           │
           │
           ▼
    ┌─────────────┐      ┌──────────────┐
    │  COMMITTED  │      │COMPENSATING  │
    │ (Hoàn tất)  │      │ (Đang hoàn)  │
    └─────────────┘      └───────┬───────┘
                                 │
                                 ▼
                        ┌───────────────┐
                        │  COMPENSATED  │
                        │ (Đã hoàn tiền)│
                        └───────────────┘
```

### 3.2. Phase Labels

| Phase | Label | Ý nghĩa |
|-------|-------|----------|
| `PREPARING` | Phase 1 ▶ | TC bắt đầu giao dịch |
| `PREPARED` | Phase 1 ✔ | Cả hai participant sẵn sàng |
| `COMMITTING` | Phase 2 ▶ | TC bắt đầu gửi COMMIT |
| `COMMIT_A` | Phase 2 ⚡ | Bank A đã COMMIT, Bank B chưa |
| `COMMITTED` | Phase 2 ✔ | Hoàn tất thành công |
| `ABORTED` | Phase * ✖ | Giao dịch bị hủy |
| `TIMEOUT` | Phase 1 ⏱ | Participant phản hồi quá chậm |
| `COMPENSATING` | Recover ↺ | Đang hoàn tiền cho Bank A |
| `COMPENSATED` | Recover ✔ | Hoàn tiền thành công |

---

## 4. XA Commands trong MySQL

### 4.1. Các lệnh XA

```sql
-- Bắt đầu XA transaction
XA START 'transaction_id';

-- Kết thúc phần thao tác dữ liệu
XA END 'transaction_id';

-- Chuẩn bị commit (Phase 1)
XA PREPARE 'transaction_id';

-- Commit (Phase 2)
XA COMMIT 'transaction_id';

-- Rollback
XA ROLLBACK 'transaction_id';

-- Kiểm tra các transaction đang trong trạng thái PREPARED
XA RECOVER;
```

### 4.2. Ví dụ thực tế

```sql
-- Bank A: Trừ tiền
XA START '0a1b2c3d4e5f6';
UPDATE accounts SET balance = balance - 500000 WHERE id = 1;
XA END '0a1b2c3d4e5f6';
XA PREPARE '0a1b2c3d4e5f6';

-- Bank B: Cộng tiền
XA START '0a1b2c3d4e5f6';
UPDATE accounts SET balance = balance + 500000 WHERE id = 2;
XA END '0a1b2c3d4e5f6';
XA PREPARE '0a1b2c3d4e5f6';

-- Commit
XA COMMIT '0a1b2c3d4e5f6';  -- Bank A
XA COMMIT '0a1b2c3d4e5f6';  -- Bank B
```

---

## 5. So sánh với các giao thức khác

### 5.1. 2PC vs 3PC

| Tiêu chí | 2PC | 3PC |
|----------|-----|-----|
| **Số pha** | 2 | 3 |
| **Độ phức tạp** | Đơn giản | Phức tạp hơn |
| **Blocking** | Có thể block nếu TC down | Ít khả năng block hơn |
| **Trong V-Bank** | ✓ Sử dụng | Chưa cần |

### 5.2. 2PC vs Saga Pattern

| Tiêu chí | 2PC | Saga |
|----------|-----|------|
| **Đảm bảo atomicity** | Hoàn toàn | Eventual consistency |
| **Latency** | Thấp | Cao hơn |
| **Phù hợp** | Giao dịch tài chính | Microservices |
| **Trong V-Bank** | ✓ Sử dụng | Không cần |

---

## 6. Threading trong V-Bank

### 6.1. Parallel PREPARE

```python
# Sử dụng ThreadPoolExecutor để PREPARE song song
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    future_from = executor.submit(xa_prepare_participant, from_config, xid, ...)
    future_to = executor.submit(xa_prepare_participant, to_config, xid, ...)

    done, pending = concurrent.futures.wait(
        [future_from, future_to],
        timeout=PREPARE_TIMEOUT
    )
```

### 6.2. Lợi ích

- Giảm thời gian chờ giữa hai Bank
- Phát hiện lỗi sớm hơn
- Timeout chính xác hơn

---

## 7. Best Practices

### 7.1. Trong implementation

| Practice | Lý do |
|----------|-------|
| Luôn log phase trước mỗi bước | Hỗ trợ recovery chính xác |
| Timeout cho Phase 1 | Tránh block vô hạn |
| Auto-recovery khi startup | Xử lý các giao dịch treo |
| Compensation cho Kịch bản 4 | Đảm bảo không mất tiền |

### 7.2. Trong vận hành

| Practice | Lý do |
|----------|-------|
| Monitor XA RECOVER thường xuyên | Phát hiện giao dịch treo |
| Alert khi timeout xảy ra | Cảnh báo sớm vấn đề |
| Backup transaction_log | Đảm bảo có dữ liệu recovery |

---

## 8. Related Documentation

- [PRD](./PRD.md)
- [Architecture](./ARCHITECTURE.md)
- [API](./API.md)
- [Error Handling](./ERROR-HANDLING.md)
- [Database](./DATABASE.md)
