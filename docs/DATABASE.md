# V-Bank 2PC — Database Documentation

> **Phiên bản:** 1.0
> **Ngày:** 17/03/2026

---

## 1. Tổng quan Database

Hệ thống V-Bank sử dụng 3 MySQL containers với các database riêng biệt:

| Container | Port | Database | Mục đích |
|-----------|------|---------|----------|
| `mysql1` | 5433 | `bank1` | Bank A - Tài khoản, giao dịch, log |
| `mysql2` | 5434 | `bank2` | Bank B - Tài khoản, giao dịch |
| `mysql3` | 5435 | `bank3` | Mở rộng |

---

## 2. Database: bank1 (Bank A)

### 2.1. Table: accounts

Lưu trữ thông tin tài khoản ngân hàng.

```sql
CREATE TABLE accounts (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15, 2) CHECK (balance >= 0),
    phone VARCHAR(20),
    password VARCHAR(255),
    account_number VARCHAR(20),
    account_type VARCHAR(50) DEFAULT 'STANDARD'
) ENGINE=InnoDB;
```

| Column | Type | Constraints | Mô tả |
|--------|------|-------------|--------|
| `id` | INT | PRIMARY KEY | ID tài khoản |
| `name` | VARCHAR(100) | | Tên chủ tài khoản |
| `balance` | DECIMAL(15,2) | CHECK >= 0 | Số dư tài khoản |
| `phone` | VARCHAR(20) | | Số điện thoại |
| `password` | VARCHAR(255) | | MD5 hash của mật khẩu |
| `account_number` | VARCHAR(20) | | Số tài khoản |
| `account_type` | VARCHAR(50) | DEFAULT 'STANDARD' | Loại tài khoản |

**Sample Data:**

```sql
INSERT INTO accounts (id, name, balance, phone, password, account_number, account_type)
VALUES
    (1, 'Nguyễn Văn A', 1234567890, '0901234567', 'e10adc3949ba59abbe56e057f20f883e', '1029 3847 5612', 'VCB PLATINUM'),
    (4, 'Lê Văn C', 5000000, '0923456789', 'e10adc3949ba59abbe56e057f20f883e', '3047 5612 8934', 'STANDARD');
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

Bảng ghi log trạng thái từng phase của 2PC - quan trọng cho recovery.

```sql
CREATE TABLE transaction_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tx_id VARCHAR(30) NOT NULL UNIQUE,
    xid VARCHAR(64) NOT NULL,
    from_account_number VARCHAR(20) NOT NULL,
    from_name VARCHAR(100) NOT NULL,
    to_account_number VARCHAR(20) NOT NULL,
    to_name VARCHAR(100) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    description VARCHAR(255) DEFAULT '',
    phase VARCHAR(20) NOT NULL DEFAULT 'PREPARING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;
```

| Column | Type | Constraints | Mô tả |
|--------|------|-------------|--------|
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | ID log |
| `tx_id` | VARCHAR(30) | NOT NULL, UNIQUE | Mã giao dịch hiển thị |
| `xid` | VARCHAR(64) | NOT NULL | XA Transaction ID |
| `from_account_number` | VARCHAR(20) | NOT NULL | Số TK người gửi |
| `from_name` | VARCHAR(100) | NOT NULL | Tên người gửi |
| `to_account_number` | VARCHAR(20) | NOT NULL | Số TK người nhận |
| `to_name` | VARCHAR(100) | NOT NULL | Tên người nhận |
| `amount` | DECIMAL(15,2) | NOT NULL | Số tiền |
| `description` | VARCHAR(255) | DEFAULT '' | Mô tả |
| `phase` | VARCHAR(20) | NOT NULL, DEFAULT 'PREPARING' | Phase hiện tại |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Thời gian tạo |
| `updated_at` | DATETIME | AUTO UPDATE | Thời gian cập nhật |

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

### 3.1. Table: accounts

```sql
CREATE TABLE accounts (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    balance DECIMAL(15, 2) CHECK (balance >= 0),
    phone VARCHAR(20),
    password VARCHAR(255),
    account_number VARCHAR(20),
    account_type VARCHAR(50) DEFAULT 'STANDARD'
) ENGINE=InnoDB;
```

**Sample Data:**

```sql
INSERT INTO accounts (id, name, balance, phone, password, account_number, account_type)
VALUES
    (2, 'Trần Thị B', 3000000, '0912345678', 'e10adc3949ba59abbe56e057f20f883e', '2038 4756 9801', 'STANDARD');
```

---

### 3.2. Table: transactions

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

---

## 4. Database: bank3 (Bank C - Mở rộng)

Tương tự Bank B, có thể mở rộng khi cần thêm ngân hàng.

---

## 5. Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BANK A (bank1)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐         ┌──────────────────┐                           │
│   │  accounts   │         │  transactions    │                           │
│   ├─────────────┤         ├──────────────────┤                           │
│   │ id (PK)     │◀───────│ from_account_id  │                           │
│   │ name        │         │ to_account_id    │                           │
│   │ balance     │         │ amount           │                           │
│   │ phone       │         │ status           │                           │
│   │ password    │         │ created_at       │                           │
│   │ account_num │         └──────────────────┘                           │
│   │ account_type│                                                     │
│   └─────────────┘                                                     │
│            │                                                           │
│            │                                                            │
│   ┌────────▼─────────┐                                                 │
│   │ transaction_log  │                                                 │
│   ├─────────────────┤                                                 │
│   │ tx_id (UNIQUE)  │                                                 │
│   │ xid             │                                                 │
│   │ phase           │                                                 │
│   │ ...             │                                                 │
│   └─────────────────┘                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        BANK B (bank2)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐         ┌──────────────────┐                           │
│   │  accounts   │         │  transactions    │                           │
│   ├─────────────┤         ├──────────────────┤                           │
│   │ id (PK)     │◀───────│ from_account_id  │                           │
│   │ name        │         │ to_account_id    │                           │
│   │ balance     │         │ amount           │                           │
│   │ phone       │         │ status           │                           │
│   │ password    │         │ created_at       │                           │
│   │ account_num │         └──────────────────┘                           │
│   │ account_type│                                                     │
│   └─────────────┘                                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Database Configuration

### 6.1. Connection Parameters

```python
# backend/config.py
DB1_CONFIG = {
    'host': 'localhost',
    'port': 5433,
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
    'port': 5434,
    'user': 'root',
    'password': 'root',
    'database': 'bank2',
    'autocommit': False,
    'connect_timeout': 5,
    'read_timeout': 8,
    'write_timeout': 8
}
```

### 6.2. Docker Compose

```yaml
# docker-compose.yml
services:
  mysql1:
    image: mysql:8
    ports:
      - "5433:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: bank1

  mysql2:
    image: mysql:8
    ports:
      - "5434:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: bank2

  mysql3:
    image: mysql:8
    ports:
      - "5435:3306"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: bank3
```

---

## 7. Indexing Strategy

### 7.1. Indexes on accounts

```sql
-- Tìm kiếm theo số tài khoản
CREATE INDEX idx_account_number ON accounts(account_number);

-- Tìm kiếm theo số điện thoại (login)
CREATE INDEX idx_phone ON accounts(phone);
```

### 7.2. Indexes on transactions

```sql
-- Tìm kiếm theo tx_id
CREATE INDEX idx_tx_id ON transactions(tx_id);

-- Tìm kiếm theo ngày
CREATE INDEX idx_created_at ON transactions(created_at);
```

### 7.3. Indexes on transaction_log

```sql
-- Tìm kiếm theo tx_id
CREATE INDEX idx_log_tx_id ON transaction_log(tx_id);

-- Tìm kiếm theo xid (recovery)
CREATE INDEX idx_log_xid ON transaction_log(xid);

-- Tìm kiếm theo phase (recovery)
CREATE INDEX idx_log_phase ON transaction_log(phase);
```

---

## 8. Backup & Recovery

### 8.1. Backup Strategy

```bash
# Backup database
mysqldump -h localhost -P 5433 -u root -proot bank1 > bank1_backup.sql
mysqldump -h localhost -P 5434 -u root -proot bank2 > bank2_backup.sql

# Restore
mysql -h localhost -P 5433 -u root -proot bank1 < bank1_backup.sql
```

### 8.2. Point-in-time Recovery

Sử dụng binary logs để recovery đến thời điểm cụ thể.

---

## 9. Security Considerations

### 9.1. Password Storage

- Password được hash bằng MD5 trong database
- Nên chuyển sang bcrypt hoặc argon2 cho production

### 9.2. Connection Security

- Sử dụng SSL cho production
- Hạn chế quyền user database

---

## 10. Related Documentation

- [PRD](./PRD.md)
- [Architecture](./ARCHITECTURE.md)
- [API](./API.md)
- [2PC Protocol](./2PC-PROTOCOL.md)
- [Error Handling](./ERROR-HANDLING.md)
