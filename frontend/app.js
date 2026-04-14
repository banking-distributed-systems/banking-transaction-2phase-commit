// Sử dụng proxy để test các lỗi mạng/toxic
const API_URL = "http://localhost:8666/api";
let currentUser = null;
let balanceVisible = false;
let lookupTimer = null;
let resolvedToAccount = null;
let toastTimer = null;

function showToast(type, title, msg) {
  const toast = document.getElementById("toast");
  const iconMap = {
    success: "fa-check-circle",
    error: "fa-times-circle",
    info: "fa-info-circle",
  };
  document.getElementById("toastTitle").textContent = title;
  document.getElementById("toastMsg").textContent = msg;
  document.getElementById("toastIconI").className =
    `fas ${iconMap[type] || "fa-info-circle"}`;
  toast.className = `toast ${type}`;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(closeToast, 3500);
}

function closeToast() {
  const toast = document.getElementById("toast");
  toast.classList.remove("show");
}

function parseLogPayload(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function parseRequestBody(body) {
  if (!body) return null;
  if (typeof body !== "string") return body;
  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
}

async function readJsonSafe(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function buildApiErrorMessage(response, payload, fallbackMessage) {
  const messageFromPayload =
    payload?.message || payload?.error?.message || payload?.error?.detail;
  const message = messageFromPayload || fallbackMessage;
  const errorCode = payload?.error?.code;
  const requestId = payload?.error?.request_id || response.headers.get("X-Request-ID");

  let fullMessage = message;
  if (errorCode) {
    fullMessage = `[${errorCode}] ${fullMessage}`;
  }
  if (requestId) {
    fullMessage = `${fullMessage} (ref: ${requestId})`;
  }
  return fullMessage;
}

async function apiFetch(url, options = {}, label = "API") {
  const method = options.method || "GET";
  const start = Date.now();
  const requestBody = parseRequestBody(options.body);

  console.groupCollapsed(`[${label}] ${method} ${url}`);
  if (requestBody !== null) {
    console.log("request:", requestBody);
  }

  let res;
  try {
    res = await fetch(url, options);
  } catch (error) {
    const elapsedMs = Date.now() - start;
    console.error(
      "network error:",
      error?.message || error,
      `(${elapsedMs}ms)`,
    );
    console.groupEnd();
    throw error;
  }

  const elapsedMs = Date.now() - start;
  try {
    const responseText = await res.clone().text();
    const responsePayload = parseLogPayload(responseText);
    console.log(
      "status:",
      `${res.status} ${res.statusText}`,
      `(${elapsedMs}ms)`,
    );
    console.log("response:", responsePayload);
  } catch (error) {
    console.log(
      "status:",
      `${res.status} ${res.statusText}`,
      `(${elapsedMs}ms)`,
    );
    console.warn("response parse error:", error?.message || error);
    console.groupEnd();

    const wrappedError = new Error("response_parse_error");
    wrappedError.name = "ResponseParseError";
    wrappedError.isResponseParseError = true;
    wrappedError.httpStatus = res.status;
    wrappedError.originalMessage = error?.message || String(error);
    throw wrappedError;
  }

  if (!res.ok) {
    console.warn("non-2xx status response");
  }
  console.groupEnd();
  return res;
}

function formatMoney(amount) {
  return new Intl.NumberFormat("vi-VN").format(amount) + " VND";
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "CHÀO BUỔI SÁNG,";
  if (h < 18) return "CHÀO BUỔI CHIỀU,";
  return "CHÀO BUỔI TỐI,";
}

function togglePassword() {
  const input = document.getElementById("loginPassword");
  const icon = document.querySelector(".toggle-password");
  if (input.type === "password") {
    input.type = "text";
    icon.classList.replace("fa-eye", "fa-eye-slash");
  } else {
    input.type = "password";
    icon.classList.replace("fa-eye-slash", "fa-eye");
  }
}

async function doLogin() {
  const phone = document.getElementById("loginPhone").value.trim();
  const password = document.getElementById("loginPassword").value;
  const msgDiv = document.getElementById("loginMessage");
  msgDiv.textContent = "";

  if (!phone || !password) {
    showToast("error", "Thiếu thông tin", "Vui lòng nhập đầy đủ thông tin");
    return;
  }

  try {
    const res = await apiFetch(
      `${API_URL}/login`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, password }),
      },
      "LOGIN",
    );
    const data = await readJsonSafe(res);
    if (res.ok && data?.status === "success") {
      currentUser = data.user;
      showDashboard();
    } else {
      const message = buildApiErrorMessage(
        res,
        data,
        "Đăng nhập thất bại",
      );
      showToast(
        "error",
        `Đăng nhập thất bại (${res.status})`,
        message,
      );
    }
  } catch (e) {
    if (e?.isResponseParseError) {
      const statusPart = e.httpStatus ? `HTTP ${e.httpStatus}` : "HTTP unknown";
      showToast(
        "error",
        "Lỗi xử lý dữ liệu",
        `${statusPart}: Server trả dữ liệu không đọc được. Có thể phản hồi bị cắt do lỗi mạng/toxic.`,
      );
      return;
    }

    showToast(
      "error",
      "Lỗi kết nối",
      "⚠️ Không thể kết nối đến hệ thống lúc này.Vui lòng kiểm tra mạng hoặc thử lại sau. (có thể do toxic hoặc mạng chậm)! (1)",
    );
  }
}

function showDashboard() {
  document.getElementById("loginScreen").style.display = "none";
  document.getElementById("receiptScreen").style.display = "none";
  document.getElementById("dashboardScreen").style.display = "flex";

  document.getElementById("greeting").textContent = getGreeting();
  document.getElementById("dashUserName").textContent = currentUser.name;
  document.getElementById("avatarCircle").textContent = currentUser.name
    .charAt(0)
    .toUpperCase();
  document.getElementById("accountNumber").textContent =
    currentUser.account_number;
  document.getElementById("accountBadge").textContent =
    currentUser.account_type;

  balanceVisible = false;
  document.getElementById("mainBalance").textContent = "******* VND";

  fetchAccounts();
}

function showReceipt(txData) {
  document.getElementById("dashboardScreen").style.display = "none";
  document.getElementById("transferModal").style.display = "none";
  document.getElementById("receiptScreen").style.display = "flex";

  document.getElementById("receiptAmount").textContent = formatMoney(
    txData.amount,
  );
  document.getElementById("receiptAmountRow").textContent = formatMoney(
    txData.amount,
  );
  document.getElementById("receiptTxId").textContent = txData.txId;
  document.getElementById("receiptTime").textContent = txData.time;
  // document.getElementById('receiptFromName').textContent = txData.fromName;
  document.getElementById("receiptFromNum").textContent = txData.fromNum;
  document.getElementById("receiptToName").textContent = txData.toName;
  document.getElementById("receiptToNum").textContent = txData.toNum;
  document.getElementById("receiptDesc").textContent =
    txData.description || "Chuyển tiền";
}

function toggleBalance() {
  const el = document.getElementById("mainBalance");
  const icon = document.getElementById("toggleBalanceEye");
  balanceVisible = !balanceVisible;
  if (balanceVisible) {
    el.textContent = formatMoney(currentUser.balance);
    icon.classList.replace("fa-eye", "fa-eye-slash");
  } else {
    el.textContent = "******* VND";
    icon.classList.replace("fa-eye-slash", "fa-eye");
  }
}

function copyAccountNumber() {
  const num = currentUser.account_number;
  navigator.clipboard.writeText(num.replace(/\s/g, ""));
}

async function fetchAccounts() {
  try {
    const response = await apiFetch(`${API_URL}/accounts`, {}, "ACCOUNTS");
    const data = await readJsonSafe(response);
    if (!response.ok) {
      const message = buildApiErrorMessage(
        response,
        data,
        "Không thể tải danh sách tài khoản",
      );
      showToast("error", `Lỗi tải dữ liệu (${response.status})`, message);
      return;
    }

    const accounts = Array.isArray(data) ? data : [];
    // Update current user balance
    if (currentUser) {
      const me = accounts.find((a) => a.id === currentUser.id);
      if (me) {
        currentUser.balance = parseFloat(me.balance);
        if (balanceVisible) {
          document.getElementById("mainBalance").textContent = formatMoney(
            currentUser.balance,
          );
        }
      }
    }
  } catch (error) {
    showToast(
      "error",
      "Lỗi mạng",
      "Không thể lấy danh sách tài khoản (có thể do toxic hoặc mạng chậm)!",
    );
    console.error("Error fetching accounts:", error);
  }
}

function openTransferModal() {
  document.getElementById("transferModal").style.display = "flex";
  document.getElementById("amount").value = "";
  document.getElementById("toAccountInput").value = "";
  document.getElementById("toAccountResult").innerHTML = "";
  resolvedToAccount = null;

  // Show current user as "from" account
  if (currentUser) {
    document.getElementById("fromAccountName").textContent = currentUser.name;
    document.getElementById("fromAccountNum").textContent =
      currentUser.account_number;
    document.getElementById("description").value =
      `${currentUser.name} chuyen tien`;
  }
}

function onToAccountInput() {
  clearTimeout(lookupTimer);
  resolvedToAccount = null;
  const input = document.getElementById("toAccountInput").value.trim();
  const resultDiv = document.getElementById("toAccountResult");

  if (!input) {
    resultDiv.innerHTML = "";
    return;
  }

  resultDiv.innerHTML =
    '<span class="lookup-loading"><i class="fas fa-spinner fa-spin"></i> Đang tìm...</span>';

  lookupTimer = setTimeout(async () => {
    try {
      const res = await apiFetch(
        `${API_URL}/lookup-account`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account_number: input }),
        },
        "LOOKUP",
      );
        const data = await readJsonSafe(res);
      if (res.ok && data?.status === "success") {
        resolvedToAccount = data.account;
        resultDiv.innerHTML = `<span class="lookup-found"><i class="fas fa-check-circle"></i> ${data.account.name}</span>`;
      } else {
          const message = buildApiErrorMessage(
            res,
            data,
            "Không tìm thấy tài khoản",
          );
          resultDiv.innerHTML = `<span class="lookup-error"><i class="fas fa-times-circle"></i> ${message}</span>`;
      }
    } catch (err) {
        let msg = "Lỗi kết nối khi tra cứu tài khoản";
        if (err?.isResponseParseError) {
          const statusPart = err.httpStatus ? `HTTP ${err.httpStatus}` : "HTTP unknown";
          msg = `${statusPart}: Phản hồi không đọc được (có thể bị cắt do toxic limit_data).`;
        } else if (err && err.name === "AbortError") {
          msg = "Timeout khi tra cứu tài khoản";
      }
      resultDiv.innerHTML = `<span class="lookup-error"><i class="fas fa-exclamation-circle"></i> ${msg}</span>`;
    }
  }, 500);
}

function closeTransferModal() {
  document.getElementById("transferModal").style.display = "none";
}

function confirmTransfer() {
  const amountVal = document.getElementById("amount").value;
  const description = document.getElementById("description").value.trim();

  if (!resolvedToAccount) {
    showToast("error", "Lỗi", "Vui lòng nhập số tài khoản người nhận hợp lệ!");
    return;
  }
  if (!amountVal || amountVal <= 0) {
    showToast("error", "Lỗi", "Số tiền không hợp lệ!");
    return;
  }

  // Điền thông tin vào dialog
  document.getElementById("confirmToName").textContent = resolvedToAccount.name;
  document.getElementById("confirmToNum").textContent =
    resolvedToAccount.account_number;
  document.getElementById("confirmAmount").textContent =
    parseInt(amountVal).toLocaleString("vi-VN") + " đ";
  document.getElementById("confirmDesc").textContent =
    description || "(Không có)";

  document.getElementById("confirmOverlay").classList.add("show");
}

function closeConfirm() {
  document.getElementById("confirmOverlay").classList.remove("show");
}

async function executeTransfer() {
  closeConfirm();
  const amountVal = document.getElementById("amount").value;
  const description = document.getElementById("description").value.trim();

  if (!resolvedToAccount) {
    showToast("error", "Lỗi", "Vui lòng nhập số tài khoản người nhận hợp lệ!");
    return;
  }

  if (!amountVal || amountVal <= 0) {
    showToast("error", "Lỗi", "Số tiền không hợp lệ!");
    return;
  }

  showToast("info", "Đang xử lý", "Đang thực hiện 2-Phase Commit...");

  try {
    const response = await apiFetch(
      `${API_URL}/transfer`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_account_number: currentUser.account_number,
          to_account_number: resolvedToAccount.account_number,
          amount: parseFloat(amountVal),
          description,
        }),
      },
      "TRANSFER",
    );
    const result = await readJsonSafe(response);
    if (response.ok) {
      const now = new Date();
      const timeStr = now.toLocaleString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
      const txId =
        result?.tx_id || "VB" + Date.now().toString().slice(-10).toUpperCase();

      closeToast();
      closeTransferModal();
      fetchAccounts();
      showReceipt({
        amount: parseFloat(amountVal),
        txId,
        time: timeStr,
        fromName: currentUser.name,
        fromNum: currentUser.account_number,
        toName: resolvedToAccount.name,
        toNum: resolvedToAccount.account_number,
        description,
      });
    } else {
      const message = buildApiErrorMessage(
        response,
        result,
        "Giao dịch thất bại",
      );
      showToast(
        "error",
        `Giao dịch thất bại (${response.status})`,
        message,
      );
    }
  } catch (error) {
    if (error?.isResponseParseError) {
      const statusPart = error.httpStatus ? `HTTP ${error.httpStatus}` : "HTTP unknown";
      showToast(
        "error",
        "Lỗi dữ liệu phản hồi",
        `${statusPart}: Dữ liệu trả về không đọc được (có thể bị cắt do toxic limit_data).`,
      );
      return;
    }

    showToast(
      "error",
      "Lỗi kết nối",
      "Không thể kết nối đến hệ thống lúc này. Vui lòng kiểm tra mạng hoặc thử lại sau.",
    );
  }
}

// Allow Enter key to login
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("loginPassword").addEventListener("keydown", (e) => {
    if (e.key === "Enter") doLogin();
  });
});
