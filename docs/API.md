# V-Bank 2PC — API Documentation

> **Phiên bản:** 1.0
> **Ngày:** 17/03/2026
> **Base URL:** `http://localhost:5000`

---

## Mục lục

1. [Authentication](#1-authentication)
2. [Account](#2-account)
3. [Transfer](#3-transfer)
4. [Recovery](#4-recovery)

---

## 1. Authentication

### POST /api/login

Đăng nhập vào hệ thống ngân hàng.

**Request**

```http
POST /api/login
Content-Type: application/json
```

```json
{
  "phone": "0901234567",
  "password": "123456"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `phone` | string | ✓ | Số điện thoại đăng ký |
| `password` | string | ✓ | Mật khẩu |

**Response (Success)**

```json
{
  "status": "success",
  "user": {
    "id": 1,
    "name": "Nguyễn Văn A",
    "balance": 5000000,
    "account_number": "102938475612",
    "account_type": "saving"
  }
}
```

**Response (Error)**

```json
{
  "status": "error",
  "message": "Số điện thoại hoặc mật khẩu không đúng"
}
```

---

## 2. Account

### GET /api/accounts

Lấy danh sách tất cả tài khoản từ cả hai ngân hàng.

**Request**

```http
GET /api/accounts
```

**Response (Success)**

```json
[
  {
    "id": 1,
    "name": "Nguyễn Văn A",
    "balance": 5000000,
    "account_number": "102938475612",
    "account_type": "saving",
    "bank": "Ngân hàng 1"
  },
  {
    "id": 2,
    "name": "Trần Thị B",
    "balance": 3000000,
    "account_number": "203847569801",
    "account_type": "checking",
    "bank": "Ngân hàng 2"
  }
]
```

---

### POST /api/lookup-account

Tra cứu thông tin tài khoản theo số tài khoản.

**Request**

```http
POST /api/lookup-account
Content-Type: application/json
```

```json
{
  "account_number": "203847569801"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `account_number` | string | ✓ | Số tài khoản cần tra cứu |

**Response (Success)**

```json
{
  "status": "success",
  "account": {
    "name": "Trần Thị B",
    "account_number": "203847569801"
  }
}
```

**Response (Error - Not Found)**

```json
{
  "status": "error",
  "message": "Không tìm thấy tài khoản"
}
```

**Response (Error - Empty Input)**

```json
{
  "status": "error",
  "message": "Vui lòng nhập số tài khoản"
}
```

---

## 3. Transfer

### POST /api/transfer

Thực hiện chuyển tiền Two-Phase Commit giữa hai ngân hàng.

**Request**

```http
POST /api/transfer
Content-Type: application/json
```

```json
{
  "from_account_number": "102938475612",
  "to_account_number": "203847569801",
  "amount": 500000,
  "description": "Chuyển tiền trả nợ"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from_account_number` | string | ✓ | Số tài khoản người gửi |
| `to_account_number` | string | ✓ | Số tài khoản người nhận |
| `amount` | number | ✓ | Số tiền chuyển ( > 0 ) |
| `description` | string | ✗ | Mô tả giao dịch |

**Response (Success)**

```json
{
  "status": "success",
  "message": "Chuyển tiền thành công! (2-Phase Commit Hoàn tất)",
  "tx_id": "VB0A1B2C3D4"
}
```

**Response (Error - Validation)**

```json
{
  "status": "error",
  "message": "Số tiền không hợp lệ"
}
```

```json
{
  "status": "error",
  "message": "Tài khoản nguồn không tồn tại"
}
```

```json
{
  "status": "error",
  "message": "Tài khoản đích không tồn tại"
}
```

```json
{
  "status": "error",
  "message": "Không thể chuyển tiền cùng một tài khoản"
}
```

**Response (Error - Timeout - Kịch bản 5)**

```json
{
  "status": "error",
  "message": "Kịch bản 5 — Timeout: Bank B (đích) không phản hồi trong 10s. Đã tự động hủy giao dịch, không tài khoản nào thay đổi số dư.",
  "timeout": true,
  "tx_id": "VB0A1B2C3D4"
}
```

**Response (Error - Partial Failure - Kịch bản 4)**

```json
{
  "status": "error",
  "message": "Lỗi COMMIT lệch pha (Kịch bản 4): Bank A đã trừ tiền nhưng Bank B chưa nhận. Đã hoàn tiền tự động cho người gửi.",
  "partial_failure": true,
  "compensation": true,
  "tx_id": "VB0A1B2C3D4"
}
```

**Response (Error - Phase 1 Failure)**

```json
{
  "status": "error",
  "message": "Giao dịch thất bại ở Phase 1: <error_message>",
  "tx_id": "VB0A1B2C3D4"
}
```

**Response (Error - Phase 2 Failure)**

```json
{
  "status": "error",
  "message": "Giao dịch thất bại, đã Rollback: <error_message>",
  "tx_id": "VB0A1B2C3D4"
}
```

---

## 4. Recovery

### POST /api/recover

Kích hoạt recovery thủ công cho các giao dịch treo (in-doubt transactions).

**Request**

```http
POST /api/recover
```

**Response (Success)**

```json
{
  "status": "success",
  "recovered": [
    {
      "tx_id": "VB0A1B2C3D4",
      "xid": "abc123...",
      "action": "COMMITTED"
    },
    {
      "tx_id": "VB5E6F7G8H9",
      "xid": "def456...",
      "action": "COMPENSATED"
    }
  ],
  "count": 2
}
```

**Response (No Pending Transactions)**

```json
{
  "status": "success",
  "recovered": [],
  "count": 0
}
```

---

## Health Check

### GET /

Kiểm tra server đang chạy.

**Request**

```http
GET /
```

**Response**

```json
{
  "status": "ok",
  "message": "V-Bank 2PC Server is running"
}
```

---

## Error Codes

| HTTP Code | Meaning |
|-----------|---------|
| `200` | Success |
| `400` | Bad Request - Invalid input |
| `401` | Unauthorized - Login failed |
| `404` | Not Found |
| `408` | Request Timeout - Kịch bản 5 |
| `500` | Internal Server Error |

---

## Transaction Status Codes

| Code | Description |
|------|-------------|
| `SUCCESS` | Giao dịch hoàn tất |
| `FAILED` | Giao dịch thất bại |
| `COMPENSATED` | Đã hoàn tiền (Kịch bản 4) |
| `TIMEOUT` | Timeout (Kịch bản 5) |

---

## Related Documentation

- [PRD](./PRD.md)
- [Architecture](./ARCHITECTURE.md)
- [2PC Protocol](./2PC-PROTOCOL.md)
- [Error Handling](./ERROR-HANDLING.md)
