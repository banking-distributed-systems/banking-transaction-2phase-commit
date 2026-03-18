# Hướng dẫn Test với Toxiproxy (Windows)

> Hướng dẫn test các kịch bản lỗi mạng cho V-Bank 2PC sử dụng Toxiproxy trên Windows

---

## Mục lục

1. [Tổng quan](#tổng-quan)
2. [Cài đặt Toxiproxy](#cài-đặt-toxiproxy)
3. [Khởi động services](#khởi-động-services)
4. [Tạo Proxy](#tạo-proxy)
5. [Test Cases](#test-cases)
6. [Reset Toxic](#reset-toxic)

---

## Tổng quan

Toxiproxy là công cụ proxy cho phép mô phỏng các tình huống mạng không ổn định:

- **Latency** - Delay mạng
- **Timeout** - Mất kết nối
- **Packet Loss** - Mất gói tin
- **Bandwidth** - Giới hạn băng thông

**Trong V-Bank 2PC, Toxiproxy giúp test các kịch bản:**

- KB 4: Bank B không phản hồi (timeout)
- KB 5: Network latency cao → timeout ở Phase 1

---

## Cài đặt Toxiproxy

### Khởi động Toxiproxy bằng Docker

```powershell
docker run -d -p 8474:8474 -p 8666:8666 --name toxiproxy ghcr.io/shopify/toxiproxy
```

**Kiểm tra Toxiproxy đang chạy:**

```powershell
docker ps | Select-String toxiproxy
```

---

## Khởi động Services

### 1. Khởi động Database

```powershell
docker-compose up -d
```

### 2. Khởi động Backend

```powershell
cd backend
python app.py
```

**Kiểm tra backend đang chạy:**

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/accounts"
```

---

## Tạo Proxy

### Tạo proxy cho API

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{
    "User-Agent" = "curl"
  } `
  -Body '{
    "name": "vbank_api",
    "listen": "127.0.0.1:8666",
    "upstream": "host.docker.internal:5000"
  }'
```

**Giải thích:**

- `name`: Tên proxy (đặt tên gì cũng được)
- `listen`: Port để client kết nối (thay vì 5000, dùng 8666)
- `upstream`: Địa chỉ thật của backend

### Kiểm tra proxy

```powershell
# Test qua proxy
curl.exe http://localhost:8474/proxies

# Test trực tiếp (bypass proxy)
Invoke-RestMethod -Uri "http://localhost:5000/api/accounts"

# Gọi qua proxy
curl.exe http://localhost:8666/
```

Nếu cả hai đều trả về kết quả → ✅ Proxy hoạt động

---

## Test Cases

Nếu muốn test ở giao diện thì đổi api tại app.js

### Test Case 1: Latency (Network chậm)

Mô phỏng network chậm 10 giây.

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" `
  -Method POST `
  -ContentType "application/json" `
   -Headers @{
    "User-Agent" = "curl"
  } `
  -Body '{
    "name": "latency",
    "type": "latency",
    "attributes": {
      "latency": 10000
    }
  }'
```

**Test với Python:**

```python
import requests
import time

start = time.time()
try:
    res = requests.get("http://localhost:8666/api/accounts", timeout=10)
    print(f"Response: {res.json()}")
except requests.exceptions.Timeout:
    print("Timeout!")
except Exception as e:
    print(f"Error: {e}")

print(f"Time: {time.time() - start}s")
```

**Kết quả mong đợi:**

- Request bị delay ~3 giây
- Vẫn thành công (nếu < timeout)

---

### Test Case 2: Timeout (Mất kết nối)

Mô phỏng server không phản hồi.

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{
    "User-Agent" = "curl"
  } `
  -Body '{
    "name": "timeout",
    "type": "timeout",
    "attributes": {
      "timeout": 5000
    }
  }'
```

**Test với Python:**

```python
import requests

try:
    res = requests.get("http://localhost:8666/api/accounts", timeout=2)
    print(f"Response: {res.json()}")
except requests.exceptions.Timeout:
    print("Timeout! Server khong phan hoi")
except Exception as e:
    print(f"Error: {e}")
```

**Kết quả mong đợi:**

```
Timeout! Server khong phan hoi
```

---

### Test Case 3: Limit Data (Packet Loss)

Mô phỏng mất gói tin.

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{
    "User-Agent" = "curl"
  } `
  -Body '{
    "name": "limit_data",
    "type": "limit_data",
    "attributes": {
      "bytes": 10
    }
  }'
```

**Test:**

```python
import requests

try:
    res = requests.get("http://localhost:8666/api/accounts", timeout=5)
    print(f"Response: {res.json()}")
except Exception as e:
    print(f"Error: {e}")
```

**Kết quả mong đợi:**

- Lỗi connection reset hoặc response truncated

---

### Test Case 4: Kịch bản 5 - Timeout ở Phase 1

Test khi Bank B phản hồi quá chậm.

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{
    "User-Agent" = "curl"
  } `
  -Body '{
    "name": "slow_bank",
    "type": "latency",
    "attributes": {
      "latency": 15000
    }
  }'
```

**Test transfer:**

```python
import requests

data = {
    "from_account_number": "102938475612",
    "to_account_number": "203847569801",
    "amount": 50000,
    "description": "Test timeout"
}

try:
    res = requests.post("http://localhost:8666/api/transfer", json=data, timeout=20)
    result = res.json()
    print(f"Status: {res.status_code}")
    print(f"Response: {result}")
except requests.exceptions.Timeout:
    print("Timeout! Kịch bản 5")
except Exception as e:
    print(f"Error: {e}")
```

**Kết quả mong đợi:**

```json
{
  "status": "error",
  "message": "Kịch bản 5 — Timeout: Bank B (đích) không phản hồi trong 10s...",
  "timeout": true,
  "tx_id": "VB..."
}
```

---

### Test Case 5: Partial Failure (Kịch bản 4)

Test khi Bank A commit xong nhưng Bank B fail.

```powershell
# Reset toxic trước
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics/latency" -Method DELETE

# Tạo scenario: Bank B fail
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{
    "User-Agent" = "curl"
  } `
  -Body '{
    "name": "bank_b_fail",
    "type": "close_stream"
  }'
```

**Test transfer:**

```python
import requests

data = {
    "from_account_number": "102938475612",
    "to_account_number": "203847569801",
    "amount": 50000,
    "description": "Test partial failure"
}

res = requests.post("http://localhost:8666/api/transfer", json=data, timeout=10)
result = res.json()

print(f"Status: {res.status_code}")
print(f"Response: {result}")
```

**Kết quả mong đợi:**

```json
{
  "status": "error",
  "message": "Lỗi COMMIT lệch pha (Kịch bản 4)...",
  "partial_failure": true,
  "compensation": true,
  "tx_id": "VB..."
}
```

---

### Test Case 6: Retry Logic

Test retry khi mạng không ổn định.

```python
import requests
import time

def call_with_retry(url, data=None, max_retries=3, delay=1):
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries}")
            if data:
                res = requests.post(url, json=data, timeout=5)
            else:
                res = requests.get(url, timeout=5)
            return res.json()
        except requests.exceptions.Timeout:
            print(f"Attempt {attempt + 1} timeout")
            if attempt < max_retries - 1:
                time.sleep(delay)
        except Exception as e:
            print(f"Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)

    return {"error": "All retries failed"}

result = call_with_retry("http://localhost:8666/api/accounts")
print(f"Final result: {result}")
```

---

### Test Case 7: Fallback Data

Test fallback khi API không khả dụng.

```python
import requests

def get_accounts_with_fallback():
    try:
        res = requests.get("http://localhost:8666/api/accounts", timeout=5)
        if res.status_code == 200:
            return res.json()
    except:
        pass

    return [{"name": "Fallback User", "account_number": "0000000000", "balance": 0}]

result = get_accounts_with_fallback()
print(f"Accounts: {result}")
```

---

## Reset Toxic

**RẤT QUAN TRỌNG:** Sau mỗi test cần reset toxic để không ảnh hưởng test khác.

### Xóa một toxic cụ thể

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics/latency" -Headers @{
    "User-Agent" = "curl"
  } ` -Method DELETE
```

### Xóa tất cả toxic

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" -Headers @{
    "User-Agent" = "curl"
  } ` -Method DELETE
```

### Xóa proxy

```powershell
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api" -Headers @{
    "User-Agent" = "curl"
  } ` -Method DELETE
```

### Kiểm tra trạng thái

Nếu lỗi thì xóa Header đi

```powershell
# Xem danh sách proxy
Invoke-RestMethod -Uri "http://localhost:8474/proxies" -Headers @{
    "User-Agent" = "curl"
  } `

# Xem toxic của proxy
Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api" -Headers @{
    "User-Agent" = "curl"
  } `
```

---

## Quick Reference

| Mục đích     | PowerShell Command                                                                                                                                                                               |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Tạo proxy    | `Invoke-RestMethod -Uri "http://localhost:8474/proxies" -Method POST -ContentType "application/json" -Body '{"name":"vbank_api","listen":"0.0.0.0:8666","upstream":"localhost:5000"}'`           |
| Thêm latency | `Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" -Method POST -ContentType "application/json" -Body '{"name":"latency","type":"latency","attributes":{"latency":3000}}'` |
| Thêm timeout | `Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" -Method POST -ContentType "application/json" -Body '{"name":"timeout","type":"timeout","attributes":{"timeout":5000}}'` |
| Xem proxy    | `Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api"`                                                                                                                               |
| Xóa toxic    | `Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api/toxics" -Method DELETE`                                                                                                         |
| Xóa proxy    | `Invoke-RestMethod -Uri "http://localhost:8474/proxies/vbank_api" -Method DELETE`                                                                                                                |

---

## Troubleshooting

### Proxy không hoạt động

```powershell
# Kiểm tra toxiproxy đang chạy
docker ps | Select-String toxiproxy

# Xem logs
docker logs toxiproxy
```

### upstream không connect được

```powershell
# Kiểm tra backend đang chạy
Invoke-RestMethod -Uri "http://localhost:5000/api/accounts" -Headers @{
    "User-Agent" = "curl"
  } `

# Kiểm tra proxy
Invoke-RestMethod -Uri "http://localhost:8474/proxies" -Headers @{
    "User-Agent" = "curl"
  } `
```

---

## Tài liệu tham khảo

- [Toxiproxy Documentation](https://github.com/Shopify/toxiproxy)
- [Toxiproxy HTTP API](https://github.com/Shopify/toxiproxy/blob/main/docs.md)
