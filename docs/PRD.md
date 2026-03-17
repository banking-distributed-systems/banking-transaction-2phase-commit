# V-Bank 2PC — Product Requirements Document (PRD)

> **Phiên bản:** 1.0
> **Ngày:** 17/03/2026
> **Trạng thái:** Approved
> **Người viết:** V-Bank Development Team

---

## 1. Tổng quan sản phẩm

### 1.1. Mục tiêu kinh doanh

V-Bank 2PC là hệ thống ngân hàng demo minh họa giao thức **Two-Phase Commit (2PC)** trong các giao dịch phân tán, cho phép chuyển tiền an toàn giữa hai ngân hàng khác nhau với cơ chế xử lý lỗi toàn vẹn.

### 1.2. Phạm vi sản phẩm

| Loại | Mô tả |
|------|-------|
| **Trong phạm vi** | Giao dịch chuyển tiền 2 ngân hàng, đăng nhập, tra cứu tài khoản, recovery tự động |
| **Ngoài phạm vi** | Thanh toán online, vay tín chấp, quản lý thẻ, SMS banking |

### 1.3. Đối tượng người dùng

- **Người dùng cuối:** Khách hàng ngân hàng cần chuyển tiền liên ngân hàng
- **Quản trị viên:** Kỹ sư vận hành hệ thống phân tán

---

## 2. Yêu cầu chức năng

### 2.1. FR-001: Xác thực người dùng

| Thuộc tính | Chi tiết |
|------------|----------|
| **Mô tả** | Người dùng đăng nhập bằng số điện thoại và mật khẩu |
| **Nguồn dữ liệu** | Bảng `accounts` trên Bank A hoặc Bank B |
| **Thành công** | Trả về thông tin tài khoản (id, name, balance, account_number, account_type) |
| **Thất bại** | Trả về mã lỗi 401 với message "Số điện thoại hoặc mật khẩu không đúng" |

### 2.2. FR-002: Tra cứu tài khoản

| Thuộc tính | Chi tiết |
|------------|----------|
| **Mô tả** | Tra cứu tên chủ tài khoản bằng số tài khoản |
| **Phạm vi** | Tìm kiếm trên cả Bank A và Bank B |
| **Kết quả** | Trả về name và account_number |

### 2.3. FR-003: Danh sách tài khoản

| Thuộc tính | Chi tiết |
|------------|----------|
| **Mô tả** | Lấy danh sách tất cả tài khoản từ cả hai ngân hàng |
| **Thông tin** | id, name, balance, account_number, account_type, bank |

### 2.4. FR-004: Chuyển tiền Two-Phase Commit

| Thuộc tính | Chi tiết |
|------------|----------|
| **Mô tả** | Thực hiện chuyển tiền giữa hai tài khoản thuộc hai ngân hàng khác nhau |
| **Đầu vào** | from_account_number, to_account_number, amount, description |
| **Đầu ra** | tx_id, status, message |
| **Đảm bảo** | Atomicity - hoặc thành công cả hai hoặc rollback cả hai |

### 2.5. FR-005: Recovery tự động

| Thuộc tính | Chi tiết |
|------------|----------|
| **Mô tả** | Tự động khôi phục các giao dịch treo khi server khởi động lại |
| **Kích hoạt** | Chạy một lần khi `python app.py` |
| **Xử lý** | Quét XA RECOVER + transaction_log, quyết định COMMIT/ROLLBACK/Compensation |

---

## 3. Yêu cầu phi chức năng

### 3.1. NFR-001: Hiệu năng

| Chỉ số | Mục tiêu |
|--------|-----------|
| **Response time** | < 500ms cho API thông thường |
| **Timeout** | 10 giây cho Phase 1 (PREPARE) |
| **Concurrent users** | Hỗ trợ 50 người dùng đồng thời |

### 3.2. NFR-002: Độ tin cậy

| Chỉ số | Mục tiêu |
|--------|-----------|
| **Availability** | 99.5% (không tính maintenance) |
| **Data consistency** | Đảm bảo ACID cho giao dịch |
| **Recovery** | Tự động xử lý 5 kịch bản lỗi |

### 3.3. NFR-003: Bảo mật

| Yêu cầu | Mô tả |
|----------|-------|
| **Authentication** | MD5 hash password trong database |
| **CORS** | Cho phép cross-origin từ frontend |
| **Input validation** | Validate số tiền > 0, tài khoản tồn tại |

### 3.4. NFR-004: Khả năng bảo trì

| Yêu cầu | Mô tả |
|----------|-------|
| **Modular** | Tách module theo Single Responsibility |
| **Logging** | Ghi log chi tiết mọi phase 2PC |
| **Code reuse** | Tái sử dụng hàm database, account service |

---

## 4. User Stories

| ID | User Story | Acceptance Criteria |
|----|------------|---------------------|
| **US-001** | Là người dùng, tôi muốn đăng nhập để truy cập hệ thống | - Nhập đúng SĐT + password → vào dashboard<br>- Nhập sai → hiển thị lỗi |
| **US-002** | Là người dùng, tôi muốn tra cứu tên người nhận | - Nhập số tài khoản → hiển thị tên<br>- Không tìm thấy → báo lỗi |
| **US-003** | Là người dùng, tôi muốn chuyển tiền an toàn | - Nhập đủ thông tin → xác nhận → chuyển<br>- Lỗi ở một bên → rollback cả hai |
| **US-004** | Là kỹ sư, tôi muốn hệ thống tự phục hồi khi restart | - Server down giữa chừng → restart → tự recover<br>- Không mất tiền |

---

## 5. Sơ đồ luồng nghiệp vụ

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Login      │────▶│  Dashboard   │────▶│  Transfer    │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                                 ▼
                                    ┌──────────────────────┐
                                    │  Two-Phase Commit    │
                                    │  ┌──────────────┐    │
                                    │  │ Phase 1      │    │
                                    │  │ PREPARE      │────┼──┐
                                    │  └──────────────┘    │  │
                                    │  ┌──────────────┐    │  │
                                    │  │ Phase 2      │    │  │
                                    │  │ COMMIT       │────┼──┘
                                    │  └──────────────┘    │
                                    └──────────────────────┘
```

---

## 6. Risk Register

| Risk ID | Risk Description | Impact | Probability | Mitigation |
|---------|------------------|--------|-------------|-------------|
| R-001 | Bank B không phản hồi PREPARE | High | Medium | Timeout 10s → auto rollback |
| R-002 | TC sập sau khi Bank A commit | High | Low | Recovery đọc log + compensation |
| R-003 | Database connection failure | Medium | Medium | Retry logic + error handling |
| R-004 | Mất kết nối mạng giữa chừng | High | Low | 2PC đảm bảo atomicity |

---

## 7. Glossary

| Term | Định nghĩa |
|------|------------|
| **2PC** | Two-Phase Commit - Giao thức giao dịch phân tán 2 pha |
| **TC** | Transaction Coordinator - Điều phối giao dịch |
| **XA** | eXtended Architecture - Chuẩn MySQL cho giao dịch phân tán |
| **Atomicity** | Tính nguyên tử - tất cả hoàn thành hoặc không có gì |
| **Compensation** | Giao dịch bù - hoàn tiền khi một bên đã commit |
| **In-doubt transaction** | Giao dịch treo - chưa xác định commit hay rollback |

---

## 8. Phụ lục

### 8.1. Tài khoản demo

| Tên | Số tài khoản | Ngân hàng | SĐT | Password |
|-----|--------------|-----------|------|----------|
| Nguyễn Văn A | 1029 3847 5612 | Bank A | 0901234567 | 123456 |
| Trần Thị B | 2038 4756 9801 | Bank B | 0912345678 | 123456 |
| Lê Văn C | 3047 5612 8934 | Bank C | 0923456789 | 123456 |

### 8.2. Tham khảo

- [MySQL XA Transaction](https://dev.mysql.com/doc/refman/8.0/en/xa.html)
- [Two-Phase Commit Protocol](https://en.wikipedia.org/wiki/Two-phase_commit_protocol)
