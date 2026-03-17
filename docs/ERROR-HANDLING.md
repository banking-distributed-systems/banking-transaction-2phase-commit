# V-Bank 2PC — Error Handling & Recovery

> **Phiên bản:** 1.0
> **Ngày:** 17/03/2026

---

## 1. Tổng quan

Hệ thống V-Bank 2PC xử lý các kịch bản lỗi có thể xảy ra trong giao dịch phân tán. Mục tiêu là **không bao giờ mất tiền** dù bất kỳ lỗi nào xảy ra.

---

## 2. Các kịch bản lỗi

### 2.1. Ma trận kịch bản

| Kịch bản | Mô tả | Nguyên nhân | Xử lý |
|-----------|--------|--------------|--------|
| **KB 1** | TC sập sau PREPARE | Server down giữa Phase 1 & 2 | Recovery: XA COMMIT |
| **KB 2** | TC sập ở PREPARING | Server down quá sớm | Recovery: XA ROLLBACK |
| **KB 3** | TC sập đang COMMITTING | Server down trong Phase 2 | Recovery: XA COMMIT |
| **KB 4** | Bank A commit, Bank B fail | Lỗi network DB B | Compensation (hoàn tiền A) |
| **KB 5** | Bank B timeout | Network latency cao | Timeout + ROLLBACK |

---

## 3. Chi tiết từng kịch bản

### 3.1. Kịch bản 1: TC sập sau PREPARE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Timeline:                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  T1: TC gửi PREPARE ──────────────────────────────▶ Bank A (READY)      │
│  T2: TC gửi PREPARE ──────────────────────────────▶ Bank B (READY)       │
│  T3: Cả hai đã PREPARE ────────────────────────▶ Log: PREPARED           │
│  T4: ⚡ TC CRASH!                                                         │
│                                                                             │
│  ─── Server Restart ───                                                   │
│                                                                             │
│  T5: Recovery quét XA RECOVER ──────────────────▶ Bank A (PREPARED)      │
│  T6: Recovery quét transaction_log ────────────▶ phase = PREPARED         │
│  T7: Recovery gửi XA COMMIT ──────────────────▶ Bank A                   │
│  T8: Recovery gửi XA COMMIT ──────────────────▶ Bank B                   │
│  T9: Log: COMMITTED ────────────────────────────▶ ✓ Hoàn tất              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Xử lý:**
- Đọc `transaction_log` → phase = `PREPARED`
- Kiểm tra `XA RECOVER` → Bank A, Bank B đang ở trạng thái PREPARED
- Gửi `XA COMMIT` cho cả hai

---

### 3.2. Kịch bản 2: TC sập ở PREPARING

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Timeline:                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  T1: TC gửi PREPARE ──────────────────────────────▶ Bank A                │
│  T2: ⚡ TC CRASH! trước khi Bank A phản hồi                                │
│                                                                             │
│  ─── Server Restart ───                                                   │
│                                                                             │
│  T3: Recovery quét transaction_log ────────────▶ phase = PREPARING        │
│  T4: Recovery quét XA RECOVER ─────────────────▶ Không có gì            │
│  T5: Recovery gửi XA ROLLBACK (nếu có) ──────▶                          │
│  T6: Log: ABORTED ─────────────────────────────▶ ✓ Rollback thành công  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Xử lý:**
- Đọc `transaction_log` → phase = `PREPARING`
- Không có XA transaction trong `XA RECOVER` (chưa kịp PREPARE)
- Log: `ABORTED`

---

### 3.3. Kịch bản 3: TC sập đang COMMITTING

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Timeline:                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  T1: Bank A ──────▶ XA COMMIT ──▶ ✓ COMMITTED                           │
│  T2: TC log: COMMITTING                                                    │
│  T3: ⚡ TC CRASH! ngay trước khi gửi COMMIT cho Bank B                   │
│                                                                             │
│  ─── Server Restart ───                                                   │
│                                                                             │
│  T4: Recovery quét transaction_log ────────────▶ phase = COMMITTING       │
│  T5: Recovery quét XA RECOVER ─────────────────▶ Bank B (PREPARED)      │
│  T6: Recovery gửi XA COMMIT ──────────────────▶ Bank B                   │
│  T7: Log: COMMITTED ────────────────────────────▶ ✓ Hoàn tất              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Xử lý:**
- Đọc `transaction_log` → phase = `COMMITTING`
- Kiểm tra `XA RECOVER` → Bank B vẫn PREPARED
- Gửi `XA COMMIT` cho Bank B

---

### 3.4. Kịch bản 4: Bank A commit, Bank B fail (Compensation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Timeline:                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  T1: Bank A ──────▶ XA COMMIT ──▶ ✓ COMMITTED (đã trừ tiền)              │
│  T2: TC log: COMMIT_A                                                      │
│  T3: Bank B ──────▶ XA COMMIT ──▶ ✗ FAILED (network error)               │
│  T4: TC phát hiện lỗi ──────────────────────────────────────────────────▶ │
│  T5: TC gửi XA ROLLBACK ────────────────────▶ Bank B                      │
│  T6: TC gọi COMPENSATION ──────────────────▶ Hoàn tiền Bank A           │
│  T7: Log: COMPENSATED ──────────────────────▶ ✓ Hoàn tiền thành công    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Xử lý:**

```python
def do_compensation(tx_id, xid, from_account_number, amount):
    """
    Tạo giao dịch bù: cộng lại số tiền đã trừ
    """
    # 1. Tìm tài khoản nguồn
    from_acc, from_config = find_account_by_number(from_account_number)

    # 2. Cộng lại tiền
    conn = get_connection({**from_config, 'autocommit': True})
    cur.execute(
        "UPDATE accounts SET balance = balance + %s WHERE id = %s",
        (amount, from_acc['id'])
    )

    # 3. Log giao dịch compensation
    comp_tx_id = 'COMP-' + tx_id
    cur.execute(
        "INSERT INTO transactions (...) VALUES (...)",
        (comp_tx_id, 'SYSTEM', from_acc['account_number'], ...)
    )
```

**Đảm bảo:**
- Bank A đã trừ tiền → Compensation cộng lại
- Giao dịch compensation được ghi log riêng
- Không mất tiền

---

### 3.5. Kịch bản 5: Timeout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Timeline:                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  T1: TC gửi PREPARE song song ──────────▶ Bank A (READY sau 2s)           │
│  T2: TC gửi PREPARE song song ──────────▶ Bank B (PENDING...)             │
│  T3: ... ─────────────────────────────────▶ ...                           │
│  T4: ⏱ TIMEOUT sau 10 giây ──────────────────────────────────────────────▶ │
│  T5: TC gửi XA ROLLBACK ──────────────────▶ Bank A (rollback)            │
│  T6: TC gửi XA ROLLBACK ──────────────────▶ Bank B (rollback)            │
│  T7: Log: TIMEOUT ────────────────────────▶ ✓ Rollback thành công         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Xử lý:**

```python
# Sử dụng ThreadPoolExecutor với timeout
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    future_from = executor.submit(xa_prepare_participant, from_config, xid, ...)
    future_to = executor.submit(xa_prepare_participant, to_config, xid, ...)

    done, pending = concurrent.futures.wait(
        [future_from, future_to],
        timeout=PREPARE_TIMEOUT  # 10 giây
    )

if pending:
    # Timeout! Rollback tất cả
    _rollback_xa_all(xid, [from_config, to_config])
    return 408 Timeout
```

---

## 4. Recovery Process

### 4.1. Recovery Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RECOVERY PROCESS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  START                                                                      │
│    │                                                                      │
│    ▼                                                                      │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ Bước 1: XA RECOVER                                                 │   │
│  │ ─────────────────────────────────────────────────────────────────── │   │
│  │ Quét tất cả database, lấy danh sách XA transactions đang PREPARED │   │
│  │                                                                     │   │
│  │ in_doubt = {                                                       │   │
│  │   'xid1': [db1_config, db2_config],                                │   │
│  │   'xid2': [db1_config]                                            │   │
│  │ }                                                                  │   │
│  └─────────────────────────────┬────────────────────────────────────────┘   │
│                                │                                            │
│                                ▼                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ Bước 2: Đọc transaction_log                                       │   │
│  │ ─────────────────────────────────────────────────────────────────── │   │
│  │ Lấy các giao dịch chưa hoàn tất                                    │   │
│  │                                                                     │   │
│  │ pending_logs = {                                                    │   │
│  │   'xid1': {'phase': 'PREPARED', 'tx_id': 'VB...', ...},          │   │
│  │   'xid2': {'phase': 'COMMIT_A', ...}                              │   │
│  │ }                                                                  │   │
│  └─────────────────────────────┬────────────────────────────────────────┘   │
│                                │                                            │
│                                ▼                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ Bước 3: Xử lý từng giao dịch                                      │   │
│  │ ─────────────────────────────────────────────────────────────────── │   │
│  │                                                                     │   │
│  │  if phase == 'COMMIT_A':                                           │   │
│  │      → XA COMMIT Bank B (nếu còn)                                  │   │
│  │      → Compensation (nếu Bank B đã mất)                            │   │
│  │                                                                     │   │
│  │  elif phase == 'COMPENSATING':                                      │   │
│  │      → Chạy lại compensation                                        │   │
│  │                                                                     │   │
│  │  elif phase in ('PREPARED', 'COMMITTING'):                         │   │
│  │      → XA COMMIT tất cả                                            │   │
│  │                                                                     │   │
│  │  else:  # PREPARING hoặc unknown                                   │   │
│  │      → XA ROLLBACK                                                 │   │
│  └─────────────────────────────┬────────────────────────────────────────┘   │
│                                │                                            │
│                                ▼                                            │
│                           COMPLETE                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2. Recovery Code

```python
def recover_in_doubt_transactions():
    # 1. XA RECOVER
    in_doubt = {}
    for config in [db1_config, db2_config]:
        conn = get_connection({**config, 'autocommit': True})
        cur.execute("XA RECOVER")
        for row in cur.fetchall():
            xid = row[3]  # formatID
            in_doubt.setdefault(xid, []).append(config)

    # 2. Đọc transaction_log
    pending_logs = {}
    cur.execute("""
        SELECT * FROM transaction_log
        WHERE phase IN ('PREPARING','PREPARED','COMMITTING','COMMIT_A','COMPENSATING')
    """)
    pending_logs = {row['xid']: row for row in cur.fetchall()}

    # 3. Xử lý từng xid
    all_xids = set(in_doubt.keys()) | set(pending_logs.keys())
    for xid in all_xids:
        log_entry = pending_logs.get(xid)
        phase = log_entry['phase'] if log_entry else None

        if phase == 'COMMIT_A':
            # Xử lý Kịch bản 4
            ...
        elif phase == 'COMPENSATING':
            # Chạy lại compensation
            ...
        elif phase in ('PREPARED', 'COMMITTING'):
            # Tiếp tục COMMIT
            ...
        else:
            # Rollback
            ...
```

---

## 5. Logging Strategy

### 5.1. Log Types

| Loại log | Đích | Nội dung |
|----------|------|----------|
| **Phase Log** | `.log` file + DB | Chi tiết từng phase |
| **Transaction Log** | `transaction_log` DB | Trạng thái giao dịch |
| **Transactions** | `transactions` DB | Lịch sử giao dịch thành công |
| **Error Log** | `.log` file | Exception stack trace |

### 5.2. Log Format

```
2026-03-17 10:23:01  INFO     [PHASE] Phase 1  ▶ PREPARING   — TC bắt đầu giao dịch | tx=VB0A1B2C3D4 | abc123... | 1029… → 2038… | 500000đ | "Chuyển tiền"
2026-03-17 10:23:01  INFO     [PHASE] Phase 1  ✔ PREPARED    — Cả hai participant sẵn sàng | tx=VB0A1B2C3D4
2026-03-17 10:23:01  INFO     [PHASE] Phase 2  ▶ COMMITTING  — TC bắt đầu gửi COMMIT | tx=VB0A1B2C3D4
2026-03-17 10:23:01  INFO     [PHASE] Phase 2  ⚡ COMMIT_A    — Bank A đã COMMIT, Bank B chưa | tx=VB0A1B2C3D4
2026-03-17 10:23:01  INFO     [PHASE] Phase 2  ✔ COMMITTED   — Hoàn tất thành công | tx=VB0A1B2C3D4
2026-03-17 10:23:01  INFO     [TRANSFER] ✓ Hoàn tất | tx=VB0A1B2C3D4 | 500000đ | 1029… → 2038…
```

---

## 6. Error Response Codes

### 6.1. HTTP Status Codes

| Code | Ý nghĩa | Kịch bản |
|------|---------|----------|
| `200` | OK | Thành công |
| `400` | Bad Request | Validation error |
| `401` | Unauthorized | Login failed |
| `404` | Not Found | Tài khoản không tồn tại |
| `408` | Request Timeout | Kịch bản 5 - Timeout |
| `500` | Internal Error | Lỗi khác |

### 6.2. Response Messages

```json
// Timeout (KB5)
{
  "status": "error",
  "message": "Kịch bản 5 — Timeout: Bank B không phản hồi trong 10s...",
  "timeout": true,
  "tx_id": "VB0A1B2C3D4"
}

// Partial Failure (KB4)
{
  "status": "error",
  "message": "Lỗi COMMIT lệch pha (Kịch bản 4): Bank A đã trừ tiền...",
  "partial_failure": true,
  "compensation": true,
  "tx_id": "VB0A1B2C3D4"
}

// Phase 1 Failed
{
  "status": "error",
  "message": "Giao dịch thất bại ở Phase 1: ...",
  "tx_id": "VB0A1B2C3D4"
}
```

---

## 7. Best Practices

### 7.1. Prevention

| Practice | Mô tả |
|----------|-------|
| Timeout hợp lý | 10s cho Phase 1 là đủ |
| Retry logic | Thử lại network error trước khi báo lỗi |
| Health check | Monitor DB connection thường xuyên |

### 7.2. Detection

| Practice | Mô tả |
|----------|-------|
| Alerting | Cảnh báo khi có timeout hoặc recovery |
| Dashboard | Theo dõi số lượng giao dịch treo |
| Log analysis | Phân tích log để phát hiện pattern |

### 7.3. Recovery

| Practice | Mô tả |
|----------|-------|
| Auto-recovery | Chạy khi server khởi động |
| Manual recovery | API `/api/recover` cho trigger thủ công |
| Compensation | Luôn có cơ chế hoàn tiền |

---

## 8. Related Documentation

- [PRD](./PRD.md)
- [Architecture](./ARCHITECTURE.md)
- [API](./API.md)
- [2PC Protocol](./2PC-PROTOCOL.md)
- [Database](./DATABASE.md)
