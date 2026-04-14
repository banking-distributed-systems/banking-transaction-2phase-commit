# Testcase 2PC Explain

## 1) Tong quan nhung gi da trien khai

Muc tieu la map bo testcase trong `testcase-2pc.md` thanh test tu dong co the chay bang pytest, uu tien:

1. Case 2PC cot loi (happy path, fail prepare, fail commit lech pha).
2. Case recovery (coordinator/participant crash theo state log).
3. Case network da co san truoc do (Toxiproxy) de demo fault injection.
4. Case business validation va logging/audit.

### File da tao/sua

1. Them file test matrix moi: `tests/test_2pc_matrix.py`
2. Sua typo patch path recover cu: `tests/test_transfer.py`
3. Sua parse amount tranh crash ValueError: `backend/routes/transfer.py`

## 2) Mapping TC01-TC16 -> Test da trien khai

| TC   | Mo ta                                       | Test function                                                     | Trang thai                             |
| ---- | ------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------- |
| TC01 | Giao dich thanh cong (A YES, B YES, COMMIT) | `test_tc01_happy_path_commit_success`                             | Pass                                   |
| TC02 | Fail Prepare tai A                          | `test_tc02_prepare_fail_bank_a`                                   | Pass                                   |
| TC03 | Fail Prepare tai B                          | `test_tc03_prepare_fail_bank_b`                                   | Pass                                   |
| TC04 | Commit A ok, B fail, xu ly lech pha         | `test_tc04_partial_commit_b_fail_then_compensate`                 | Pass                                   |
| TC05 | Coordinator crash sau commit A              | `test_tc05_coordinator_crash_after_commit_a_recover_commit_b`     | Pass                                   |
| TC06 | Coordinator crash truoc commit              | `test_tc06_coordinator_crash_before_commit_recover_abort`         | Pass                                   |
| TC07 | Participant crash sau prepare               | `test_tc07_participant_crash_after_prepare_recover_commit`        | Pass                                   |
| TC08 | In-doubt state, cho coordinator quyet dinh  | `test_tc08_in_doubt_state_waiting_coordinator_then_recover`       | Pass                                   |
| TC09 | Commit gui nhieu lan                        | `test_tc09_commit_sent_multiple_times_idempotent`                 | Pass                                   |
| TC10 | Rollback gui nhieu lan                      | `test_tc10_rollback_sent_multiple_times_idempotent`               | Pass                                   |
| TC11 | Concurrency 2 giao dich cung nguon          | `test_tc11_concurrent_transfers_do_not_crash`                     | Pass                                   |
| TC12 | Chuyen tien 0 hoac am                       | `test_tc12_transfer_reject_zero_or_negative_amount`               | Pass                                   |
| TC13 | Tai khoan khong ton tai                     | `test_tc13_transfer_reject_missing_account`                       | Pass                                   |
| TC14 | Double submit (chi xu ly 1 lan)             | `test_tc14_double_submit_should_process_once`                     | XFAIL (chua co idempotency key/dedupe) |
| TC15 | Logging phase day du                        | `test_tc15_transaction_logs_have_prepare_commit_rollback_markers` | Pass                                   |
| TC16 | Recovery tu log                             | `test_tc16_recover_endpoint_returns_recovery_from_log`            | Pass                                   |

## 3) Giai thich chi tiet case fail 1 ben (A hoac B)

Day la phan trong tam de test kieu "failed mot ben" mot cach on dinh trong unit test.

### 3.1 Fail ben A tai Phase 1 (Prepare)

Trong test:

1. Mock `xa_prepare_participant` de nem exception khi participant la debit (`is_debit=True`, tuong ung Bank A).
2. Bank B van cho prepare binh thuong.
3. Ky vong coordinator rollback toan bo (`rollback_xa_all` duoc goi).

KQ mong doi:

1. `success=False`
2. Message chua "Phase 1"
3. Khong co commit nao duoc ghi nhan.

### 3.2 Fail ben B tai Phase 1 (Prepare)

Tuong tu A, nhung nem exception khi `is_debit=False` (participant nhan tien).

### 3.3 Fail ben B tai Phase 2 (Commit lech pha)

Trong test:

1. A commit thanh cong.
2. B commit nem loi.
3. He thong vao nhanh partial commit, rollback XA ben B va chay compensation ben A.

KQ mong doi:

1. Response co `partial_failure=True`
2. Co co `compensation` va message canh bao/day thong tin bu tru.

## 4) Cac nguyen tac test duoc dung

1. Test 2PC core + recovery dung mock de deterministic (khong phu thuoc DB that, khong can kill process that).
2. Validation/business test thong qua Flask test client.
3. Recovery test gia lap state XA RECOVER + transaction_log bang fake connection/cursor.
4. Giu test nhe de chay nhanh trong CI.

## 5) Sua loi trong code de test on dinh

## 5.1 Sua parse amount trong transfer route

File: `backend/routes/transfer.py`

Van de:

1. Truoc day `amount = float(...)` co the nem `ValueError` neu client gui string.

Da sua:

1. Boc `float(...)` trong `try/except (TypeError, ValueError)`.
2. Tra ve HTTP 400 + message "So tien khong hop le".

Y nghia:

1. API khong con crash voi input sai kieu.
2. Phu hop testcase validation (TC12 va test transfer cu).

## 5.2 Sua typo patch target trong test recover cu

File: `tests/test_transfer.py`

Da sua:

1. `routes.recover.recover_in_doubt_transactions` -> `routes.recovery.recover_in_doubt_transactions`.

## 6) Cach chay test

### 6.1 Chay bo test moi + transfer test

```powershell
python -m pytest -q tests/test_2pc_matrix.py tests/test_transfer.py
```

Ket qua hien tai:

1. 34 passed
2. 1 xfailed (TC14)

### 6.2 Chay toan bo test

```powershell
python -m pytest -q
```

## 7) Cau hinh va pham vi

### 7.1 Timeout trong 2PC

File: `backend/config.py`

1. `PREPARE_TIMEOUT = 10` (giay)

### 7.2 Request timeout trong script Toxiproxy

File: `test_toxiproxy.py`

1. `REQUEST_TIMEOUT = 30` giay
2. Script da cap nhat de dung `reset_peer` thay `close_stream`.
3. `slicer` da dung dung attributes: `average_size`, `size_variation`, `delay`.

## 8) Cach test network fault (tham khao nhanh)

1. Xoa toxic cu: chon `E` trong menu test_toxiproxy.py.
2. Test bandwidth (M):
3. 64 KB/s: cham nhe
4. 8 KB/s: cham ro
5. 1 KB/s: rat cham nhung login van co the pass do payload nho
6. Test slicer (P):
7. pass cham vua: `120 40 5000`
8. fail timeout: `10 2 35000000` (voi timeout client 30s)

## 9) Gioi han hien tai va huong tiep theo

### 9.1 TC14 dang XFAIL

Ly do:

1. Chua co idempotency key hoac duplicate-request dedupe trong API transfer.

Neu muon pass TC14 theo dung expectation "chi xu ly 1 lan", can bo sung:

1. Idempotency-Key header hoac request fingerprint + TTL.
2. Co che luu va tra lai ket qua cho request duplicate.

### 9.2 Concurrency thuc chien

Test hien tai cover muc coordinator khong crash trong concurrent call co mock.
De nang cap sat thuc te, can them integration test voi DB that + transaction lock assertion.

## 10) Tom tat ket qua

1. Da trien khai bo testcase map theo TC01-TC16 bang test tu dong.
2. Da cover ro nhat nhom "fail 1 ben" (A/B) va recovery.
3. Da sua 2 van de ky thuat de bo test on dinh (parse amount, patch typo).
4. Da co tai lieu day du de chay/test/hieu co che.
