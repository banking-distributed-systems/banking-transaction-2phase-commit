**LỆNH TẠO PROXY API**

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies" -Method POST -ContentType "application/json" -Headers @{
	"User-Agent" = "curl"
} ` -Body '{"name":"vbank_api","listen":"127.0.0.1:8666","upstream":"host.docker.internal:5000"}'
```

**TÀI KHOẢN**

- sdt: 0901234567
- psswrd: 123456

**Kích thước response login:** khoảng 398 bytes

---

**TC01 – Happy path (A/B prepare YES, commit thành công)**

- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000

**Kỳ vọng:**

- API trả `success`
- `message` chứa: `Chuyển tiền thành công! (2-Phase Commit Hoàn tất)`
- A bị trừ tiền, B được cộng tiền
- `transaction_log` đi đủ phase:
- PREPARING
- PREPARED
- COMMITTING
- COMMIT_A
- COMMITTED

---

**TC02 – Bank A fail ở Phase 1 (prepare)**

- Mô tả: participant nguồn (A) trả lỗi trong prepare

**Kỳ vọng:**

- API trả `error`
- `message` chứa: `Giao dịch thất bại ở Phase 1`
- Coordinator rollback toàn bộ participant
- Không đổi số dư A/B
- `transaction_log` kết thúc ở `ABORTED`

---

**TC03 – B trả NO.**

- cấu hình mô phỏng để Bank B từ chối giao dịch:

```bash
docker exec mysql2 mysql -uroot -proot bank2 -e "DROP TRIGGER IF EXISTS reject_bank_b_prepare; CREATE TRIGGER reject_bank_b_prepare BEFORE UPDATE ON accounts FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bank B rejected transaction (TC03)';"
```

- cho phép bank B nhận giao dịch:

```bash
docker exec mysql2 mysql -uroot -proot bank2 -e "DROP TRIGGER IF EXISTS reject_bank_b_prepare;"
```

**Kỳ vọng:**

- API trả `error`
- `message` chứa: `Giao dịch thất bại ở Phase 1`
- Coordinator rollback toàn bộ
- Không đổi số dư A/B
- `transaction_log` kết thúc ở `ABORTED`

---

**TC04 – Commit A thành công, B thất bại**

- cấu hình để cho TC04 – Commit A thành công, B thất bại.
- chuyển tiền với nội dung y như bên dưới:

- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC04_B_COMMIT_FAIL

**Kỳ vọng:**

- API trả `error`
- `message` chứa cụm: `Lỗi COMMIT lệch pha (Kịch bản 4)`
- A đã commit trừ tiền trước, B commit lỗi
- Hệ thống chạy compensation hoàn tiền lại cho A
- `extra_data` có:
- `partial_failure = true`
- `compensation = true/false` (thực tế xử lý bù)
- Nếu compensation thành công: số dư cuối cùng không bị lệch

---

**TC05 – Coordinator chết sau khi commit A**

- cấu hình để chạy TC05 – Coordinator chết sau khi commit A.
- chuyển tiền với nội dung y như bên dưới:

- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC05_CRASH_AFTER_COMMIT_A

**Kỳ vọng:**

- Backend crash ngay sau phase `COMMIT_A` (trước commit B)
- Trước recovery: giao dịch ở trạng thái dở dang
- Sau khi restart backend hoặc gọi `POST /api/recover`:
- Recovery commit nốt Bank B
- `transaction_log` chuyển sang `COMMITTED`
- API recover trả action `COMMIT_B_COMPLETED` cho giao dịch này

---

**TC06 – Coordinator crash trước commit**

- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC06_CRASH_BEFORE_COMMIT

**Kỳ vọng:**

- A không bị trừ tiền
- B không được cộng tiền
- transaction_log = ABORTED

---

**TC07 – Participant crash sau prepare**

- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC07_CRASH_AFTER_PREPARE

**Kỳ vọng:**

- A bị trừ tiền
- B được cộng tiền
- transaction_log = COMMITTED

---

**TC08 – Giao dịch in-doubt / crash lúc COMMITTING**

- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC08_CRASH_DURING_COMMITTING

**Kỳ vọng:**

- Server crash khi phase = COMMITTING
- Sau khi restart backend hoặc bấm Recovery:
- transaction_log = COMMITTED
- A bị trừ tiền
- B được cộng tiền

---

**TC09 – Commit gửi nhiều lần**

- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC09_COMMIT_TWICE

**Kỳ vọng:**

- transaction_log = COMMITTED
- A bị trừ đúng 1 lần
- B được cộng đúng 1 lần
- Không bị nhân đôi tiền dù commit được gọi lại
- API trả success

---

**TC10 – Rollback gửi nhiều lần**

- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC10_ROLLBACK_TWICE

**Kỳ vọng:**

- transaction_log = ABORTED
- A không bị trừ tiền
- B không được cộng tiền
- API trả error demo
- Rollback gửi 2 lần nhưng hệ thống không crash

---

**TC11 – Concurrent transfer**

- Mở 2 tab hoặc 2 trình duyệt
- Cùng chuyển từ A sang B
- Bấm gần như cùng lúc

**Kỳ vọng:**

- Server không crash
- Mỗi request có tx_id riêng
- Nếu cả hai đủ số dư thì cả hai COMMITTED
- A bị trừ tổng số tiền của 2 giao dịch
- B được cộng tổng số tiền của 2 giao dịch

---

**TC12 – Nhập số tiền 0 hoặc âm**

**Kỳ vọng:**

- API trả lỗi validation
- Không tạo giao dịch 2PC thành công
- Không đổi số dư A/B
- Không COMMITTED

---

**TC13 – Nhập tài khoản không tồn tại**

**Kỳ vọng:**

- API trả lỗi tài khoản đích không tồn tại
- Không chạy 2PC commit
- Không đổi số dư A/B

---

**TC14 – Idempotency**

**Kỳ vọng:**

- Request đầu xử lý thật
- Request sau không tạo giao dịch mới
- Request sau trả lại response cũ
- Có idempotent_replay = true
- A/B chỉ đổi số dư 1 lần

---

**TC15 – Logging phase đầy đủ**

- Không cần keyword riêng. Có thể dùng một giao dịch thường hoặc các token trên.

**Kỳ vọng với giao dịch thành công bình thường:**

- PREPARING
- PREPARED
- COMMITTING
- COMMIT_A
- COMMITTED

---

**TC16 – Recovery từ log**

- Không cần keyword riêng, dùng lại TC06/TC07/TC08 để tạo giao dịch treo.

**Cách test:**

- Chạy một trong:
- TC06_CRASH_BEFORE_COMMIT
- TC07_CRASH_AFTER_PREPARE
- TC08_CRASH_DURING_COMMITTING
- Sau khi server crash:
- Restart backend
- hoặc gọi:

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:5000/api/recover"
```

**Kỳ vọng theo từng phase:**

- Nếu phase PREPARING => recovery rollback => ABORTED
- Nếu phase PREPARED => recovery commit => COMMITTED
- Nếu phase COMMITTING => recovery commit => COMMITTED
- Nếu phase COMMIT_A => recovery commit B => COMMITTED
