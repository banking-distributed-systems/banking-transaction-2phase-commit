# 📘 Test Cases – Hệ thống chuyển tiền 2-Phase Commit (2PC)

## 🎯 Mục tiêu

Đảm bảo tính **Atomicity (nguyên tử)** và **Consistency (toàn vẹn dữ liệu)** trong giao dịch phân tán giữa Bank A và Bank B.

---

# 🟢 I. Happy Path (Cơ bản)

## TC01 – Giao dịch thành công

**Mô tả:**

- Bank A prepare → YES
- Bank B prepare → YES
- Coordinator commit

**Kỳ vọng:**

- A bị trừ tiền
- B được cộng tiền
- Log = COMMIT

---

# ❌ II. Fail tại Phase 1 (Prepare)

## TC02 – Bank A không đủ tiền

**Mô tả:**

- A trả NO

**Kỳ vọng:**

- Coordinator rollback
- Không thay đổi dữ liệu

---

## TC03 – Bank B từ chối giao dịch

**Mô tả:**

- A → YES
- B → NO

**Kỳ vọng:**

- Rollback toàn bộ

---

# 💥 III. Fail tại Phase 2 (Commit)

## TC04 – Commit A thành công, B thất bại

**Mô tả:**

- A commit OK
- B lỗi khi commit

**Kỳ vọng:**

- Không được lệch dữ liệu
- Retry hoặc rollback

---

## TC05 – Coordinator chết sau khi commit A

**Mô tả:**

- Commit A xong
- Chưa commit B → crash

**Kỳ vọng:**

- Khi restart, commit B tiếp

---

# 🔄 IV. Recovery (Phục hồi)

## TC06 – Coordinator crash trước commit

**Mô tả:**

- Prepare xong
- Chưa commit → crash

**Kỳ vọng:**

- Rollback sau khi restart

---

## TC07 – Participant crash sau prepare

**Mô tả:**

- A prepare xong → crash

**Kỳ vọng:**

- A hỏi lại coordinator khi hồi phục

---

## TC08 – Giao dịch bị treo (In-doubt)

**Mô tả:**

- A đã prepare
- Chưa nhận commit/rollback

**Kỳ vọng:**

- A chờ coordinator

---

# 🔁 V. Idempotency

## TC09 – Commit gửi nhiều lần

**Mô tả:**

- Coordinator gửi commit 2 lần

**Kỳ vọng:**

- Không xử lý trùng

---

## TC10 – Rollback gửi nhiều lần

**Kỳ vọng:**

- Không gây lỗi

---

# 🔒 VI. Concurrency

## TC11 – 2 giao dịch cùng trừ tiền

**Mô tả:**

- 2 transaction cùng thao tác account A

**Kỳ vọng:**

- Không race condition
- Có lock hợp lý

---

# 🧠 VII. Business Logic

## TC12 – Chuyển tiền 0 hoặc âm

**Kỳ vọng:**

- Bị từ chối

---

## TC13 – Tài khoản không tồn tại

**Kỳ vọng:**

- Rollback

---

## TC14 – Double submit (bấm 2 lần)

**Kỳ vọng:**

- Chỉ xử lý 1 transaction

---

# 🧪 VIII. Logging & Audit

## TC15 – Ghi log transaction

**Kỳ vọng:**

- Có log đầy đủ: prepare, commit, rollback

---

## TC16 – Khôi phục từ log

**Mô tả:**

- Restart hệ thống

**Kỳ vọng:**

- Dựa vào log để xử lý tiếp

---

# 🏆 Tổng kết

| Nhóm         | Mục tiêu             |
| ------------ | -------------------- |
| Happy path   | Thành công           |
| Prepare fail | Ngăn commit          |
| Commit fail  | Tránh lệch dữ liệu   |
| Recovery     | Phục hồi hệ thống    |
| Idempotency  | Không xử lý trùng    |
| Concurrency  | Tránh race condition |
| Business     | Validate dữ liệu     |
| Logging      | Theo dõi & khôi phục |

---

# 🚀 Gợi ý demo

Nên demo 3 case chính:

1. Commit thành công
2. Partial commit (B fail)
3. Coordinator crash + recovery

👉 Đảm bảo cover đầy đủ bản chất 2PC
