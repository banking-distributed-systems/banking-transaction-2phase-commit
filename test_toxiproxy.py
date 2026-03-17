"""
Test script cho Toxiproxy
Chạy: python test_toxiproxy.py
"""

import requests
import time
import json

API_VIA_PROXY = "http://localhost:8666/api"
API_DIRECT = "http://localhost:5000/api"


def print_response(res):
    """In response đẹp"""
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print()


def create_proxy():
    """Tạo proxy"""
    print("\n" + "=" * 60)
    print("TẠO PROXY")
    print("=" * 60)

    # Xóa proxy cũ nếu có
    try:
        requests.delete("http://localhost:8474/proxies/vbank_api", timeout=5)
        print("Đã xóa proxy cũ")
    except:
        pass

    # Tạo proxy mới
    proxy_config = {
        "name": "vbank_api",
        "listen": "0.0.0.0:8666",
        "upstream": "host.docker.internal:5000"
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies",
            json=proxy_config,
            timeout=5
        )
        if res.status_code in [200, 201]:
            print("✅ Tạo proxy thành công!")
            print(f"   Listen: 127.0.0.1:8666")
            print(f"   Upstream: host.docker.internal:5000")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def delete_proxy():
    """Xóa proxy"""
    print("\n" + "=" * 60)
    print("XÓA PROXY")
    print("=" * 60)

    try:
        res = requests.delete("http://localhost:8474/proxies/vbank_api", timeout=5)
        if res.status_code in [200, 204]:
            print("✅ Xóa proxy thành công!")
        else:
            print(f"❌ Lỗi: {res.status_code}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_latency():
    """Thêm latency toxic"""
    print("\n" + "=" * 60)
    print("THÊM LATENCY (10 giây)")
    print("=" * 60)

    toxic = {
        "name": "latency",
        "type": "latency",
        "attributes": {
            "latency": 10000
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=5
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm latency thành công!")
            print("   Latency: 10000ms (10 giây)")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_timeout():
    """Thêm timeout toxic"""
    print("\n" + "=" * 60)
    print("THÊM TIMEOUT (5 giây)")
    print("=" * 60)

    toxic = {
        "name": "timeout",
        "type": "timeout",
        "attributes": {
            "timeout": 5000
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=5
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm timeout thành công!")
            print("   Timeout: 5000ms (5 giây)")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def clear_toxics():
    """Xóa tất cả toxic"""
    print("\n" + "=" * 60)
    print("XÓA TẤT CẢ TOXICS")
    print("=" * 60)

    try:
        res = requests.delete("http://localhost:8474/proxies/vbank_api/toxics", timeout=5)
        if res.status_code in [200, 204]:
            print("✅ Xóa tất cả toxic thành công!")
        else:
            print(f"❌ Lỗi: {res.status_code}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def check_services():
    """Kiểm tra các service đang chạy"""
    print("=" * 60)
    print("KIỂM TRA SERVICES")
    print("=" * 60)

    # 1. Kiểm tra backend trực tiếp
    print("\n[1] Kiểm tra backend (direct)...")
    try:
        res = requests.get(f"{API_DIRECT}/accounts", timeout=5)
        print(f"    ✅ Backend OK - Status: {res.status_code}")
    except Exception as e:
        print(f"    ❌ Backend ERROR: {e}")
        print("    → Cần khởi động backend: cd backend && python app.py")

    # 2. Kiểm tra proxy
    print("\n[2] Kiểm tra Toxiproxy...")
    try:
        res = requests.get("http://localhost:8474/proxies", timeout=5)
        proxies = res.json()
        print(f"    ✅ Toxiproxy OK - Status: {res.status_code}")

        # Hiển thị tất cả proxy
        if 'proxies' in proxies:
            for p in proxies['proxies']:
                print(f"\n    📋 Proxy: {p['name']}")
                print(f"       Listen: {p['listen']}")
                print(f"       Upstream: {p['upstream']}")
                print(f"       Enabled: {p['enabled']}")

        if 'proxies' in proxies and len(proxies['proxies']) == 0:
            print("    ⚠️  Chưa có proxy! Cần tạo proxy")
    except Exception as e:
        print(f"    ❌ Toxiproxy ERROR: {e}")
        print("    → Cần khởi động Toxiproxy:")
        print("    → docker run -d -p 8474:8474 -p 8666:8666 --name toxiproxy ghcr.io/shopify/toxiproxy")

    # 3. Kiểm tra proxy qua port 8666
    print("\n[3] Kiểm tra proxy (localhost:8666)...")
    try:
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=5)
        print(f"    ✅ Proxy OK - Status: {res.status_code}")
    except Exception as e:
        print(f"    ❌ Proxy ERROR: {e}")
        print("    → Proxy chưa được tạo hoặc upstream không đúng")


def test_health_check():
    """Test 1: Health check"""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)

    try:
        res = requests.get(f"{API_VIA_PROXY}/", timeout=5)
        print(f"Status: {res.status_code}")
        print_response(res.json())
    except Exception as e:
        print(f"Lỗi: {e}")
        print("\n💡 Gợi ý: Chạy test '7' để kiểm tra services trước")


def test_get_accounts():
    """Test 2: Lấy danh sách tài khoản"""
    print("\n" + "=" * 60)
    print("TEST 2: Get Accounts")
    print("=" * 60)

    try:
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=5)
        print(f"Status: {res.status_code}")
        print_response(res.json())
    except Exception as e:
        print(f"Lỗi: {e}")
        print("\n💡 Gợi ý: Chạy test '7' để kiểm tra services trước")


def test_login():
    """Test 3: Đăng nhập"""
    print("\n" + "=" * 60)
    print("TEST 3: Login")
    print("=" * 60)

    data = {
        "phone": "0901234567",
        "password": "123456"
    }

    try:
        res = requests.post(f"{API_VIA_PROXY}/login", json=data, timeout=5)
        print(f"Status: {res.status_code}")
        print_response(res.json())
    except Exception as e:
        print(f"Lỗi: {e}")
        print("\n💡 Gợi ý: Chạy test '7' để kiểm tra services trước")


def test_transfer():
    """Test 4: Chuyển tiền"""
    print("\n" + "=" * 60)
    print("TEST 4: Transfer (bình thường)")
    print("=" * 60)

    data = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 10000,
        "description": "Test qua proxy"
    }

    try:
        start = time.time()
        res = requests.post(f"{API_VIA_PROXY}/transfer", json=data, timeout=30)
        elapsed = time.time() - start
        print(f"Status: {res.status_code}")
        print(f"Time: {elapsed:.2f}s")
        print_response(res.json())
    except requests.exceptions.Timeout:
        print("Timeout! Server không phản hồi")
    except Exception as e:
        print(f"Lỗi: {e}")
        print("\n💡 Gợi ý: Chạy test '7' để kiểm tra services trước")


def test_transfer_with_latency():
    """Test 5: Transfer với latency"""
    print("\n" + "=" * 60)
    print("TEST 5: Transfer với Latency 10s")
    print("=" * 60)
    print("⚠️  ĐẢM BẢO ĐÃ THÊM LATENCY TRONG TOXIPROXY TRƯỚC!")
    print("   Nhập 'C' trong menu để thêm latency")
    print()

    data = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 20000,
        "description": "Test latency"
    }

    try:
        start = time.time()
        print(f"Bắt đầu: {time.strftime('%H:%M:%S')}")
        res = requests.post(f"{API_VIA_PROXY}/transfer", json=data, timeout=30)
        elapsed = time.time() - start
        print(f"Hoàn thành: {time.strftime('%H:%M:%S')}")
        print(f"Status: {res.status_code}")
        print(f"Thời gian: {elapsed:.2f}s")
        print_response(res.json())
    except requests.exceptions.Timeout:
        print("Timeout! Request bị delay quá lâu")
    except Exception as e:
        print(f"Lỗi: {e}")
        print("\n💡 Gợi ý: Chạy test '7' để kiểm tra services trước")


def test_transfer_timeout():
    """Test 6: Kịch bản 5 - Timeout"""
    print("\n" + "=" * 60)
    print("TEST 6: Kịch bản 5 - Timeout")
    print("=" * 60)
    print("⚠️  ĐẢM BẢO ĐÃ THÊM TIMEOUT TRONG TOXIPROXY TRƯỚC!")
    print("   Nhập 'D' trong menu để thêm timeout")
    print()

    data = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 30000,
        "description": "Test timeout"
    }

    try:
        start = time.time()
        res = requests.post(f"{API_VIA_PROXY}/transfer", json=data, timeout=30)
        elapsed = time.time() - start
        print(f"Status: {res.status_code}")
        print(f"Time: {elapsed:.2f}s")
        print_response(res.json())
    except requests.exceptions.Timeout:
        print("Timeout! Request bị timeout")
    except Exception as e:
        print(f"Lỗi: {e}")


def menu():
    """Menu chọn test"""
    while True:
        print("\n" + "=" * 60)
        print("CHỌN TEST CASE:")
        print("=" * 60)
        print("1. Health Check")
        print("2. Get Accounts")
        print("3. Login")
        print("4. Transfer (bình thường)")
        print("5. Transfer với Latency 10s")
        print("6. Transfer với Timeout (Kịch bản 5)")
        print("---")
        print("A. Tạo Proxy")
        print("B. Xóa Proxy")
        print("C. Thêm Latency (10s)")
        print("D. Thêm Timeout (5s)")
        print("E. Xóa tất cả Toxics")
        print("7. KIỂM TRA SERVICES")
        print("0. Thoát")
        print()

        choice = input("Nhập số/chữ: ").strip().upper()

        if choice == "0":
            print("Thoát!")
            break
        elif choice == "1":
            test_health_check()
        elif choice == "2":
            test_get_accounts()
        elif choice == "3":
            test_login()
        elif choice == "4":
            test_transfer()
        elif choice == "5":
            test_transfer_with_latency()
        elif choice == "6":
            test_transfer_timeout()
        elif choice == "A":
            create_proxy()
        elif choice == "B":
            delete_proxy()
        elif choice == "C":
            add_latency()
        elif choice == "D":
            add_timeout()
        elif choice == "E":
            clear_toxics()
        elif choice == "7":
            check_services()
        else:
            print("Lựa chọn không hợp lệ!")


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║       V-Bank 2PC - Toxiproxy Test Script             ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # Tự động kiểm tra services trước
    check_services()

    # Hiển thị menu
    menu()
