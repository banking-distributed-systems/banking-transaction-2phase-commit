"""
Test script cho Toxiproxy
Chạy: python test_toxiproxy.py
"""

import requests
import time
import json

API_VIA_PROXY = "http://localhost:8666/api"
API_DIRECT = "http://localhost:5000/api"

# Giá trị mặc định
DEFAULT_LATENCY = 10000   # 10 giây
DEFAULT_TIMEOUT = 5000     # 5 giây
REQUEST_TIMEOUT = 5  # Timeout cho request đến proxy (nên lớn hơn timeout của toxic)

def print_response(res):
    """In response đẹp"""
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print()


def get_input(prompt, default_value, input_type=int):
    """Lấy input từ user với giá trị mặc định"""
    try:
        value = input(f"{prompt} (default: {default_value}): ").strip()
        if not value:
            return default_value
        return input_type(value)
    except ValueError:
        print(f"  → Giá trị không hợp lệ, dùng mặc định: {default_value}")
        return default_value


def create_proxy():
    """Tạo proxy"""
    print("\n" + "=" * 60)
    print("TẠO PROXY")
    print("=" * 60)

    # Xóa proxy cũ nếu có
    try:
        requests.delete("http://localhost:8474/proxies/vbank_api", timeout=REQUEST_TIMEOUT)
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
            timeout=REQUEST_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("✅ Tạo proxy thành công!")
            print(f"   Listen: 0.0.0.0:8666")
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
        res = requests.delete("http://localhost:8474/proxies/vbank_api", timeout=REQUEST_TIMEOUT)
        if res.status_code in [200, 204]:
            print("✅ Xóa proxy thành công!")
        else:
            print(f"❌ Lỗi: {res.status_code}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_latency():
    """Thêm latency toxic với giá trị từ user"""
    print("\n" + "=" * 60)
    print("THÊM LATENCY (Network Delay)")
    print("=" * 60)

    # Lấy latency từ user
    latency = get_input("Nhập latency (ms)", DEFAULT_LATENCY)

    toxic = {
        "name": "latency",
        "type": "latency",
        "attributes": {
            "latency": latency
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=REQUEST_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm latency thành công!")
            print(f"   Latency: {latency}ms ({latency/1000:.1f} giây)")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_timeout():
    """Thêm timeout toxic với giá trị từ user"""
    print("\n" + "=" * 60)
    print("THÊM TIMEOUT (Connection Timeout)")
    print("=" * 60)

    # Lấy timeout từ user
    timeout = get_input("Nhập timeout (ms)", DEFAULT_TIMEOUT)

    toxic = {
        "name": "timeout",
        "type": "timeout",
        "attributes": {
            "timeout": timeout
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=REQUEST_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm timeout thành công!")
            print(f"   Timeout: {timeout}ms ({timeout/1000:.1f} giây)")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_both_latency_and_timeout():
    """Thêm cả latency và timeout, giải thích sự khác biệt"""
    print("\n" + "=" * 60)
    print("THÊM LATENCY VÀ TIMEOUT CÙNG LÚC")
    print("=" * 60)

    # Lấy giá trị từ user
    latency = get_input("Nhập latency (ms)", DEFAULT_LATENCY)
    timeout = get_input("Nhập timeout (ms)", DEFAULT_TIMEOUT)

    print("\n" + "-" * 60)
    print("📊 SO SÁNH LATENCY vs TIMEOUT:")
    print("-" * 60)

    if latency > timeout:
        print(f"""
⚠️  LATENCY ({latency}ms) > TIMEOUT ({timeout}ms)

→ Request sẽ bị TIMEOUT trước khi nhận được response!
→ Server không kịp phản hồi trong thời gian timeout
→ Kết quả: Connection timeout error
""")
    elif latency == timeout:
        print(f"""
⚖️  LATENCY ({latency}ms) = TIMEOUT ({timeout}ms)

→ Request có thể thành công hoặc timeout tùy timing
→ Rất nhạy cảm với timing
""")
    else:
        print(f"""
✅ LATENCY ({latency}ms) < TIMEOUT ({timeout}ms)

→ Request sẽ hoàn thành trước khi timeout!
→ Server có đủ thời gian để phản hồi
""")

    print("-" * 60)

    # Thêm latency
    toxic_latency = {
        "name": "latency",
        "type": "latency",
        "attributes": {
            "latency": latency
        }
    }

    # Thêm timeout
    toxic_timeout = {
        "name": "timeout",
        "type": "timeout",
        "attributes": {
            "timeout": timeout
        }
    }

    try:
        # Thêm latency
        res1 = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic_latency,
            timeout=REQUEST_TIMEOUT
        )
        if res1.status_code in [200, 201]:
            print(f"✅ Thêm latency: {latency}ms")
        else:
            print(f"❌ Lỗi thêm latency: {res1.status_code}")

        # Thêm timeout
        res2 = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic_timeout,
            timeout=REQUEST_TIMEOUT
        )
        if res2.status_code in [200, 201]:
            print(f"✅ Thêm timeout: {timeout}ms")
        else:
            print(f"❌ Lỗi thêm timeout: {res2.status_code}")

    except Exception as e:
        print(f"❌ Lỗi: {e}")


def clear_toxics():
    """Xóa tất cả toxic"""
    print("\n" + "=" * 60)
    print("XÓA TẤT CẢ TOXICS")
    print("=" * 60)

    try:
        # Lấy danh sách toxics
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=REQUEST_TIMEOUT)

        if res.status_code != 200:
            print(f"❌ Không lấy được proxy: {res.status_code}")
            return

        data = res.json()
        toxics = data.get("toxics", [])

        if not toxics:
            print("⚪ Không có toxic nào để xóa")
            return

        # Xóa từng toxic
        for toxic in toxics:
            name = toxic.get("name")
            del_res = requests.delete(
                f"http://localhost:8474/proxies/vbank_api/toxics/{name}",
                timeout=REQUEST_TIMEOUT
            )

            if del_res.status_code in [200, 204]:
                print(f"✅ Đã xóa toxic: {name}")
            else:
                print(f"❌ Lỗi xóa {name}: {del_res.status_code}")

        print("\n🎉 Đã xóa toàn bộ toxics!")

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
        res = requests.get(f"{API_DIRECT}/accounts", timeout=REQUEST_TIMEOUT)
        print(f"    ✅ Backend OK - Status: {res.status_code}")
    except Exception as e:
        print(f"    ❌ Backend ERROR: {e}")
        print("    → Cần khởi động backend: cd backend && python app.py")

    # 2. Kiểm tra proxy
    print("\n[2] Kiểm tra Toxiproxy...")
    try:
        res = requests.get("http://localhost:8474/proxies", timeout=REQUEST_TIMEOUT)
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
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=REQUEST_TIMEOUT)
        print(f"    ✅ Proxy OK - Status: {res.status_code}")
    except Exception as e:
        print(f"    ❌ Proxy ERROR: {e}")
        print("    → Proxy chưa được tạo hoặc upstream không đúng")


def show_proxy_info():
    """Xem thông tin chi tiết của proxy hiện tại"""
    print("\n" + "=" * 60)
    print("THÔNG TIN PROXY HIỆN TẠI")
    print("=" * 60)

    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=REQUEST_TIMEOUT)
        if res.status_code == 404:
            print("❌ Proxy chưa được tạo!")
            print("   Vui lòng chọn 'A' để tạo proxy")
            return

        if res.status_code != 200:
            print(f"❌ Lỗi: {res.status_code}")
            return

        data = res.json()

        print(f"\n📋 Tên proxy: {data.get('name', 'N/A')}")
        print(f"   Listen: {data.get('listen', 'N/A')}")
        print(f"   Upstream: {data.get('upstream', 'N/A')}")
        print(f"   Enabled: {data.get('enabled', 'N/A')}")
        print(f"   Mode: {data.get('mode', 'N/A')}")

        # Hiển thị toxics
        toxics = data.get('toxics', [])
        print(f"\n📦 Toxics ({len(toxics)} active):")

        if not toxics:
            print("   ⚪ Không có toxic nào")
        else:
            for toxic in toxics:
                print(f"\n   🔸 {toxic.get('name', 'N/A')}")
                print(f"      Type: {toxic.get('type', 'N/A')}")
                print(f"      Stream: {toxic.get('stream', 'N/A')}")
                print(f"      Enabled: {toxic.get('enabled', 'N/A')}")

                # Hiển thị attributes
                attrs = toxic.get('attributes', {})
                if 'latency' in attrs:
                    latency_val = attrs['latency']
                    print(f"      Latency: {latency_val}ms ({latency_val/1000:.1f} giây)")
                if 'timeout' in attrs:
                    timeout_val = attrs['timeout']
                    print(f"      Timeout: {timeout_val}ms ({timeout_val/1000:.1f} giây)")
                if 'jitter' in attrs:
                    print(f"      Jitter: {attrs['jitter']}ms")
                if 'bytes' in attrs:
                    print(f"      Bytes: {attrs['bytes']}")

        # Phân tích latency vs timeout
        latency_ms = 0
        timeout_ms = 0
        for t in toxics:
            attrs = t.get('attributes', {})
            if t.get('type') == 'latency':
                latency_ms = attrs.get('latency', 0)
            elif t.get('type') == 'timeout':
                timeout_ms = attrs.get('timeout', 0)

        if latency_ms > 0 and timeout_ms > 0:
            print(f"\n📊 PHÂN TÍCH:")
            if latency_ms > timeout_ms:
                print(f"   ⚠️  Latency ({latency_ms}ms) > Timeout ({timeout_ms}ms)")
                print(f"   → Request SẼ bị TIMEOUT!")
            elif latency_ms == timeout_ms:
                print(f"   ⚖️  Latency ({latency_ms}ms) = Timeout ({timeout_ms}ms)")
                print(f"   → Kết quả không nhất quán")
            else:
                print(f"   ✅ Latency ({latency_ms}ms) < Timeout ({timeout_ms}ms)")
                print(f"   → Request sẽ thành công (chậm hơn)")

    except Exception as e:
        print(f"❌ Lỗi: {e}")


def test_health_check():
    """Test 1: Health check"""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)

    try:
        res = requests.get(f"{API_VIA_PROXY}/", timeout=REQUEST_TIMEOUT)
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
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=REQUEST_TIMEOUT)
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
        res = requests.post(f"{API_VIA_PROXY}/login", json=data, timeout=REQUEST_TIMEOUT)
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
        res = requests.post(f"{API_VIA_PROXY}/transfer", json=data, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        print(f"Status: {res.status_code}")
        print(f"Time: {elapsed:.2f}s")
        print_response(res.json())
    except requests.exceptions.Timeout:
        print("Timeout! Server không phản hồi")
    except Exception as e:
        print(f"Lỗi: {e}")
        print("\n💡 Gợi ý: Chạy test '7' để kiểm tra services trước")


def test_transfer_with_current_toxics():
    """Test 5: Transfer với toxics hiện tại"""
    print("\n" + "=" * 60)
    print("TEST 5: Transfer với Toxics hiện tại")
    print("=" * 60)

    # Lấy thông tin toxic hiện tại
    latency_ms = 0
    timeout_ms = 0

    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            toxics = data.get('toxics', [])

            for t in toxics:
                attrs = t.get('attributes', {})
                if t.get('type') == 'latency':
                    latency_ms = attrs.get('latency', 0)
                elif t.get('type') == 'timeout':
                    timeout_ms = attrs.get('timeout', 0)

            if latency_ms > 0 or timeout_ms > 0:
                print(f"📊 Toxics đang active:")
                if latency_ms > 0:
                    print(f"   Latency: {latency_ms}ms ({latency_ms/1000:.1f}s)")
                if timeout_ms > 0:
                    print(f"   Timeout: {timeout_ms}ms ({timeout_ms/1000:.1f}s)")

                # Phân tích
                if latency_ms > timeout_ms:
                    print(f"\n⚠️  PHÂN TÍCH: Latency > Timeout")
                    print(f"   Request sẽ bị TIMEOUT!")
                elif latency_ms > 0 and timeout_ms > 0:
                    print(f"\n✅ PHÂN TÍCH: Latency < Timeout")
                    print(f"   Request sẽ thành công (chậm hơn bình thường)")
            else:
                print("⚠️  Không có toxics nào đang active!")
                print("   Vui lòng thêm latency/timeout trước khi test")
                return
        else:
            print("❌ Không lấy được thông tin proxy")
            return
    except Exception as e:
        print(f"Lỗi lấy thông tin toxic: {e}")
        return

    data = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 20000,
        "description": "Test với toxics"
    }

    try:
        start = time.time()
        print(f"\n🚀 Bắt đầu transfer lúc: {time.strftime('%H:%M:%S')}")
        res = requests.post(f"{API_VIA_PROXY}/transfer", json=data, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        print(f"🏁 Hoàn thành lúc: {time.strftime('%H:%M:%S')}")
        print(f"Status: {res.status_code}")
        print(f"Thời gian: {elapsed:.2f}s")

        # Phân tích kết quả
        if elapsed > (timeout_ms / 1000) and timeout_ms > 0:
            print(f"\n❌ KẾT QUẢ: Request bị TIMEOUT!")
            print(f"   Thời gian thực ({elapsed:.2f}s) > Timeout ({timeout_ms/1000}s)")
        else:
            print(f"\n✅ KẾT QUẢ: Request thành công!")

        print_response(res.json())
    except requests.exceptions.Timeout:
        print(f"\n❌ KẾT QUẢ: Request bị TIMEOUT exception!")
        print(f"   Request không nhận được response trong timeout")
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
        print("5. Transfer với Toxics hiện tại")
        print("---")
        print("A. Tạo Proxy")
        print("B. Xóa Proxy")
        print("C. Thêm Latency (nhập ms)")
        print("D. Thêm Timeout (nhập ms)")
        print("F. Thêm CẢ Latency + Timeout (có giải thích)")
        print("S. Xem thông tin Proxy & Toxics")
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
            test_transfer_with_current_toxics()
        elif choice == "A":
            create_proxy()
        elif choice == "B":
            delete_proxy()
        elif choice == "C":
            add_latency()
        elif choice == "D":
            add_timeout()
        elif choice == "F":
            add_both_latency_and_timeout()
        elif choice == "S":
            show_proxy_info()
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
    ║       Hỗ trợ nhập Latency/Timeout tùy chỉnh        ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    # Tự động kiểm tra services trước
    check_services()

    # Hiển thị menu
    menu()
