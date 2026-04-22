# V-Bank 2PC — Database Documentation

> **Phiên bản:** 2.0
> **Ngày cập nhật:** 22/04/2026

---

## 1. Tổng quan Database

Hệ thống V-Bank sử dụng 4 MySQL containers với các database riêng biệt:

| Container | Port | Database | Mục đích |
|-----------|------|---------|----------|
| `mysql1` | 3306 | `bank1` | Bank A — tài khoản, transaction_log |
| `mysql2` | 3307 | `bank2` | Bank B — tài khoản, transaction_log |
| `mysql3` | 3308 | `bank3` | Bank C — tài khoản, transaction_log |
| `coordinator` | 3309 | `coordinator` | Coordinator — giao dịch tổng hợp, idempotency |

---

## 2. Database: bank1 (Bank A)

### 2.1. Table: accounts

Lưu trữ thông tin tài khoản ngân hàng.

```sql
CREATE TABLE accounts (
    account_number VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15,2) CHECK (balance >= 0)
) ENGINE=InnoDB;
```

| Column | Type | Constraints | Mô tả |
|--------|------|-------------|--------|
| `account_number` | VARCHAR(20) | PRIMARY KEY | Số tài khoản |
| `name` | VARCHAR(100) | | Tên chủ tài khoản |
| `balance` | DECIMAL(15,2) | CHECK >= 0 | Số dư tài khoản |

**Sample Data:**

```sql
INSERT INTO accounts (account_number, name, balance)
VALUES ('102938475612', 'Nguyễn Văn A', 1234567890);
```

---

### 2.2. Table: transactions

Lưu trữ lịch sử giao dịch thành công.

```sql
CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tx_id VARCHAR(30) NOT NULL UNIQUE,
    from_account_number VARCHAR(20) NOT NULL,
    from_name VARCHAR(100) NOT NULL,
    to_account_number VARCHAR(20) NOT NULL,
    to_name VARCHAR(100) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    description VARCHAR(255) DEFAULT '',
    status VARCHAR(20) DEFAULT 'SUCCESS',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
```

| Column | Type | Constraints | Mô tả |
|--------|------|-------------|--------|
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | ID giao dịch |
| `tx_id` | VARCHAR(30) | NOT NULL, UNIQUE | Mã giao dịch (VB...) |
| `from_account_number` | VARCHAR(20) | NOT NULL | Số TK người gửi |
| `from_name` | VARCHAR(100) | NOT NULL | Tên người gửi |
| `to_account_number` | VARCHAR(20) | NOT NULL | Số TK người nhận |
| `to_name` | VARCHAR(100) | NOT NULL | Tên người nhận |
| `amount` | DECIMAL(15,2) | NOT NULL | Số tiền |
| `description` | VARCHAR(255) | DEFAULT '' | Mô tả giao dịch |
| `status` | VARCHAR(20) | DEFAULT 'SUCCESS' | Trạng thái |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Thời gian tạo |

**Status Values:**

| Status | Mô tả |
|--------|--------|
| `SUCCESS` | Giao dịch hoàn tất |
| `FAILED` | Giao dịch thất bại |
| `COMPENSATED` | Đã hoàn tiền (compensation) |

---

### 2.3. Table: transaction_log

Bảng ghi trạng thái XA transaction tại từng participant — dùng cho recovery.

```sql
CREATE TABLE transaction_log (
    tx_id VARCHAR(30) PRIMARY KEY,
    xid   VARCHAR(64),
    phase VARCHAR(20),
    amount DECIMAL(15,2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
```

| Column | Type | Constraints | Mô tả |
|--------|------|-------------|--------|
| `tx_id` | VARCHAR(30) | PRIMARY KEY | Mã giao dịch |
| `xid` | VARCHAR(64) | | XA Transaction ID |
| `phase` | VARCHAR(20) | | Phase hiện tại của 2PC |
| `amount` | DECIMAL(15,2) | | Số tiền giao dịch |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Thời gian ghi log |

**Phase Values:**

| Phase | Mô tả |
|-------|--------|
| `PREPARING` | Đang chuẩn bị |
| `PREPARED` | Đã sẵn sàng commit |
| `COMMITTING` | Đang commit |
| `COMMIT_A` | Bank A đã commit |
| `COMMITTED` | Hoàn tất |
| `ABORTED` | Đã hủy |
| `TIMEOUT` | Timeout |
| `COMPENSATING` | Đang hoàn tiền |
| `COMPENSATED` | Đã hoàn tiền |

---

## 3. Database: bank2 (Bank B)

Cấu trúc giống bank1. Chỉ lưu tài khoản và transaction_log của participant B.

### Table: accounts

```sql
CREATE TABLE accounts (
    account_number VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15,2)
) ENGINE=InnoDB;
```

**Sample Data:**

```sql
INSERT INTO accounts (account_number, name, balance)
VALUES ('203847569801', 'Trần Thị B', 2000000);
```

### Table: transaction_log

Cấu trúc giống bank1.transaction_log (xem mục 2.2).

---

## 4. Database: bank3 (Bank C)

Cấu trúc giống bank1 & bank2.

### Table: accounts

```sql
CREATE TABLE accounts (
    account_number VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15,2)
) ENGINE=InnoDB;
```

**Sample Data:**

```sql
INSERT INTO accounts (account_number, name, balance)
VALUES ('304756128934', 'Lê Văn C', 8000000);
```

### Table: transaction_log

Cấu trúc giống bank1.transaction_log (xem mục 2.2).

---

## 5. Database: coordinator (Coordinator)

Database dùng riêng bởi Transaction Coordinator (Flask). Không dùng XA.

### 5.1. Table: transactions

Lưu kết quả tổng hợp của từng giao dịch (do `account_service.save_transaction()` ghi).

```sql
CREATE TABLE transactions (
    tx_id        VARCHAR(30) PRIMARY KEY,
    from_account VARCHAR(20),
    to_account   VARCHAR(20),
    amount       DECIMAL(15,2),
    status       VARCHAR(20),
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
```

| Column | Type | Mô tả |
|--------|------|--------|
| `tx_id` | VARCHAR(30) | Mã giao dịch duy nhất |
| `from_account` | VARCHAR(20) | Số TK người gửi |
| `to_account` | VARCHAR(20) | Số TK người nhận |
| `amount` | DECIMAL(15,2) | Số tiền |
| `status` | VARCHAR(20) | Trạng thái (SUCCESS / FAILED / COMPENSATED / TIMEOUT) |
| `created_at` | DATETIME | Thời gian tạo |

### 5.2. Table: idempotency_keys

Đảm bảo idempotency cho API `/api/transfer` (tránh double-submit).

```sql
CREATE TABLE idempotency_keys (
    idem_key VARCHAR(64) PRIMARY KEY,
    status   VARCHAR(20),
    tx_id    VARCHAR(30)
) ENGINE=InnoDB;
```

| Column | Type | Mô tả |
|--------|------|--------|
| `idem_key` | VARCHAR(64) | Idempotency key từ header `Idempotency-Key` |
| `status` | VARCHAR(20) | `PROCESSING` hoặc `SUCCESS` / `FAILED` |
| `tx_id` | VARCHAR(30) | Mã giao dịch liên kết |

---

## 6. Entity Relationship Diagram

```
  bank1 / bank2 / bank3 (mỗi participant)
  ┌──────────────────────┐   ┌─────────────────────────┐
  │      accounts        │   │     transaction_log     │
  ├──────────────────────┤   ├─────────────────────────┤
  │ account_number (PK)  │   │ tx_id (PK)              │
  │ name                 │   │ xid                     │
  │ balance              │   │ phase                   │
  └──────────────────────┘   │ amount                  │
                             │ created_at              │
                             └─────────────────────────┘

  coordinator
  ┌──────────────────────┐   ┌──────────────────────────┐
  │    transactions      │   │    idempotency_keys      │
  ├──────────────────────┤   ├──────────────────────────┤
  │ tx_id (PK)           │   │ idem_key (PK)            │
  │ from_account         │   │ status                   │
  │ to_account           │   │ tx_id                    │
  │ amount               │   └──────────────────────────┘
  │ status               │
  │ created_at           │
  └──────────────────────┘
```

---

## 7. Database Configuration

### 7.1. Connection Parameters

```python
# backend/config.py
DB1_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'bank1',
    'autocommit': False,
    'connect_timeout': 5,
    'read_timeout': 8,
    'write_timeout': 8
}

DB2_CONFIG = {
    'host': 'localhost',
    'port': 3307,
    'user': 'root',
    'password': 'root',
    'database': 'bank2',
    'autocommit': False,
    'connect_timeout': 5,
    'read_timeout': 8,
    'write_timeout': 8
}

DB3_CONFIG = {
    'host': 'localhost',
    'port': 3308,
    'user': 'root',
    'password': 'root',
    'database': 'bank3',
    'autocommit': False,
    'connect_timeout': 5,
    'read_timeout': 8,
    'write_timeout': 8
}

COORDINATOR_DB_CONFIG = {
    'host': 'localhost',
    'port': 3309,
    'user': 'root',
    'password': 'root',
    'database': 'coordinator',
    'autocommit': True,
    'connect_timeout': 5,
    'read_timeout': 8,
    'write_timeout': 8
}
```

### 7.2. Docker Compose

```yaml
# docker-compose.yml
services:
  mysql1:
    image: mysql:8
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: bank1

  mysql2:
    image: mysql:8
    ports:
      - "3307:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: bank2

  mysql3:
    image: mysql:8
    ports:
      - "3308:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: bank3
```

---

## 7. Indexing Strategy

### 8.1. Indexes on accounts

```sql
-- Tìm kiếm theo số tài khoản (account_number là PRIMARY KEY nên index tự động)
-- Không cần thêm index phụ
```

### 8.2. Indexes on transaction_log

```sql
-- Tìm kiếm theo tx_id (là PRIMARY KEY, index tự động)
-- Tìm kiếm theo xid (recovery)
CREATE INDEX idx_log_xid ON transaction_log(xid);

-- Tìm kiếm theo phase (recovery)
CREATE INDEX idx_log_phase ON transaction_log(phase);
```

---

## 9. Backup & Recovery

### 8.1. Backup Strategy

```bash
# Backup database
mysqldump -h localhost -P 3306 -u root -proot bank1 > bank1_backup.sql
mysqldump -h localhost -P 3307 -u root -proot bank2 > bank2_backup.sql

# Restore
mysql -h localhost -P 3306 -u root -proot bank1 < bank1_backup.sql
```

### 8.2. Point-in-time Recovery

Sử dụng binary logs để recovery đến thời điểm cụ thể.

---

## 10. Security Considerations

### 10.1. Connection Security

- Sử dụng SSL cho production
- Hạn chế quyền user database

---

## 11. Related Documentation

- [PRD](./PRD.md)
- [Architecture](./ARCHITECTURE.md)
- [API](./API.md)
- [2PC Protocol](./2PC-PROTOCOL.md)
- [Error Handling](./ERROR-HANDLING.md)
