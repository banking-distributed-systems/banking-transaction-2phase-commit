# Demo TC06-TC16 tren UI/API

Tat ca token ben duoi nhap vao o **Noi dung chuyen khoan**. Neu khong nhap token thi giao dich chay binh thuong.

Tai khoan demo thuong dung:

- Nguon: `102938475612`
- Dich: `203847569801`
- So tien: `50000`

Truoc khi chay cac case crash, nen dam bao trigger TC03 da tat:

```powershell
docker exec mysql2 mysql -uroot -proot bank2 -e "DROP TRIGGER IF EXISTS reject_bank_b_prepare;"
```

## TC06 - Coordinator crash truoc commit

Noi dung chuyen khoan:

```text
TC06_CRASH_BEFORE_COMMIT
```

Flow: A/B da prepare, coordinator crash khi log van la `PREPARING`.
Sau khi chay lai backend, recovery se rollback va phase thanh `ABORTED`.

## TC07 - Crash sau prepare

Noi dung chuyen khoan:

```text
TC07_CRASH_AFTER_PREPARE
```

Flow: A/B da `PREPARED`, coordinator crash truoc quyet dinh commit.
Sau khi chay lai backend, recovery se commit cac XA prepared va phase thanh `COMMITTED`.

## TC08 - In-doubt khi dang committing

Noi dung chuyen khoan:

```text
TC08_CRASH_DURING_COMMITTING
```

Flow: log da vao `COMMITTING`, coordinator crash truoc khi gui commit.
Sau khi chay lai backend hoac bam Recovery thu cong, phase thanh `COMMITTED`.

## TC09 - Commit gui nhieu lan

Noi dung chuyen khoan:

```text
TC09_COMMIT_TWICE
```

Flow: coordinator gui XA COMMIT lan dau thanh cong, gui lai lan hai khong lam xu ly trung.
Ky vong response thanh cong, phase `COMMITTED`.

## TC10 - Rollback gui nhieu lan

Noi dung chuyen khoan:

```text
TC10_ROLLBACK_TWICE
```

Flow: coordinator gui XA ROLLBACK hai lan.
Ky vong response loi demo, phase `ABORTED`, so du khong doi.

## TC11 - Concurrency

Mo hai tab UI hoac gui hai request API cung luc voi cung tai khoan nguon. Ky vong server khong crash va moi request co `tx_id` rieng.

## TC12 - Chuyen tien 0 hoac am

Nhap so tien `0` hoac so am tren UI. Ky vong API tra loi validation error, khong tao giao dich 2PC thanh cong.

## TC13 - Tai khoan khong ton tai

Nhap tai khoan dich khong co, vi du `999999999999`. Ky vong API bao tai khoan dich khong ton tai.

## TC14 - Double submit

Frontend da gui `Idempotency-Key` cho moi lan chuyen. De demo ro nhat bang API, gui lai cung body va cung header `Idempotency-Key`; lan hai se tra response da luu voi `idempotent_replay: true`.

## TC15 - Logging phase

Sau moi giao dich, xem dashboard transaction gan day hoac query:

```powershell
docker exec mysql mysql -uroot -proot bank1 -e "SELECT tx_id, phase, description FROM transaction_log ORDER BY id DESC LIMIT 10;"
```

## TC16 - Recovery tu log

Dung mot trong cac token crash `TC06_CRASH_BEFORE_COMMIT`, `TC07_CRASH_AFTER_PREPARE`, `TC08_CRASH_DURING_COMMITTING`, sau do chay lai backend hoac goi:

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:5000/api/recover"
```
