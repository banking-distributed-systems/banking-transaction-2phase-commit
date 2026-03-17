import requests
import time
import json
import traceback

API_VIA_PROXY = "http://localhost:8666/api"
API_DIRECT = "http://localhost:5000/api"

API_TIMEOUT = 5
REQUEST_TIMEOUT = 30

DEBUG = True

def debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

# ============================================================
# 🔥 CORE: PHÂN LOẠI LỖI CHUẨN
# ============================================================

def analyze_exception(e, start_time):
    elapsed = time.time() - start_time

    print("\n📊 PHÂN TÍCH LỖI:")
    print("-" * 40)
    print(f"⏱️  Thời gian: {elapsed:.2f}s")

    if isinstance(e, requests.exceptions.Timeout):
        print("❌ CLIENT TIMEOUT")
        print("→ Client chờ quá lâu, server không phản hồi")
        return

    err_str = str(e)

    if "RemoteDisconnected" in err_str:
        print("💣 CONNECTION BỊ ĐÓNG (NETWORK FAILURE)")
        print("→ Toxiproxy timeout/reset đã kill connection")
        return

    if "Connection refused" in err_str:
        print("❌ KHÔNG KẾT NỐI ĐƯỢC")
        print("→ Proxy hoặc backend chưa chạy")
        return

    print("❓ LỖI KHÁC:")
    print(err_str)

# ============================================================
# TEST FUNCTION CHUẨN
# ============================================================

def safe_request(method, url, **kwargs):
    debug(f"Calling {method.upper()} {url}")
    start = time.time()

    try:
        res = requests.request(method, url, **kwargs)
        elapsed = time.time() - start

        print(f"✅ SUCCESS - {res.status_code} ({elapsed:.2f}s)")

        try:
            print(json.dumps(res.json(), indent=2, ensure_ascii=False))
        except:
            print(res.text[:200])

        return res

    except Exception as e:
        print(f"❌ ERROR: {e}")
        analyze_exception(e, start)

        if DEBUG:
            traceback.print_exc()

        return None

# ============================================================
# PROXY CONTROL
# ============================================================

def create_proxy():
    requests.delete("http://localhost:8474/proxies/vbank_api")

    config = {
        "name": "vbank_api",
        "listen": "0.0.0.0:8666",
        "upstream": "host.docker.internal:5000"
    }

    res = requests.post("http://localhost:8474/proxies", json=config)

    if res.status_code in [200, 201]:
        print("✅ Proxy created")
    else:
        print("❌ Create proxy failed", res.text)


def clear_toxics():
    res = requests.get("http://localhost:8474/proxies/vbank_api")
    data = res.json()

    for t in data.get("toxics", []):
        name = t["name"]
        requests.delete(f"http://localhost:8474/proxies/vbank_api/toxics/{name}")
        print(f"🧹 Removed toxic: {name}")

# ============================================================
# TOXICS
# ============================================================

def add_latency(ms):
    toxic = {
        "name": "latency",
        "type": "latency",
        "stream": "downstream",
        "attributes": {"latency": ms}
    }

    res = requests.post("http://localhost:8474/proxies/vbank_api/toxics", json=toxic)
    print(f"✅ Added latency {ms}ms" if res.status_code in [200,201] else res.text)


def add_timeout(ms):
    toxic = {
        "name": "timeout",
        "type": "timeout",
        "stream": "upstream",
        "attributes": {"timeout": ms}
    }

    res = requests.post("http://localhost:8474/proxies/vbank_api/toxics", json=toxic)
    print(f"💣 Added timeout {ms}ms" if res.status_code in [200,201] else res.text)

# ============================================================
# TEST CASES
# ============================================================

def test_health():
    safe_request("get", f"{API_VIA_PROXY}/", timeout=REQUEST_TIMEOUT)


def test_accounts():
    safe_request("get", f"{API_VIA_PROXY}/accounts", timeout=REQUEST_TIMEOUT)


def test_transfer():
    data = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 10000,
        "description": "test"
    }

    safe_request("post", f"{API_VIA_PROXY}/transfer", json=data, timeout=REQUEST_TIMEOUT)

# ============================================================
# DEMO MODES
# ============================================================

def demo_success():
    print("🟢 DEMO: SUCCESS")
    clear_toxics()
    test_accounts()


def demo_slow():
    print("🐢 DEMO: SLOW (LATENCY)")
    clear_toxics()
    add_latency(2000)
    test_accounts()


def demo_fail():
    print("💣 DEMO: FAIL (TIMEOUT → DROP)")
    clear_toxics()
    add_timeout(3000)
    test_accounts()


def demo_mid_drop():
    print("🔥 DEMO: MID-RESPONSE DROP (LATENCY + TIMEOUT)")
    clear_toxics()

    print("⚙️ Config:")
    print("   - latency = 2000ms (delay response)")
    print("   - timeout = 3000ms (kill connection)")

    add_latency(2000)
    add_timeout(3000)

    print("🚀 Gửi request...")
    print("👉 Expect: response bị kill giữa đường")

    test_accounts()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("""
        🚀 TOXIPROXY DEBUG TOOL (PRO VERSION)

        1. Success (no toxic)
        2. Slow (latency)
        3. Fail (timeout)
        """)

    create_proxy()

    while True:
        print("\n1. Success")
        print("2. Slow (latency)")
        print("3. Fail (timeout)")
        print("4. Mid-drop (latency + timeout)")

        choice = input("\nChọn (1-4, q): ")

        if choice == "1":
            demo_success()
        elif choice == "2":
            demo_slow()
        elif choice == "3":
            demo_fail()
        elif choice == "4":
            demo_mid_drop()
        elif choice == "q":
            break
        else:
            print("Invalid")
