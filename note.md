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

**TC03 – B trả NO.**

- Cấu hình mô phỏng để Bank B từ chối giao dịch:

```bash
docker exec mysql2 mysql -uroot -proot bank2 -e "DROP TRIGGER IF EXISTS reject_bank_b_prepare; CREATE TRIGGER reject_bank_b_prepare BEFORE UPDATE ON accounts FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bank B rejected transaction (TC03)';"
```

- Cho phép Bank B nhận giao dịch lại:

```bash
docker exec mysql2 mysql -uroot -proot bank2 -e "DROP TRIGGER IF EXISTS reject_bank_b_prepare;"
```

---

**TC04 – Commit A thành công, B thất bại**

- Chuyển tiền với nội dung y như bên dưới:
- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC04_B_COMMIT_FAIL

---

**TC05 – Coordinator chết sau khi commit A**

- Chuyển tiền với nội dung y như bên dưới:
- Từ A: 102938475612
- Đến B: 203847569801
- Số tiền: 50000
- Nội dung: TC05_CRASH_AFTER_COMMIT_A

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

**TC11**

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

**TC14**

Mở PowerShell và chạy:

```powershell
$body = @{
	from_account_number = "102938475612"
	to_account_number = "203847569801"
	amount = 20000
	description = "TC14 double submit"
} | ConvertTo-Json

$key = "TC14-DEMO-001"

$res1 = Invoke-RestMethod `
	-Method POST `
	-Uri "http://localhost:5000/api/transfer" `
	-ContentType "application/json" `
	-Headers @{ "Idempotency-Key" = $key } `
	-Body $body

$res2 = Invoke-RestMethod `
	-Method POST `
	-Uri "http://localhost:5000/api/transfer" `
	-ContentType "application/json" `
	-Headers @{ "Idempotency-Key" = $key } `
	-Body $body

$res1
$res2
```

**Kỳ vọng:**

- Request đầu xử lý thật
- Request sau không tạo giao dịch mới
- Request sau trả lại response cũ
- Có idempotent_replay = true
- A/B chỉ đổi số dư 1 lần

Ví dụ:

```json
{
  "status": "success",
  "tx_id": "VB..."
}
```

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
- Hoặc gọi:

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:5000/api/recover"
```

**Kỳ vọng theo từng phase:**

- Nếu phase PREPARING => recovery rollback => ABORTED
- Nếu phase PREPARED => recovery commit => COMMITTED
- Nếu phase COMMITTING => recovery commit => COMMITTED
- Nếu phase COMMIT_A => recovery commit B => COMMITTED
