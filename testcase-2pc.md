# Test Cases - Two-Phase Commit (TC01-TC16)

## Muc tieu

Dam bao tinh nguyen tu va nhat quan khi chuyen tien lien ngan hang bang 2PC, bao gom ca tinh huong loi, recovery, idempotency va concurrency.

## Dieu kien chay

- Backend API chay o localhost:5000.
- Neu test qua proxy, dung localhost:8666 (Toxiproxy) -> upstream localhost:5000.
- Tai khoan demo mac dinh:
  - A: 102938475612
  - B: 203847569801

## Ma tran testcase

### Nhom 1 - Happy path

#### TC01 - A/B prepare YES, commit thanh cong

- Ky vong:
  - API tra success.
  - A bi tru tien, B duoc cong tien.
  - transaction_log di du phase:
    - PREPARING
    - PREPARED
    - COMMITTING
    - COMMIT_A
    - COMMITTED

### Nhom 2 - Fail Phase 1 (prepare)

#### TC02 - Bank A fail o prepare

- Ky vong:
  - API tra error voi thong diep that bai o Phase 1.
  - Coordinator rollback toan bo participant.
  - Khong doi so du A/B.
  - transaction_log ket thuc ABORTED.

#### TC03 - Bank B tra NO

- Ky vong:
  - API tra error voi thong diep that bai o Phase 1.
  - Rollback toan bo.
  - Khong doi so du A/B.
  - transaction_log ket thuc ABORTED.

### Nhom 3 - Fail Phase 2 (commit)

#### TC04 - Commit A thanh cong, B that bai

- Ky vong:
  - API tra error, thong diep co "Kich ban 4".
  - A da commit tru tien, B commit loi.
  - He thong chay compensation cho A.
  - Response co flag:
    - partial_failure = true
    - compensation = true/false

#### TC05 - Coordinator crash sau COMMIT_A

- Ky vong:
  - Backend dung sau COMMIT_A, truoc commit B.
  - Sau restart hoac goi /api/recover:
    - Bank B duoc commit tiep.
    - transaction_log thanh COMMITTED.
    - Recovery action: COMMIT_B_COMPLETED.

### Nhom 4 - Recovery

#### TC06 - Crash truoc commit

- Ky vong:
  - Recovery dua giao dich ve ABORTED.
  - A khong bi tru, B khong duoc cong.

#### TC07 - Crash sau PREPARED

- Ky vong:
  - Recovery tiep tuc commit.
  - transaction_log ve COMMITTED.

#### TC08 - In-doubt o COMMITTING

- Ky vong:
  - Recovery tiep tuc commit.
  - transaction_log ve COMMITTED.

### Nhom 5 - Idempotency

#### TC09 - Commit gui nhieu lan

- Ky vong:
  - He thong khong crash.
  - Khong nhan doi tien.
  - Trang thai cuoi COMMITTED.

#### TC10 - Rollback gui nhieu lan

- Ky vong:
  - He thong xu ly an toan, khong crash.
  - Trang thai cuoi ABORTED.

#### TC14 - Double submit cung Idempotency-Key

- Ky vong:
  - Request dau xu ly that.
  - Request sau replay response cu, khong tao giao dich moi.
  - idempotent_replay = true.
  - tx_id cua 2 response giong nhau.
  - So du A/B chi doi 1 lan.

### Nhom 6 - Concurrency

#### TC11 - 2 giao dich dong thoi tu A sang B

- Ky vong:
  - Server khong crash.
  - Moi request co tx_id rieng.
  - Neu du so du, ca hai giao dich COMMITTED.

### Nhom 7 - Business validation

#### TC12 - So tien <= 0

- Ky vong:
  - API tra loi validation.
  - Khong tao giao dich thanh cong.
  - Khong doi so du A/B.

#### TC13 - Tai khoan dich khong ton tai

- Ky vong:
  - API tra loi tai khoan dich khong ton tai.
  - Khong chay commit 2PC.
  - Khong doi so du A/B.

### Nhom 8 - Logging va audit

#### TC15 - Day du phase log trong transaction_log

- Ky vong (giao dich thanh cong):
  - PREPARING
  - PREPARED
  - COMMITTING
  - COMMIT_A
  - COMMITTED

#### TC16 - Recovery tu transaction_log

- Ky vong theo phase:
  - PREPARING -> recovery rollback -> ABORTED
  - PREPARED -> recovery commit -> COMMITTED
  - COMMITTING -> recovery commit -> COMMITTED
  - COMMIT_A -> recovery commit B -> COMMITTED

## Mapping voi test tu dong

- tests/test_2pc_matrix.py: cover logic matrix TC01-TC16 voi mock.
- tests/test_transfer.py: cover API transfer, idempotency, transfer status, transfer recent.
- tests/test_database.py: cover ket noi DB va truy van co ban.
- tests/test_frontend_smoke.py: smoke test wiring UI monitor/recovery.
- tests/test_toxiproxy_e2e.py: E2E qua localhost:8666 (marker e2e, RUN_TOXIPROXY_E2E=1).

## Goi y demo nhanh

1. TC01: happy path.
2. TC04: partial commit + compensation.
3. TC05/TC16: crash + recovery tu log.
