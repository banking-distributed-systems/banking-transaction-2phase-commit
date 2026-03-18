"""
Test script cho Toxiproxy
Chạy: python test_toxiproxy.py
"""

import requests
import time
import json
import sys
import traceback

API_VIA_PROXY = "http://localhost:8666/api"
API_DIRECT = "http://localhost:5000/api"

# ============================================================
# DEBUG MODE - Bật để xem chi tiết
# ============================================================
DEBUG = True  # Bật debug để theo dõi

def debug_print(msg):
    """In debug message"""
    if DEBUG:
        print(f"[DEBUG] {msg}", flush=True)

# ============================================================
# CẤU HÌNH TIMEOUT - QUAN TRỌNG!
# ============================================================
API_TIMEOUT = 5           # thời gian client chấp nhận chờ api phản hồi khi gọi API Toxiproxy (ví dụ: tạo proxy, thêm toxic). Nếu vượt quá thì sẽ coi là lỗi.
REQUEST_TIMEOUT = 30       # thời gian client chờ toàn bộ quá trình request hoàn tất, bao gồm đi qua proxy và backend. Nếu vượt quá thì client sẽ tự hủy request.

# Giá trị mặc định cho toxic
DEFAULT_LATENCY = 1000    # 1 giây - Network delay
DEFAULT_TIMEOUT = 5000     # 5 giây - thời gian proxy chờ backend phải bắt đầu phản hồi, nếu backend ko gửi response trong thời gian này thì proxy sẽ đóng kết nối, thường là thời gian backend phản hồi + timeout > default timeout -> lỗi timeout, không phụ thuộc vào latency


def print_response(res):
    """In response đẹp - có xử lý lỗi JSON"""
    try:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except (TypeError, ValueError):
        # JSON bị cắt hoặc không parse được
        print(f"⚠️ Response bị cắt (truncated), không parse được JSON:")
        print(f"   Raw: {str(res)[:200]}...")
    print()


def safe_json_response(res):
    """Parse JSON response an toàn - xử lý truncated response"""
    try:
        return res.json()
    except ValueError:
        # Response bị cắt (truncated) do limit_data toxic
        print("⚠️ Response bị cắt (truncated), không parse được JSON!")
        print(f"   Raw response (first 500 chars): {res.text[:500]}")
        return None


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
        requests.delete("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
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
            timeout=API_TIMEOUT
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
        res = requests.delete("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        if res.status_code in [200, 204]:
            print("✅ Xóa proxy thành công!")
        else:
            print(f"❌ Lỗi: {res.status_code}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_latency():
    """Thêm latency toxic - tác động lên response (downstream)"""
    print("\n" + "=" * 60)
    print("THÊM LATENCY (Network Delay)")
    print("=" * 60)
    print("📌 Latency: Delay response từ server về client")

    # Lấy latency từ user
    latency = get_input("Nhập latency (ms)", DEFAULT_LATENCY)

    # Dùng timestamp để tránh trùng tên toxic
    toxic_name = f"latency_{int(time.time())}"

    toxic = {
        "name": toxic_name,
        "type": "latency",
        "stream": "downstream",  # Latency ở downstream
        "attributes": {
            "latency": latency
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm latency thành công!")
            print(f"   Latency: {latency}ms ({latency/1000:.1f} giây)")
            print(f"   Stream: downstream (delay response)")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_timeout():
    """Thêm timeout toxic - QUAN TRỌNG: phải dùng upstream!"""
    print("\n" + "=" * 60)
    print("THÊM TIMEOUT (Backend Timeout)")
    print("=" * 60)
    print("📌 Timeout: Chờ backend bắt đầu phản hồi")
    print("⚠️  QUAN TRỌNG: Phải dùng stream='upstream'!")

    # Lấy timeout từ user
    timeout = get_input("Nhập timeout (ms)", DEFAULT_TIMEOUT)

    # Kiểm tra giá trị an toàn
    if timeout < 3000:
        print(f"   ⚠️  CẢNH BÁO: Timeout {timeout}ms có thể quá nhỏ!")
        print(f"       Nên >= 3000ms để tránh false timeout")

    # DEBUG: Kiểm tra proxy trước khi thêm toxic
    debug_print("=" * 50)
    debug_print("DEBUG: Kiểm tra proxy TRƯỚC KHI thêm timeout...")
    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        debug_print(f"GET proxy status: {res.status_code}")
        if res.status_code == 200:
            proxy_data = res.json()
            debug_print(f"Proxy enabled: {proxy_data.get('enabled')}")
            debug_print(f"Proxy toxics: {proxy_data.get('toxics', [])}")
        else:
            debug_print(f"Lỗi lấy proxy: {res.text}")
    except Exception as e:
        debug_print(f"Lỗi kiểm tra proxy: {e}")
        traceback.print_exc()

    # Dùng timestamp để tránh trùng tên toxic
    toxic_name = f"timeout_{int(time.time())}"

    toxic = {
        "name": toxic_name,
        "type": "timeout",
        "stream": "upstream",  # 🔥 QUAN TRỌNG: phải là upstream!
        "attributes": {
            "timeout": timeout
        }
    }

    debug_print(f"Gửi request thêm timeout toxic: {toxic}")

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        debug_print(f"Response status: {res.status_code}")
        debug_print(f"Response body: {res.text}")

        if res.status_code in [200, 201]:
            print("✅ Thêm timeout thành công!")
            print(f"   Timeout: {timeout}ms ({timeout/1000:.1f} giây)")
            print(f"   Stream: upstream (chờ backend phản hồi)")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")

        # DEBUG: Kiểm tra proxy SAU KHI thêm toxic
        debug_print("=" * 50)
        debug_print("DEBUG: Kiểm tra proxy SAU KHI thêm timeout...")
        try:
            res_check = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
            if res_check.status_code == 200:
                proxy_data = res_check.json()
                debug_print(f"Proxy enabled: {proxy_data.get('enabled')}")
                debug_print(f"Proxy toxics: {json.dumps(proxy_data.get('toxics', []), indent=2)}")
            else:
                debug_print(f"Không lấy được proxy: {res_check.status_code}")
        except Exception as e:
            debug_print(f"Lỗi kiểm tra proxy sau khi thêm: {e}")

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        debug_print(f"Exception: {e}")
        traceback.print_exc()


def add_limit_data():
    """Thêm limit_data toxic - Packet Loss (cắt response)"""
    print("\n" + "=" * 60)
    print("THÊM LIMIT DATA (Packet Loss)")
    print("=" * 60)
    print("📌 Limit Data: Cắt/giới hạn dữ liệu trả về")
    print("   → Response bị truncated (mất dữ liệu cuối)")
    print("   → Dùng để test xử lý response bị cắt")

    # Lấy bytes từ user
    bytes_val = get_input("Nhập số bytes giới hạn", 100)

    # Dùng timestamp để tránh trùng tên toxic
    toxic_name = f"limit_data_{int(time.time())}"

    toxic = {
        "name": toxic_name,
        "type": "limit_data",
        "stream": "downstream",
        "attributes": {
            "bytes": bytes_val
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm limit_data thành công!")
            print(f"   Giới hạn: {bytes_val} bytes")
            print(f"   Stream: downstream (cắt response từ server)")
            print(f"   → Response sẽ bị cắt sau {bytes_val} bytes")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_close_stream():
    """Thêm close_stream toxic - Hard Failure (server chết)"""
    print("\n" + "=" * 60)
    print("THÊM CLOSE STREAM (Hard Failure)")
    print("=" * 60)
    print("📌 Close Stream: Đóng connection ngay lập tức")
    print("   → Simulate server crash/died")
    print("   → Dùng để test kịch bản:")
    print("      - Bank B chết giữa chừng (partial commit)")
    print("      - Network failure hoàn toàn")
    print("⚠️  CẢNH BÁO: Đây là hard failure - KHÔNG recovery!")

    # Dùng timestamp để tránh trùng tên toxic
    toxic_name = f"close_stream_{int(time.time())}"

    toxic = {
        "name": toxic_name,
        "type": "close_stream",
        "stream": "downstream",
        "attributes": {}
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm close_stream thành công!")
            print(f"   → Server/connection sẽ bị đóng NGAY LẬP TỨC")
            print(f"   → Request nào gọi sẽ bị lỗi Connection Closed")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_bandwidth():
    """Thêm bandwidth toxic - Simulate slow network"""
    print("\n" + "=" * 60)
    print("THÊM BANDWIDTH (Slow Network)")
    print("=" * 60)
    print("📌 Bandwidth: Giới hạn tốc độ mạng")
    print("   → Simulate mạng chậm (không phải delay giả)")
    print("   → Rate = bytes/giây")

    # Lấy rate từ user
    rate = get_input("Nhập bandwidth (bytes/giây)", 1024)

    toxic = {
        "name": f"bandwidth_{int(time.time())}",
        "type": "bandwidth",
        "stream": "downstream",
        "attributes": {
            "rate": rate
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm bandwidth thành công!")
            print(f"   Rate: {rate} bytes/giây")
            rate_kb = rate / 1024
            print(f"   ≈ {rate_kb:.1f} KB/giây")
            print(f"   → Mạng sẽ bị chậm đi")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_slicer():
    """Thêm slicer toxic - Random packet loss (realistic hơn limit_data)"""
    print("\n" + "=" * 60)
    print("THÊM SLICER (Random Packet Loss)")
    print("=" * 60)
    print("📌 Slicer: Cắt response ngẫu nhiên")
    print("   → Realistic hơn limit_data (cắt cố định)")
    print("   → Simulate network instability")

    # Lấy size từ user
    size = get_input("Nhập average size per slice (bytes)", 100)

    toxic = {
        "name": f"slicer_{int(time.time())}",
        "type": "slicer",
        "stream": "downstream",
        "attributes": {
            "size": size
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("✅ Thêm slicer thành công!")
            print(f"   Average size: {size} bytes/slice")
            print(f"   → Response sẽ bị cắt ngẫu nhiên")
        else:
            print(f"❌ Lỗi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def add_both_latency_and_timeout():
    """Thêm cả latency và timeout với giải thích đúng"""
    print("\n" + "=" * 60)
    print("THÊM LATENCY VÀ TIMEOUT CÙNG LÚC")
    print("=" * 60)

    # Lấy giá trị từ user
    latency = get_input("Nhập latency (ms)", DEFAULT_LATENCY)
    timeout = get_input("Nhập timeout (ms)", DEFAULT_TIMEOUT)

    print("\n" + "-" * 60)
    print("📊 CẤU HÌNH:")
    print("-" * 60)
    print(f"   Latency: {latency}ms (downstream)")
    print(f"   Timeout: {timeout}ms (upstream)")

    # Phân tích - QUAN TRỌNG: timeout upstream KHÔNG phụ thuộc latency!
    backend_time = 2000  # Ước tính backend xử lý
    total_time = backend_time + latency

    print(f"\n📊 PHÂN TÍCH:")
    print(f"   Backend xử lý: ~{backend_time}ms")
    print(f"   + Latency: {latency}ms (downstream - KHÔNG ảnh hưởng timeout)")
    print(f"   = Tổng response: ~{total_time}ms")
    print(f"   Timeout: {timeout}ms (upstream - chỉ chờ backend bắt đầu phản hồi)")

    print(f"\n🔥 QUAN TRỌNG:")
    print(f"   Timeout upstream = chờ backend BẮT ĐẦU phản hồi")
    print(f"   → KHÔNG phụ thuộc latency (latency chỉ ảnh hưởng downstream)")
    print()

    if timeout < backend_time:
        print(f"❌ CHẮC CHẮN TIMEOUT:")
        print(f"   Timeout ({timeout}ms) < Backend time ({backend_time}ms)")
        print(f"   → Backend chưa kịp bắt đầu phản hồi đã bị timeout!")
    elif timeout > backend_time:
        print(f"✅ CHẮC CHẮN KHÔNG TIMEOUT:")
        print(f"   Timeout ({timeout}ms) > Backend time ({backend_time}ms)")
        print(f"   → Backend đủ thời gian bắt đầu phản hồi")
        print(f"   → Request sẽ thành công (chậm hơn do latency)")

    print("-" * 60)

    # DEBUG: Kiểm tra proxy trước khi thêm toxics
    debug_print("=" * 50)
    debug_print("DEBUG: Kiểm tra proxy TRƯỚC KHI thêm toxics...")
    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        debug_print(f"GET proxy status: {res.status_code}")
        if res.status_code == 200:
            proxy_data = res.json()
            debug_print(f"Proxy enabled: {proxy_data.get('enabled')}")
            debug_print(f"Proxy listen: {proxy_data.get('listen')}")
            debug_print(f"Proxy upstream: {proxy_data.get('upstream')}")
            debug_print(f"Proxy toxics: {proxy_data.get('toxics', [])}")
    except Exception as e:
        debug_print(f"Lỗi kiểm tra proxy: {e}")

    # Dùng timestamp để tránh trùng tên toxic
    ts = int(time.time())

    # Thêm latency
    toxic_latency = {
        "name": f"latency_{ts}",
        "type": "latency",
        "stream": "downstream",
        "attributes": {
            "latency": latency
        }
    }

    # Thêm timeout - QUAN TRỌNG: upstream!
    toxic_timeout = {
        "name": f"timeout_{ts}",
        "type": "timeout",
        "stream": "upstream",  # 🔥 QUAN TRỌNG
        "attributes": {
            "timeout": timeout
        }
    }

    debug_print("Gửi request thêm latency...")
    try:
        res1 = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic_latency,
            timeout=API_TIMEOUT
        )
        debug_print(f"Latency response: {res1.status_code} - {res1.text}")
        if res1.status_code in [200, 201]:
            print(f"✅ Thêm latency: {latency}ms (downstream)")
        else:
            print(f"❌ Lỗi thêm latency: {res1.status_code} - {res1.text}")

    except Exception as e:
        debug_print(f"Exception khi thêm latency: {e}")
        traceback.print_exc()

    debug_print("Gửi request thêm timeout...")
    try:
        res2 = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic_timeout,
            timeout=API_TIMEOUT
        )
        debug_print(f"Timeout response: {res2.status_code} - {res2.text}")
        if res2.status_code in [200, 201]:
            print(f"✅ Thêm timeout: {timeout}ms (upstream)")
        else:
            print(f"❌ Lỗi thêm timeout: {res2.status_code} - {res2.text}")

    except Exception as e:
        debug_print(f"Exception khi thêm timeout: {e}")
        traceback.print_exc()

    # DEBUG: Kiểm tra proxy SAU KHI thêm toxics
    debug_print("=" * 50)
    debug_print("DEBUG: Kiểm tra proxy SAU KHI thêm toxics...")
    try:
        res_check = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        if res_check.status_code == 200:
            proxy_data = res_check.json()
            debug_print(f"Proxy enabled: {proxy_data.get('enabled')}")
            debug_print(f"Proxy toxics: {json.dumps(proxy_data.get('toxics', []), indent=2)}")
        else:
            debug_print(f"Không lấy được proxy: {res_check.status_code}")
    except Exception as e:
        debug_print(f"Lỗi kiểm tra proxy sau khi thêm: {e}")

    # DEBUG: Test ngay sau khi thêm toxics
    debug_print("=" * 50)
    debug_print("DEBUG: Test request ngay sau khi thêm toxics...")
    try:
        debug_print("Gọi health check...")
        start_test = time.time()
        res_test = requests.get(f"{API_VIA_PROXY}/", timeout=5)
        elapsed = time.time() - start_test
        debug_print(f"Health check response: {res_test.status_code} - Time: {elapsed:.3f}s")
    except Exception as e:
        debug_print(f"Lỗi test: {e}")
        debug_print(traceback.format_exc())


def clear_toxics():
    """Xóa tất cả toxic"""
    print("\n" + "=" * 60)
    print("XÓA TẤT CẢ TOXICS")
    print("=" * 60)

    # DEBUG: Kiểm tra proxy trước khi xóa
    debug_print("=" * 50)
    debug_print("DEBUG: Kiểm tra proxy TRƯỚC KHI xóa toxics...")
    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)

        if res.status_code != 200:
            print(f"❌ Không lấy được proxy: {res.status_code}")
            return

        data = res.json()
        toxics = data.get("toxics", [])

        debug_print(f"Proxy enabled: {data.get('enabled')}")
        debug_print(f"Proxy listen: {data.get('listen')}")
        debug_print(f"Proxy upstream: {data.get('upstream')}")
        debug_print(f"Số lượng toxics: {len(toxics)}")

        if not toxics:
            print("⚪ Không có toxic nào để xóa")
            return

        for toxic in toxics:
            name = toxic.get("name")
            debug_print(f"Đang xóa toxic: {name} (type={toxic.get('type')}, stream={toxic.get('stream')})")

            del_res = requests.delete(
                f"http://localhost:8474/proxies/vbank_api/toxics/{name}",
                timeout=API_TIMEOUT
            )

            debug_print(f"Xóa {name}: {del_res.status_code} - {del_res.text}")

            if del_res.status_code in [200, 204]:
                print(f"✅ Đã xóa toxic: {name}")
            else:
                print(f"❌ Lỗi xóa {name}: {del_res.status_code}")

        print("\n🎉 Đã xóa toàn bộ toxics!")

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        debug_print(f"Exception: {e}")
        traceback.print_exc()

    # DEBUG: Kiểm tra proxy SAU KHI xóa
    debug_print("=" * 50)
    debug_print("DEBUG: Kiểm tra proxy SAU KHI xóa toxics...")
    try:
        res_check = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        if res_check.status_code == 200:
            proxy_data = res_check.json()
            debug_print(f"Proxy enabled: {proxy_data.get('enabled')}")
            debug_print(f"Proxy toxics: {proxy_data.get('toxics', [])}")
        else:
            debug_print(f"Không lấy được proxy: {res_check.status_code}")
    except Exception as e:
        debug_print(f"Lỗi kiểm tra proxy: {e}")


def check_services():
    """Kiểm tra các service đang chạy"""
    print("=" * 60)
    print("KIỂM TRA SERVICES")
    print("=" * 60)

    print("\n[1] Kiểm tra backend (direct)...")
    try:
        res = requests.get(f"{API_DIRECT}/accounts", timeout=API_TIMEOUT)
        print(f"    ✅ Backend OK - Status: {res.status_code}")
    except Exception as e:
        print(f"    ❌ Backend ERROR: {e}")
        print("    → Cần khởi động backend: cd backend && python app.py")

    print("\n[2] Kiểm tra Toxiproxy...")
    try:
        res = requests.get("http://localhost:8474/proxies", timeout=API_TIMEOUT)
        proxies = res.json()
        print(f"    ✅ Toxiproxy OK - Status: {res.status_code}")

        if 'proxies' in proxies:
            for p in proxies['proxies']:
                print(f"\n    📋 Proxy: {p['name']}")
                print(f"       Listen: {p['listen']}")
                print(f"       Upstream: {p['upstream']}")
                print(f"       Enabled: {p['enabled']}")

                # DEBUG: Hiển thị chi tiết toxics
                toxics = p.get('toxics', [])
                if toxics:
                    print(f"       Toxics: {len(toxics)}")
                    for t in toxics:
                        attrs = t.get('attributes', {})
                        if 'latency' in attrs:
                            print(f"         - {t['name']}: latency={attrs['latency']}ms, stream={t['stream']}")
                        elif 'timeout' in attrs:
                            print(f"         - {t['name']}: timeout={attrs['timeout']}ms, stream={t['stream']}")
                        else:
                            print(f"         - {t['name']}: {t['type']}, stream={t['stream']}")

        if 'proxies' in proxies and len(proxies['proxies']) == 0:
            print("    ⚠️  Chưa có proxy! Cần tạo proxy")
    except Exception as e:
        print(f"    ❌ Toxiproxy ERROR: {e}")
        print("    → Cần khởi động Toxiproxy:")
        print("    → docker run -d -p 8474:8474 -p 8666:8666 --name toxiproxy ghcr.io/shopify/toxiproxy")

    print("\n[3] Kiểm tra proxy (localhost:8666)...")
    start = time.time()

    # Lấy thông tin toxics từ proxy
    latency_ms = None
    timeout_ms = None

    try:
        proxy_res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        if proxy_res.status_code == 200:
            proxy_data = proxy_res.json()
            toxics = proxy_data.get('toxics', [])

            for t in toxics:
                attrs = t.get('attributes', {})
                if t.get('type') == 'latency':
                    latency_ms = attrs.get('latency')
                elif t.get('type') == 'timeout':
                    timeout_ms = attrs.get('timeout')
    except:
        pass  # Bỏ qua nếu không lấy được thông tin proxy

    # Test kết nối
    try:
        debug_print("Testing proxy connection...")
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        debug_print(f"Proxy response: {res.status_code} in {elapsed:.3f}s")

        print(f"    ✅ Proxy OK - Status: {res.status_code}")

        # Hiển thị thông tin latency và timeout
        latency_str = f"{latency_ms}ms" if latency_ms is not None else "Chưa cấu hình"
        timeout_str = f"{timeout_ms}ms" if timeout_ms is not None else "Chưa cấu hình"

        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"    ❌ CLIENT TIMEOUT")
        print(f"    Time: {elapsed:.2f}s")
        print(f"    → Client chờ vượt quá {REQUEST_TIMEOUT}s")

        # Hiển thị thông tin toxics
        latency_str = f"{latency_ms}ms" if latency_ms is not None else "Chưa cấu hình"
        timeout_str = f"{timeout_ms}ms" if timeout_ms is not None else "Chưa cấu hình"
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start
        print(f"    💣 CONNECTION CLOSED")
        print(f"    Time: {elapsed:.2f}s")

        if "RemoteDisconnected" in str(e):
            print("    → Proxy đã đóng connection (timeout toxic)")
        elif "Connection refused" in str(e):
            print("    → Proxy hoặc backend chưa chạy")
        else:
            print("    → Lỗi network khác")

        print(f"    → Chi tiết: {e}")

        # Hiển thị thông tin toxics
        latency_str = f"{latency_ms}ms" if latency_ms is not None else "Chưa cấu hình"
        timeout_str = f"{timeout_ms}ms" if timeout_ms is not None else "Chưa cấu hình"
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except Exception as e:
        elapsed = time.time() - start
        print(f"    ❌ UNKNOWN ERROR")
        print(f"    Time: {elapsed:.2f}s")

        # Hiển thị thông tin toxics
        latency_str = f"{latency_ms}ms" if latency_ms is not None else "Chưa cấu hình"
        timeout_str = f"{timeout_ms}ms" if timeout_ms is not None else "Chưa cấu hình"
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")
        print(f"    → {type(e).__name__}: {e}")


def show_proxy_info():
    """Xem thông tin chi tiết của proxy hiện tại"""
    print("\n" + "=" * 60)
    print("THÔNG TIN PROXY HIỆN TẠI")
    print("=" * 60)

    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
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

        toxics = data.get('toxics', [])
        print(f"\n📦 Toxics ({len(toxics)} active):")

        if not toxics:
            print("   ⚪ Không có toxic nào")
        else:
            for toxic in toxics:
                stream = toxic.get('stream', 'N/A')
                stream_emoji = "⬇️" if stream == "downstream" else "⬆️"

                print(f"\n   🔸 {toxic.get('name', 'N/A')} {stream_emoji}")
                print(f"      Type: {toxic.get('type', 'N/A')}")
                print(f"      Stream: {stream}")
                print(f"      Enabled: {toxic.get('enabled', 'N/A')}")

                attrs = toxic.get('attributes', {})
                if 'latency' in attrs:
                    print(f"      Latency: {attrs['latency']}ms")
                if 'timeout' in attrs:
                    print(f"      Timeout: {attrs['timeout']}ms")

        # Phân tích
        latency_ms = 0
        timeout_ms = 0
        for t in toxics:
            attrs = t.get('attributes', {})
            if t.get('type') == 'latency':
                latency_ms = attrs.get('latency', 0)
            elif t.get('type') == 'timeout':
                timeout_ms = attrs.get('timeout', 0)

        if latency_ms > 0 or timeout_ms > 0:
            print(f"\n📊 PHÂN TÍCH:")
            backend_time = 2000
            total_time = backend_time + latency_ms

            if timeout_ms > 0:
                if timeout_ms < backend_time:
                    print(f"   ⚠️  Timeout ({timeout_ms}ms) < Backend ({backend_time}ms)")
                    print(f"   → Sẽ bị TIMEOUT ngay!")
                elif timeout_ms < total_time:
                    print(f"   ⚠️  Timeout ({timeout_ms}ms) gần sát tổng ({total_time}ms)")
                    print(f"   → Dễ bị TIMEOUT!")
                else:
                    print(f"   ✅ Timeout ({timeout_ms}ms) > Tổng ({total_time}ms)")
                    print(f"   → Request thành công (chậm)")

    except Exception as e:
        print(f"❌ Lỗi: {e}")


def get_toxic_info():
    """Lấy thông tin latency và timeout từ proxy"""
    latency_ms = None
    timeout_ms = None

    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            toxics = data.get('toxics', [])

            for t in toxics:
                attrs = t.get('attributes', {})
                if t.get('type') == 'latency':
                    latency_ms = attrs.get('latency')
                elif t.get('type') == 'timeout':
                    timeout_ms = attrs.get('timeout')
    except:
        pass

    return latency_ms, timeout_ms


def format_toxic_info(latency_ms, timeout_ms):
    """Format thông tin latency/timeout để hiển thị"""
    latency_str = f"{latency_ms}ms" if latency_ms is not None else "Chưa cấu hình"
    timeout_str = f"{timeout_ms}ms" if timeout_ms is not None else "Chưa cấu hình"
    return latency_str, timeout_str


def test_health_check():
    """Test 1: Health check"""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)

    # Lấy thông tin toxics
    latency_ms, timeout_ms = get_toxic_info()
    start = time.time()

    try:
        res = requests.get(f"{API_VIA_PROXY}/health", timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start

        print(f"✅ SUCCESS")
        print(f"Status: {res.status_code}")
        print(f"Time: {elapsed:.2f}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

        data = safe_json_response(res)
if data:
    print_response(data)

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"❌ CLIENT TIMEOUT")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ Client chờ vượt quá {REQUEST_TIMEOUT}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start
        print(f"💣 CONNECTION CLOSED")
        print(f"Time: {elapsed:.2f}s")

        # Phân tích nguyên nhân
        if "RemoteDisconnected" in str(e):
            print("→ Proxy đã đóng connection (timeout toxic)")
        elif "Connection refused" in str(e):
            print("→ Proxy hoặc backend chưa chạy")
        else:
            print("→ Lỗi network khác")

        print(f"→ Chi tiết: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ UNKNOWN ERROR")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ {type(e).__name__}: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")


def test_get_accounts():
    """Test 2: Lấy danh sách tài khoản"""
    print("\n" + "=" * 60)
    print("TEST 2: Get Accounts")
    print("=" * 60)

    # Lấy thông tin toxics
    latency_ms, timeout_ms = get_toxic_info()
    start = time.time()

    try:
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start

        print(f"✅ SUCCESS")
        print(f"Status: {res.status_code}")
        print(f"Time: {elapsed:.2f}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

        data = safe_json_response(res)
if data:
    print_response(data)

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"❌ CLIENT TIMEOUT")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ Client chờ vượt quá {REQUEST_TIMEOUT}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start
        print(f"💣 CONNECTION CLOSED")
        print(f"Time: {elapsed:.2f}s")

        if "RemoteDisconnected" in str(e):
            print("→ Proxy đã đóng connection (timeout toxic)")
        elif "Connection refused" in str(e):
            print("→ Proxy hoặc backend chưa chạy")
        else:
            print("→ Lỗi network khác")

        print(f"→ Chi tiết: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ UNKNOWN ERROR")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ {type(e).__name__}: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")


def test_login():
    """Test 3: Đăng nhập"""
    print("\n" + "=" * 60)
    print("TEST 3: Login")
    print("=" * 60)

    data = {
        "phone": "0901234567",
        "password": "123456"
    }

    # Lấy thông tin toxics
    latency_ms, timeout_ms = get_toxic_info()
    start = time.time()

    try:
        res = requests.post(f"{API_VIA_PROXY}/login", json=data, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start

        print(f"✅ SUCCESS")
        print(f"Status: {res.status_code}")
        print(f"Time: {elapsed:.2f}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

        data = safe_json_response(res)
if data:
    print_response(data)

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"❌ CLIENT TIMEOUT")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ Client chờ vượt quá {REQUEST_TIMEOUT}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start
        print(f"💣 CONNECTION CLOSED")
        print(f"Time: {elapsed:.2f}s")

        if "RemoteDisconnected" in str(e):
            print("→ Proxy đã đóng connection (timeout toxic)")
        elif "Connection refused" in str(e):
            print("→ Proxy hoặc backend chưa chạy")
        else:
            print("→ Lỗi network khác")

        print(f"→ Chi tiết: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ UNKNOWN ERROR")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ {type(e).__name__}: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")


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

    # Lấy thông tin toxics
    latency_ms, timeout_ms = get_toxic_info()
    debug_print("Bắt đầu transfer...")
    start = time.time()

    try:
        res = requests.post(f"{API_VIA_PROXY}/transfer", json=data, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        debug_print(f"Transfer completed: {res.status_code} in {elapsed:.3f}s")

        print(f"✅ SUCCESS")
        print(f"Status: {res.status_code}")
        print(f"Time: {elapsed:.2f}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

        data = safe_json_response(res)
if data:
    print_response(data)

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"❌ CLIENT TIMEOUT")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ Client chờ vượt quá {REQUEST_TIMEOUT}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start
        print(f"💣 CONNECTION CLOSED")
        print(f"Time: {elapsed:.2f}s")

        if "RemoteDisconnected" in str(e):
            print("→ Proxy đã đóng connection (timeout toxic)")
        elif "Connection refused" in str(e):
            print("→ Proxy hoặc backend chưa chạy")
        else:
            print("→ Lỗi network khác")

        print(f"→ Chi tiết: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ UNKNOWN ERROR")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ {type(e).__name__}: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")


def test_transfer_with_current_toxics():
    """Test 5: Transfer với toxics hiện tại"""
    print("\n" + "=" * 60)
    print("TEST 5: Transfer với Toxics hiện tại")
    print("=" * 60)

    latency_ms = 0
    timeout_ms = 0

    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
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
                    print(f"   Latency: {latency_ms}ms (downstream)")
                if timeout_ms > 0:
                    print(f"   Timeout: {timeout_ms}ms (upstream)")
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

    start = time.time()
    print(f"\n🚀 Bắt đầu transfer lúc: {time.strftime('%H:%M:%S')}")

    try:
        res = requests.post(f"{API_VIA_PROXY}/transfer", json=data, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        print(f"🏁 Hoàn thành lúc: {time.strftime('%H:%M:%S')}")

        print(f"✅ SUCCESS")
        print(f"Status: {res.status_code}")
        print(f"Time: {elapsed:.2f}s")

        if elapsed > REQUEST_TIMEOUT:
            print(f"\n❌ KẾT QUẢ: Client TIMEOUT!")
        elif timeout_ms > 0 and elapsed > (timeout_ms / 1000):
            print(f"\n❌ KẾT QUẢ: Proxy TIMEOUT!")
        else:
            print(f"\n✅ KẾT QUẢ: Request thành công!")

        data = safe_json_response(res)
if data:
    print_response(data)

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"🏁 Hoàn thành lúc: {time.strftime('%H:%M:%S')}")
        print(f"❌ CLIENT TIMEOUT")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ Client chờ vượt quá {REQUEST_TIMEOUT}s")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start
        print(f"🏁 Hoàn thành lúc: {time.strftime('%H:%M:%S')}")
        print(f"💣 CONNECTION CLOSED")
        print(f"Time: {elapsed:.2f}s")

        if "RemoteDisconnected" in str(e):
            print("→ Proxy đã đóng connection (timeout toxic)")
        elif "Connection refused" in str(e):
            print("→ Proxy hoặc backend chưa chạy")
        else:
            print("→ Lỗi network khác")

        print(f"→ Chi tiết: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")

    except Exception as e:
        elapsed = time.time() - start
        print(f"🏁 Hoàn thành lúc: {time.strftime('%H:%M:%S')}")
        print(f"❌ UNKNOWN ERROR")
        print(f"Time: {elapsed:.2f}s")
        print(f"→ {type(e).__name__}: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"       Latency: {latency_str}")
        print(f"       Timeout: {timeout_str}")


def test_retry_logic():
    """Test Retry Logic - Tự động retry khi timeout"""
    print("\n" + "=" * 60)
    print("TEST RETRY LOGIC")
    print("=" * 60)
    print("📌 Test retry khi timeout/connection error")
    print("   → Simulate: timeout → retry → success")

    # Cấu hình retry
    max_retries = get_input("Số lần retry tối đa", 3)
    retry_delay = get_input("Delay giữa các lần retry (ms)", 1000)

    # Lấy thông tin toxics
    latency_ms, timeout_ms = get_toxic_info()

    print(f"\n📊 Cấu hình:")
    print(f"   Max retries: {max_retries}")
    print(f"   Retry delay: {retry_delay}ms")

    latency_str = f"{latency_ms}ms" if latency_ms else "Không"
    timeout_str = f"{timeout_ms}ms" if timeout_ms else "Không"
    print(f"   Latency toxic: {latency_str}")
    print(f"   Timeout toxic: {timeout_str}")

    print("\n" + "-" * 60)
    print("🔄 Bắt đầu test với retry...")
    print("-" * 60)

    data = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 10000,
        "description": "Test retry"
    }

    start = time.time()
    last_error = None

    for attempt in range(1, max_retries + 1):
        print(f"\n🔄 Attempt {attempt}/{max_retries}")

        try:
            res = requests.post(
                f"{API_VIA_PROXY}/transfer",
                json=data,
                timeout=REQUEST_TIMEOUT
            )
            elapsed = time.time() - start
            print(f"   ✅ SUCCESS sau {elapsed:.2f}s")
            print(f"   Status: {res.status_code}")
            data = safe_json_response(res)
if data:
    print_response(data)

            # Hiển thị thông tin toxics
            latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
            print(f"   Latency: {latency_str}")
            print(f"   Timeout: {timeout_str}")

            return  # Thành công, thoát

        except requests.exceptions.Timeout as e:
            elapsed = time.time() - start
            last_error = "TIMEOUT"
            print(f"   ❌ TIMEOUT sau {elapsed:.2f}s (lần {attempt})")

            # Hiển thị thông tin toxics
            latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
            print(f"   Latency: {latency_str}")
            print(f"   Timeout: {timeout_str}")

        except requests.exceptions.ConnectionError as e:
            elapsed = time.time() - start
            last_error = "CONNECTION ERROR"

            if "RemoteDisconnected" in str(e):
                print(f"   💣 CONNECTION CLOSED sau {elapsed:.2f}s (lần {attempt})")
                print(f"   → Proxy đã đóng connection")
            else:
                print(f"   💣 CONNECTION ERROR sau {elapsed:.2f}s (lần {attempt})")

            # Hiển thị thông tin toxics
            latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
            print(f"   Latency: {latency_str}")
            print(f"   Timeout: {timeout_str}")

        except Exception as e:
            elapsed = time.time() - start
            last_error = f"ERROR: {type(e).__name__}"
            print(f"   ❌ ERROR sau {elapsed:.2f}s: {e}")
            break

        # Retry nếu còn lần
        if attempt < max_retries:
            print(f"   ⏳ Chờ {retry_delay}ms trước khi retry...")
            time.sleep(retry_delay / 1000)

    # Tất cả retries thất bại
    print("\n" + "-" * 60)
    print(f"❌ THẤT BẠI sau {max_retries} attempts!")
    print(f"   Last error: {last_error}")
    print("-" * 60)


def test_fallback_data():
    """Test Fallback Data - Dùng dữ liệu dự phòng khi API fail"""
    print("\n" + "=" * 60)
    print("TEST FALLBACK DATA")
    print("=" * 60)
    print("📌 Test dùng dữ liệu dự phòng khi API fail")
    print("   → Simulate: API fail → dùng cache/local data")

    # Lấy thông tin toxics
    latency_ms, timeout_ms = get_toxic_info()

    print("\n📊 Test 1: Gọi API bình thường...")
    print("-" * 60)

    try:
        start = time.time()
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start

        print(f"✅ API Response:")
        print(f"   Status: {res.status_code}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Data: {res.text[:200]}...")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"   Latency: {latency_str}")
        print(f"   Timeout: {timeout_str}")

    except Exception as e:
        print(f"❌ API Error: {e}")

        # Hiển thị thông tin toxics
        latency_str, timeout_str = format_toxic_info(latency_ms, timeout_ms)
        print(f"   Latency: {latency_str}")
        print(f"   Timeout: {timeout_str}")

    print("\n📊 Test 2: Fallback với dữ liệu mẫu (khi API fail)...")
    print("-" * 60)

    # Simulate fallback data
    fallback_data = [
        {"account_number": "102938475612", "name": "Nguyen Van A", "balance": 100000},
        {"account_number": "203847569801", "name": "Le Thi B", "balance": 50000},
    ]

    print("✅ Fallback Data (mock):")
    print(json.dumps(fallback_data, indent=2, ensure_ascii=False))
    print("\n→ Khi API fail, hệ thống có thể:")
    print("   1. Dùng dữ liệu cache trước đó")
    print("   2. Dùng dữ liệu mẫu (mock)")
    print("   3. Hiển thị thông báo lỗi và yêu cầu thử lại")


# ============================================================
# AUTO SCENARIO TESTS
# ============================================================

def scenario_timeout_then_retry():
    """Scenario: Timeout → Retry → Success"""
    print("\n" + "=" * 60)
    print("🔄 SCENARIO: Timeout → Retry → Success")
    print("=" * 60)

    # Lấy cấu hình
    timeout_val = get_input("Nhập timeout (ms)", DEFAULT_TIMEOUT)
    max_retries = get_input("Số lần retry", 3)

    print("\n📋 Kịch bản:")
    print(f"   1. Thêm timeout toxic ({timeout_val}ms)")
    print(f"   2. Gọi API (sẽ bị timeout)")
    print(f"   3. Retry {max_retries} lần")
    print(f"   4. Xóa toxic")

    input("\n🚀 Nhấn Enter để bắt đầu...")

    # Bước 1: Thêm timeout
    print("\n📍 Bước 1: Thêm timeout toxic...")
    toxic = {
        "name": f"timeout_{int(time.time())}",
        "type": "timeout",
        "stream": "upstream",
        "attributes": {
            "timeout": timeout_val
        }
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print(f"   ✅ Đã thêm timeout: {timeout_val}ms")
        else:
            print(f"   ❌ Lỗi thêm toxic: {res.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")
        return

    # Bước 2: Gọi API với retry
    print(f"\n📍 Bước 2: Gọi API với {max_retries} retries...")

    data = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 10000,
        "description": "Test scenario"
    }

    success = False
    for attempt in range(1, max_retries + 1):
        print(f"\n   🔄 Attempt {attempt}/{max_retries}")

        try:
            res = requests.post(
                f"{API_VIA_PROXY}/transfer",
                json=data,
                timeout=REQUEST_TIMEOUT
            )
            print(f"   ✅ SUCCESS! Status: {res.status_code}")
            success = True
            break
        except Exception as e:
            print(f"   ❌ Failed: {type(e).__name__}")
            if attempt < max_retries:
                print(f"   ⏳ Waiting 1s before retry...")
                time.sleep(1)

    # Bước 3: Xóa toxic
    print("\n📍 Bước 3: Xóa toxic...")
    try:
        requests.delete(
            f"http://localhost:8474/proxies/vbank_api/toxics/{toxic['name']}",
            timeout=API_TIMEOUT
        )
        print("   ✅ Đã xóa toxic")
    except:
        pass

    # Kết quả
    print("\n" + "=" * 60)
    if success:
        print("✅ SCENARIO PASSED: Retry thành công!")
    else:
        print("❌ SCENARIO FAILED: Retry thất bại!")
    print("=" * 60)


def scenario_partial_commit():
    """Scenario: Partial Commit - Bank B chết giữa chừng"""
    print("\n" + "=" * 60)
    print("🔄 SCENARIO: Partial Commit (Bank B chết)")
    print("=" * 60)

    print("\n📋 Kịch bản 2PC:")
    print("   1. Prepare: Gửi tiền từ A → B")
    print("   2. Bank B bị chết (close_stream toxic)")
    print("   3. Commit thất bại")
    print("   4. Rollback (A không bị trừ tiền)")

    input("\n🚀 Nhấn Enter để bắt đầu...")

    # Bước 1: Kiểm tra số dư trước
    print("\n📍 Bước 1: Kiểm tra số dư trước...")
    try:
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            print(f"   ✅ Accounts: {res.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")

    # Bước 2: Thêm close_stream (Bank B chết)
    print("\n📍 Bước 2: Bank B chết (thêm close_stream)...")

    toxic = {
        "name": f"close_stream_{int(time.time())}",
        "type": "close_stream",
        "stream": "downstream",
        "attributes": {}
    }

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        if res.status_code in [200, 201]:
            print("   ✅ Bank B đã 'chết' (close_stream)")
        else:
            print(f"   ❌ Lỗi: {res.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")
        return

    # Bước 3: Thử transfer (sẽ fail)
    print("\n📍 Bước 3: Thử transfer (sẽ fail)...")

    data = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 10000,
        "description": "Test partial commit"
    }

    try:
        res = requests.post(
            f"{API_VIA_PROXY}/transfer",
            json=data,
            timeout=REQUEST_TIMEOUT
        )
        print(f"   ❌ Response: {res.status_code} - {res.text[:100]}")
    except Exception as e:
        print(f"   ✅ Đúng kỳ vọng - Connection error: {type(e).__name__}")

    # Bước 4: Xóa toxic và kiểm tra
    print("\n📍 Bước 4: Xóa toxic và kiểm tra...")
    try:
        requests.delete(
            f"http://localhost:8474/proxies/vbank_api/toxics/{toxic['name']}",
            timeout=API_TIMEOUT
        )
        print("   ✅ Đã xóa toxic (Bank B sống lại)")
    except:
        pass

    # Kiểm tra số dư sau
    try:
        res = requests.get(f"{API_VIA_PROXY}/accounts", timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            print(f"   ✅ Accounts: {res.text[:200]}...")
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")

    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ:")
    print("   → A không bị trừ tiền (rollback)")
    print("   → B không nhận được tiền")
    print("   → Giao dịch bị hủy (partial commit failure)")
    print("=" * 60)


def configure_defaults():
    """Cấu hình giá trị mặc định"""
    global DEFAULT_LATENCY, DEFAULT_TIMEOUT, REQUEST_TIMEOUT

    print("\n" + "=" * 60)
    print("CẤU HÌNH GIÁ TRỊ MẶC ĐỊNH")
    print("=" * 60)

    print(f"\n📊 Giá trị hiện tại:")
    print(f"   DEFAULT_LATENCY:  {DEFAULT_LATENCY}ms")
    print(f"   DEFAULT_TIMEOUT:  {DEFAULT_TIMEOUT}ms")
    print(f"   REQUEST_TIMEOUT:  {REQUEST_TIMEOUT}s (client)")

    print("\n" + "-" * 60)
    print("Nhập giá trị mới (Enter để giữ nguyên):")
    print("-" * 60)

    new_latency = get_input("DEFAULT_LATENCY (ms)", DEFAULT_LATENCY)
    if new_latency != DEFAULT_LATENCY:
        DEFAULT_LATENCY = new_latency

    new_timeout = get_input("DEFAULT_TIMEOUT (ms)", DEFAULT_TIMEOUT)
    if new_timeout != DEFAULT_TIMEOUT:
        DEFAULT_TIMEOUT = new_timeout

    new_request_timeout = get_input("REQUEST_TIMEOUT (seconds)", REQUEST_TIMEOUT)
    if new_request_timeout != REQUEST_TIMEOUT:
        REQUEST_TIMEOUT = new_request_timeout

    print("\n" + "-" * 60)
    print("📊 Giá trị sau cập nhật:")
    print(f"   DEFAULT_LATENCY:  {DEFAULT_LATENCY}ms")
    print(f"   DEFAULT_TIMEOUT:  {DEFAULT_TIMEOUT}ms")
    print(f"   REQUEST_TIMEOUT:  {REQUEST_TIMEOUT}s")

    # Kiểm tra
    print("\n📋 Kiểm tra:")
    if DEFAULT_TIMEOUT < 3000:
        print(f"   ⚠️  Timeout ({DEFAULT_TIMEOUT}ms) có thể quá nhỏ!")
    elif DEFAULT_TIMEOUT < DEFAULT_LATENCY + 2000:
        print(f"   ⚠️  Timeout gần sát tổng thời gian!")
    else:
        print(f"   ✅ Cấu hình hợp lệ")

    print("-" * 60)


def deep_debug_timeout():
    """
    DEBUG CHUYÊN SÂU: Theo dõi từng bước khi thêm timeout
    """
    print("\n" + "=" * 60)
    print("🔍 DEBUG CHUYÊN SÂU: Timeout Toxic")
    print("=" * 60)

    timeout_ms = get_input("Nhập timeout (ms)", DEFAULT_TIMEOUT)

    # Bước 1: Kiểm tra trạng thái ban đầu
    print("\n📍 BƯỚC 1: Kiểm tra trạng thái ban đầu")
    print("-" * 50)
    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            print(f"  ✅ Proxy tồn tại")
            print(f"     - Enabled: {data.get('enabled')}")
            print(f"     - Listen: {data.get('listen')}")
            print(f"     - Upstream: {data.get('upstream')}")
            toxics = data.get('toxics', [])
            print(f"     - Toxics: {len(toxics)}")
            for t in toxics:
                print(f"       * {t.get('name')}: {t.get('type')} ({t.get('stream')})")
        else:
            print(f"  ❌ Proxy không tồn tại: {res.status_code}")
            return
    except Exception as e:
        print(f"  ❌ Lỗi: {e}")
        return

    # Bước 2: Test request trước khi thêm toxic
    print("\n📍 BƯỚC 2: Test request TRƯỚC KHI thêm toxic")
    print("-" * 50)
    try:
        start = time.time()
        res = requests.get(f"{API_VIA_PROXY}/", timeout=5)
        elapsed = time.time() - start
        print(f"  ✅ Request OK: {res.status_code} trong {elapsed:.3f}s")
    except Exception as e:
        print(f"  ❌ Request thất bại: {e}")

    # Bước 3: Thêm timeout toxic
    print(f"\n📍 BƯỚC 3: Thêm timeout toxic ({timeout_ms}ms)")
    print("-" * 50)
    toxic = {
        "name": "timeout",
        "type": "timeout",
        "stream": "upstream",
        "attributes": {
            "timeout": timeout_ms
        }
    }
    print(f"  Gửi: {json.dumps(toxic)}")

    try:
        res = requests.post(
            "http://localhost:8474/proxies/vbank_api/toxics",
            json=toxic,
            timeout=API_TIMEOUT
        )
        print(f"  Response: {res.status_code}")
        print(f"  Body: {res.text[:500]}")

        if res.status_code not in [200, 201]:
            print(f"\n  ⚠️  CẢNH BÁO: Thêm toxic THẤT BẠI!")
            return
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        traceback.print_exc()
        return

    # Bước 4: Kiểm tra proxy NGAY SAU KHI thêm toxic
    print("\n📍 BƯỚC 4: Kiểm tra proxy NGAY SAU KHI thêm toxic")
    print("-" * 50)
    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            print(f"  ✅ Proxy OK")
            print(f"     - Enabled: {data.get('enabled')}")
            toxics = data.get('toxics', [])
            print(f"     - Toxics: {len(toxics)}")
            for t in toxics:
                print(f"       * {t.get('name')}: type={t.get('type')}, stream={t.get('stream')}, enabled={t.get('enabled')}")
                if t.get('attributes'):
                    print(f"         attrs: {t.get('attributes')}")
        else:
            print(f"  ❌ Lỗi lấy proxy: {res.status_code}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    # Bước 5: Test request NGAY SAU KHI thêm toxic
    print("\n📍 BƯỚC 5: Test request NGAY SAU KHI thêm toxic")
    print("-" * 50)
    print(f"  Đợi 1 giây để toxic ổn định...")
    time.sleep(1)

    start = time.time()
    print(f"  Gọi {API_VIA_PROXY}/ với timeout client = 10s...")

    try:
        res = requests.get(f"{API_VIA_PROXY}/", timeout=10)
        elapsed = time.time() - start
        print(f"  ✅ Response: {res.status_code} trong {elapsed:.3f}s")
        print(f"     Body: {res.text[:200]}")

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"  ❌ CLIENT TIMEOUT")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  → Client chờ vượt quá 10s")

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start
        print(f"  💣 CONNECTION CLOSED")
        print(f"  Time: {elapsed:.2f}s")

        if "RemoteDisconnected" in str(e):
            print("  → Proxy đã đóng connection (timeout toxic)")
        elif "Connection refused" in str(e):
            print("  → Proxy hoặc backend chưa chạy")
        else:
            print("  → Lỗi network khác")

        print(f"  → Chi tiết: {e}")

    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ UNKNOWN ERROR")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  → {type(e).__name__}: {e}")

    # Bước 6: Kiểm tra proxy lần cuối
    print("\n📍 BƯỚC 6: Kiểm tra proxy lần cuối")
    print("-" * 50)
    try:
        res = requests.get("http://localhost:8474/proxies/vbank_api", timeout=API_TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            toxics = data.get('toxics', [])
            print(f"  ✅ Proxy still running")
            print(f"     - Enabled: {data.get('enabled')}")
            print(f"     - Toxics: {len(toxics)}")
        else:
            print(f"  ❌ Proxy có thể đã bị kill: {res.status_code}")
    except Exception as e:
        print(f"  ❌ Proxy không thể truy cập: {e}")

    print("\n" + "=" * 60)
    print("KẾT THÚC DEBUG")
    print("=" * 60)


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
        print("L. Thêm Limit Data (Packet Loss)")
        print("K. Thêm Close Stream (Server chết)")
        print("B. Thêm Bandwidth (Slow network)")
        print("P. Thêm Slicer (Random packet loss)")
        print("F. Thêm CẢ Latency + Timeout")
        print("S. Xem thông tin Proxy & Toxics")
        print("E. Xóa tất cả Toxics")
        print("---")
        print("R. Test Retry Logic (timeout → retry)")
        print("W. Test Fallback Data (API fail → dùng dự phòng)")
        print("---")
        print("1. Scenario: Timeout → Retry → Success")
        print("2. Scenario: Partial Commit (Bank B chết)")
        print("---")
        print("T. DEBUG CHUYÊN SÂU Timeout (theo dõi từng bước)")
        print("G. Cấu hình giá trị mặc định")
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
        elif choice == "L":
            add_limit_data()
        elif choice == "K":
            add_close_stream()
        elif choice == "B":
            add_bandwidth()
        elif choice == "P":
            add_slicer()
        elif choice == "F":
            add_both_latency_and_timeout()
        elif choice == "S":
            show_proxy_info()
        elif choice == "E":
            clear_toxics()
        elif choice == "R":
            test_retry_logic()
        elif choice == "W":
            test_fallback_data()
        elif choice == "1":
            scenario_timeout_then_retry()
        elif choice == "2":
            scenario_partial_commit()
        elif choice == "T":
            deep_debug_timeout()
        elif choice == "G":
            configure_defaults()
        elif choice == "7":
            check_services()
        else:
            print("Lựa chọn không hợp lệ!")


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║       V-Bank 2PC - Toxiproxy Test Script             ║
    ║       Fixed: stream='upstream' for timeout            ║
    ╚══════════════════════════════════════════════════════════╝

    ⚠️  QUAN TRỌNG:
    - Latency → downstream (delay response)
    - Timeout → upstream (chờ backend phản hồi)
    - REQUEST_TIMEOUT (30s) > DEFAULT_TIMEOUT (5000ms)
    """)

    check_services()
    menu()
