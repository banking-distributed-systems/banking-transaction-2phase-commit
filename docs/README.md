# V-Bank 2PC — Documentation Index

> **Phiên bản:** 1.0
> **Ngày:** 17/03/2026

---

## Giới thiệu

Đây là bộ tài liệu đầy đủ cho hệ thống **V-Bank 2PC** - Ứng dụng ngân hàng demo minh họa giao thức Two-Phase Commit (2PC) trong giao dịch phân tán.

---

## 📚 Danh sách tài liệu

| # | Tài liệu | Mô tả |
|---|-----------|--------|
| 1 | **[PRD.md](./PRD.md)** | Product Requirements Document - Yêu cầu sản phẩm, user stories, risk register |
| 2 | **[ARCHITECTURE.md](./ARCHITECTURE.md)** | Kiến trúc hệ thống, component diagram, data flow |
| 3 | **[API.md](./API.md)** | Tài liệu API đầy đủ, request/response examples |
| 4 | **[2PC-PROTOCOL.md](./2PC-PROTOCOL.md)** | Chi tiết giao thức Two-Phase Commit, XA commands |
| 5 | **[ERROR-HANDLING.md](./ERROR-HANDLING.md)** | Xử lý lỗi, 5 kịch bản lỗi, recovery process |
| 6 | **[DATABASE.md](./DATABASE.md)** | Thiết kế database, schema, indexes |

---

## 🔀 Đọc theo luồng

### Dành cho Developer mới

```
1. PRD.md
   ↓
2. ARCHITECTURE.md
   ↓
3. API.md
   ↓
4. DATABASE.md
```

### Dành cho Technical Lead

```
ARCHITECTURE.md
       ↓
2PC-PROTOCOL.md
       ↓
ERROR-HANDLING.md
       ↓
DATABASE.md
```

### Dành cho người vận hành

```
2PC-PROTOCOL.md
       ↓
ERROR-HANDLING.md
       ↓
DATABASE.md
```

---

## 📋 Quick Reference

### API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/login` | Đăng nhập |
| `GET` | `/api/accounts` | Danh sách tài khoản |
| `POST` | `/api/lookup-account` | Tra cứu tài khoản |
| `POST` | `/api/transfer` | Chuyển tiền (2PC) |
| `POST` | `/api/recover` | Recovery thủ công |

### Kịch bản lỗi 2PC

| Kịch bản | Mô tả | Xử lý |
|-----------|--------|--------|
| KB 1 | TC sập sau PREPARE | XA COMMIT |
| KB 2 | TC sập ở PREPARING | XA ROLLBACK |
| KB 3 | TC sập đang COMMITTING | XA COMMIT |
| KB 4 | Bank A commit, Bank B fail | Compensation |
| KB 5 | Timeout | Auto ROLLBACK |

### Database Connections

| Service | Port | Database |
|---------|------|----------|
| mysql1 | 5433 | bank1 |
| mysql2 | 5434 | bank2 |
| mysql3 | 5435 | bank3 |

---

## 🚀 Bắt đầu nhanh

```bash
# 1. Khởi động database
docker-compose up -d

# 2. Cài đặt dependencies
pip install -e .

# 3. Chạy server
python -c "from backend.app import main; main()"

# 4. Mở frontend
# Sử dụng Live Server hoặc mở index.html
```

---

## 📞 Liên hệ

- **Team:** V-Bank Development Team
- **Email:** dev@vbank.local
- **GitHub:** [vbank/2pc](https://github.com/vbank/2pc)

---

## 📄 License

MIT License - Xem chi tiết tại [LICENSE](../LICENSE)

---

## 🔗 Liên kết nhanh

- [README chính](../README.md)
- [Source Code](../backend/)
- [Frontend](../frontend/)
- [Database Scripts](../db1-init/)
