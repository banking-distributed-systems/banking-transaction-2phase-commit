# V-Bank — Banking Transaction với Two-Phase Commit (2PC)

Ứng dụng ngân hàng demo minh hoạ giao thức **Two-Phase Commit (2PC)** trong hệ thống phân tán, xử lý các kịch bản lỗi thực tế khi chuyển tiền giữa các ngân hàng khác nhau.

---

## Mục lục

- [Yêu cầu](#yêu-cầu)
- [Cài đặt](#cài-đặt)
- [Chạy ứng dụng](#chạy-ứng-dụng)
- [Chạy tests](#chạy-tests)
- [Tài khoản demo](#tài-khoản-demo)
- [API Endpoints](#api-endpoints)
- [Tính năng](#tính-năng)
- [Xử lý lỗi](#xử-lý-lỗi)
- [Cấu trúc project](#cấu-trúc-project)

---

## Yêu cầu

| Phần mềm       | Phiên bản tối thiểu |
| -------------- | ------------------- |
| Python         | 3.10+               |
| Docker Desktop | Latest              |
| Git            | Latest              |

---

## Cài đặt

### 1. Clone project

```bash
git clone <repository-url>
cd banking-transaction-2phase-commit
```

### 2. Cài đặt dependencies

```bash
# Cài đặt tự động (khuyến nghị)
pip install -e .

# Hoặc cài đặt thủ công từ requirements.txt
pip install -r backend/requirements.txt
```

**Dependencies được cài tự động:**

- `flask` - Web framework
- `flask-cors` - CORS support
- `pymysql` - MySQL driver
- `pytest` - Testing framework (optional, cho dev)

### 3. Khởi động database

```bash
# Chạy Docker containers
docker-compose up -d
```

**Database containers:**

| Container | Port (Host) | Port (Container) | Database       |
| --------- | ----------- | ---------------- | -------------- |
| mysql1    | 3306        | 3306             | bank1 (Bank A) |
| mysql2    | 3307        | 3306             | bank2 (Bank B) |
| mysql3    | 3308        | 3306             | bank3 (Bank C) |

### 4. Kiểm tra database

```bash
# Kiểm tra containers đang chạy
docker ps

# Xem logs
docker-compose logs -f
```

---

## Chạy ứng dụng

### Cách 1: Chạy trực tiếp

```bash
cd backend
python app.py
```

### Cách 2: Chạy qua pip (sau khi cài -e .)

```bash
vbank-server
```

### Cách 3: Import trong Python

```python
from backend.app import main
main()
```

**Kết quả mong đợi:**

```
═══════════════════════════════════════════════════════════════
              V-Bank 2PC Server đang khởi động...
═══════════════════════════════════════════════════════════════
[STARTUP] Đang kiểm tra kết nối database...
[STARTUP] ✓ Kết nối Bank A (bank1) thành công
[STARTUP] ✓ Kết nối Bank B (bank2) thành công
[STARTUP] ✓ Kết nối Bank C (bank3) thành công
[STARTUP] Đang chạy recovery cho các giao dịch treo...
[STARTUP] ✓ Không có giao dịch treo nào
═══════════════════════════════════════════════════════════════
  🎉 V-Bank 2PC Server khởi động thành công!
  📍 Server chạy tại: http://localhost:5000
  📍 API Base URL:    http://localhost:5000/api
  🗄  Database:       bank1/bank2/bank3
  ⏱  Prepare Timeout: 10 giây
═══════════════════════════════════════════════════════════════
```

### Mở Frontend

Sử dụng VS Code Live Server hoặc mở trực tiếp:

```
http://localhost:5000/
```

Hoặc mở file `index.html` ở thư mục gốc.

---

## Chạy Tests

### Chạy tất cả tests

```bash
# Từ thư mục gốc
python -m pytest tests/ -v
```

### Chạy tests cụ thể

```bash
# Unit tests (không cần database)
python -m pytest tests/test_config.py -v

# Database tests
python -m pytest tests/test_database.py -v

# API tests
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_accounts_api.py -v
python -m pytest tests/test_transfer.py -v
```

### Tests với coverage

```bash
# Cài đặt pytest-cov
pip install pytest-cov

# Chạy với coverage report
python -m pytest tests/ --cov=backend --cov-report=html
```

### Kết quả tests

```
============================= test session starts =============================
platform win32 -- Python 3.13.x, pytest-9.x.x
collected 101 items

tests/test_config.py::TestDatabaseConfig::test_db1_config_exists PASSED   [  1%]
tests/test_config.py::TestDatabaseConfig::test_db1_config_has_required_fields PASSED [  2%]
...
============================== 101 passed in 2.5s ==============================
```

---

## Tài khoản demo

| Tên          | Số tài khoản   | Ngân hàng | SĐT        | Mật khẩu |
| ------------ | -------------- | --------- | ---------- | -------- |
| Nguyễn Văn A | 1029 3847 5612 | Bank A    | 0901234567 | 123456   |
| Trần Thị B   | 2038 4756 9801 | Bank B    | 0912345678 | 123456   |
| Lê Văn C     | 3047 5612 8934 | Bank C    | 0923456789 | 123456   |

---

## API Endpoints

| Method | Endpoint              | Mô tả                         |
| ------ | --------------------- | ----------------------------- |
| `GET`  | `/`                   | Health check                  |
| `POST` | `/api/login`          | Đăng nhập                     |
| `GET`  | `/api/accounts`       | Lấy danh sách tài khoản       |
| `POST` | `/api/lookup-account` | Tra cứu tên theo số tài khoản |
| `POST` | `/api/transfer`       | Thực hiện chuyển tiền (2PC)   |
| `POST` | `/api/recover`        | Kích hoạt recovery thủ công   |

### Ví dụ API calls

```bash
# Login
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "0901234567", "password": "123456"}'

# Get accounts
curl http://localhost:5000/api/accounts

# Lookup account
curl -X POST http://localhost:5000/api/lookup-account \
  -H "Content-Type: application/json" \
  -d '{"account_number": "203847569801"}'

# Transfer
curl -X POST http://localhost:5000/api/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "from_account_number": "102938475612",
    "to_account_number": "203847569801",
    "amount": 50000,
    "description": "Test transfer"
  }'

# Manual recovery
curl -X POST http://localhost:5000/api/recover
```

---

## Tính năng

- **Đăng nhập** theo số điện thoại / mật khẩu
- **Chuyển tiền** bằng số tài khoản, tra cứu tên chủ tài khoản trực tiếp
- **Popup xác nhận** trước khi thực hiện giao dịch
- **Hóa đơn giao dịch** sau khi chuyển thành công
- **Toàn bộ 2PC** được ghi log chi tiết ra `transaction_log` (DB) và file `.log`
- **Recovery tự động** mỗi lần server khởi động

---

## Xử lý lỗi

| #        | Kịch bản                               | Cơ chế xử lý                                                  |
| -------- | -------------------------------------- | ------------------------------------------------------------- |
| **KB 1** | TC sập sau Phase 1 (PREPARE)           | Startup recovery: đọc log → `PREPARED` → XA COMMIT tiếp tục   |
| **KB 2** | TC sập ở trạng thái PREPARING          | Startup recovery: đọc log → `PREPARING` → XA ROLLBACK         |
| **KB 3** | TC sập đang COMMITTING                 | Startup recovery: đọc log → `COMMITTING` → XA COMMIT tiếp tục |
| **KB 4** | Bank A COMMIT xong, Bank B chưa COMMIT | **Compensating Transaction** (hoàn tiền Bank A)               |
| **KB 5** | Bank B phản hồi quá chậm (Timeout)     | Timeout 10s → tự động XA ROLLBACK, trả HTTP 408               |

---

## Cấu trúc project

```
banking-transaction-2phase-commit/
├── backend/
│   ├── __init__.py           # Package marker
│   ├── app.py                # Flask entry point
│   ├── config.py             # DB configs, constants
│   ├── logger.py             # Logging configuration
│   ├── database.py           # DB helpers
│   ├── account_service.py    # Account operations
│   ├── two_phase_commit.py   # 2PC logic & recovery
│   ├── routes/               # API routes
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── accounts.py
│   │   ├── transfer.py
│   │   └── recovery.py
│   └── requirements.txt
├── frontend/
│   ├── app.js
│   └── style.css
├── index.html                # Entry UI
├── db1-init/                 # Database initialization
├── db2-init/
├── db3-init/
├── tests/                    # Test suite
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_account_service.py
│   ├── test_auth.py
│   ├── test_accounts_api.py
│   ├── test_transfer.py
│   └── conftest.py
├── docs/                     # Documentation
│   ├── README.md
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── 2PC-PROTOCOL.md
│   ├── ERROR-HANDLING.md
│   └── DATABASE.md
├── pyproject.toml           # Package configuration
├── pytest.ini               # Pytest config
├── docker-compose.yml
└── README.md
```

---

## Stack công nghệ

| Tầng         | Công nghệ                        |
| ------------ | -------------------------------- |
| Frontend     | HTML5, CSS3, Vanilla JavaScript  |
| Backend      | Python 3, Flask, PyMySQL         |
| Database     | MySQL 8 (XA Transactions)        |
| Container    | Docker, Docker Compose           |
| 2PC Protocol | MySQL XA (eXtended Architecture) |
| Testing      | pytest                           |

---

## Troubleshooting

### Lỗi kết nối database

```bash
# Kiểm tra Docker đang chạy
docker ps

# Khởi động lại containers
docker-compose down
docker-compose up -d
```

### Lỗi import module

```bash
# Đảm bảo đã cài package
pip install -e .
```

### Xem logs

```bash
# Backend logs
tail -f .log

# Docker logs
docker-compose logs -f mysql1
```

---

## License

Nguyen Phuoc Sang's License

---

## Tài liệu tham khảo

- [API Documentation](./docs/API.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [2PC Protocol](./docs/2PC-PROTOCOL.md)
- [Error Handling](./docs/ERROR-HANDLING.md)
- [Database](./docs/DATABASE.md)
