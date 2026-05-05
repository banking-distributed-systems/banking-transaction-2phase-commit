// Sử dụng proxy để test các lỗi mạng/toxic
const API_URL = "http://localhost:8666/api";
const SESSION_STORAGE_KEY = "vbank_current_user";
let currentUser = null;
let balanceVisible = false;
let lookupTimer = null;
let resolvedToAccount = null;
let toastTimer = null;
let pendingTransferIdempotencyKey = null;
let txAutoRefreshTimer = null;

function persistCurrentUser() {
  if (!currentUser) return;
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(currentUser));
  } catch (error) {
    console.warn("Không thể lưu session đăng nhập:", error?.message || error);
  }
}

function clearPersistedSession() {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  } catch (error) {
    console.warn("Không thể xóa session đã lưu:", error?.message || error);
  }
}

function restoreSessionFromStorage() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.name || !parsed.account_number) {
      clearPersistedSession();
      return null;
    }
    return parsed;
  } catch {
    clearPersistedSession();
    return null;
  }
}

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
  const requestId =
    payload?.error?.request_id || response.headers.get("X-Request-ID");

  let fullMessage = message;
  if (errorCode) {
    fullMessage = `[${errorCode}] ${fullMessage}`;
  }
  if (requestId) {
    fullMessage = `${fullMessage} (ref: ${requestId})`;
  }
  return fullMessage;
}

function mapPhaseHint(phase) {
  const hints = {
    PREPARING: "Đang chuẩn bị giao dịch ở cả 2 participant.",
    PREPARED: "Đã sẵn sàng commit.",
    COMMITTING: "Coordinator đang gửi commit.",
    COMMIT_A: "A đã commit, B chưa commit xong.",
    COMMITTED: "Giao dịch đã hoàn tất thành công.",
    ABORTED: "Giao dịch đã rollback/hủy.",
    TIMEOUT: "Giao dịch timeout ở Phase 1.",
    COMPENSATING: "Hệ thống đang hoàn tiền bù.",
    COMPENSATED: "Đã hoàn tiền bù thành công.",
  };
  return hints[phase] || "Trạng thái đang được cập nhật.";
}

function renderTxStatus(data) {
  const box = document.getElementById("statusTxResult");
  if (!box) return;

  if (!data) {
    box.textContent = "Không có dữ liệu giao dịch.";
    return;
  }

  const phaseClass = `phase-${data.phase || "UNKNOWN"}`;
  box.innerHTML = `
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
  <strong style="font-size:13px">${escHtml(data.tx_id || "-")}</strong>
  <span class="tx-phase-badge ${escHtml(phaseClass)}">${escHtml(data.phase || "UNKNOWN")}</span>
</div>
<div style="font-size:11px;color:#6b7b8d;line-height:1.6">
  <div><b>Chi tiết:</b> ${escHtml(data.phase_label || "-")}</div>
  <div><b>Nguồn → Đích:</b> ${escHtml(data.from_account_number || "-")} → ${escHtml(data.to_account_number || "-")}</div>
  <div><b>Số tiền:</b> ${(data.amount || 0).toLocaleString("vi-VN")} VND</div>
  <div><b>Thông điệp:</b> ${escHtml(data.message || mapPhaseHint(data.phase))}</div>
  <div><b>Cập nhật:</b> ${escHtml(data.updated_at || "-")}</div>
</div>`;
}

function escHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _logLineClass(line) {
  if (line.includes("ERROR")) return "log-error";
  if (line.includes("[PARTIAL COMMIT]") || line.includes("[COMPENSAT"))
    return "log-partial";
  if (line.includes("WARNING") || line.includes("[COMPENSAT"))
    return "log-phase-warn";
  if (line.includes("[BAL]")) {
    const label = line.match(/\[BAL\]\s+(\S+)/)?.[1] || "";
    if (label.startsWith("TRƯỚC")) return "log-bal-before";
    if (label.startsWith("SAU-COMPENS") || label.startsWith("TRƯỚC-COMP"))
      return "log-bal-comp";
    return "log-bal-after";
  }
  if (line.includes("[PHASE]")) return "log-phase";
  return "";
}

function renderTxLog(lines) {
  const panel = document.getElementById("txLogPanel");
  if (!panel) return;
  if (!Array.isArray(lines) || lines.length === 0) {
    panel.classList.remove("has-lines");
    panel.innerHTML =
      '<span class="tx-log-empty">Chưa có log cho giao dịch này.</span>';
    return;
  }
  panel.classList.add("has-lines");
  panel.innerHTML = lines
    .map((line) => {
      const cls = _logLineClass(line);
      return `<span class="tx-log-line ${cls}">${escHtml(line)}</span>`;
    })
    .join("\n");
  panel.scrollTop = panel.scrollHeight;
}

async function fetchTxLog(txId) {
  try {
    const res = await apiFetch(
      `${API_URL}/transfer/log/${encodeURIComponent(txId)}`,
      {},
      "TX-LOG",
    );
    const payload = await readJsonSafe(res);
    if (res.ok && payload?.status === "success") {
      renderTxLog(payload.lines || []);
    } else {
      renderTxLog([]);
    }
  } catch {
    renderTxLog([]);
  }
}

function renderRecentTransactions(items = []) {
  const box = document.getElementById("txRecentList");
  if (!box) return;

  if (!Array.isArray(items) || items.length === 0) {
    box.textContent = "Chưa có giao dịch gần nhất.";
    return;
  }

  box.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "tx-recent-item";

    const top = document.createElement("div");
    top.className = "tx-recent-top";

    const txId = document.createElement("strong");
    txId.textContent = item.tx_id || "-";

    const phase = document.createElement("span");
    phase.className = `tx-phase-badge phase-${item.phase || "UNKNOWN"}`;
    phase.textContent = item.phase || "UNKNOWN";

    top.appendChild(txId);
    top.appendChild(phase);

    const detail = document.createElement("div");
    detail.textContent = `${(item.amount || 0).toLocaleString("vi-VN")} VND | ${item.updated_at || "-"}`;

    row.appendChild(top);
    row.appendChild(detail);
    row.addEventListener("click", () => lookupTransactionStatus(item.tx_id));
    box.appendChild(row);
  });
}

async function fetchRecentTransactions(limit = 8) {
  try {
    const res = await apiFetch(
      `${API_URL}/transfer/recent?limit=${encodeURIComponent(limit)}`,
      {},
      "TX-RECENT",
    );
    const payload = await readJsonSafe(res);
    if (!res.ok || payload?.status !== "success") {
      renderRecentTransactions([]);
      return;
    }
    renderRecentTransactions(payload.items || []);
  } catch {
    renderRecentTransactions([]);
  }
}

async function lookupTransactionStatus(txIdOverride = null, options = {}) {
  const { silent = false } = options;
  const input = document.getElementById("statusTxIdInput");
  const txId = (txIdOverride || input?.value || "").trim();
  const box = document.getElementById("statusTxResult");

  if (!txId) {
    if (box) box.textContent = "Vui lòng nhập mã giao dịch.";
    return;
  }

  if (input && txIdOverride) {
    input.value = txId;
  }

  if (box && !silent) box.textContent = "Đang tra cứu trạng thái...";

  try {
    const res = await apiFetch(
      `${API_URL}/transfer/status/${encodeURIComponent(txId)}`,
      {},
      "TX-STATUS",
    );
    const payload = await readJsonSafe(res);

    if (!res.ok || payload?.status !== "success") {
      const message = buildApiErrorMessage(
        res,
        payload,
        "Không thể tra cứu trạng thái giao dịch",
      );
      if (box) box.textContent = message;
      return;
    }

    renderTxStatus(payload.data);
    await fetchTxLog(txId);
  } catch (error) {
    if (box) box.textContent = "Lỗi kết nối khi tra cứu trạng thái giao dịch.";
  }
}

async function runManualRecovery() {
  showToast("info", "Recovery", "Đang chạy recovery thủ công...");
  try {
    const res = await apiFetch(
      `${API_URL}/recover`,
      { method: "POST", headers: { "Content-Type": "application/json" } },
      "RECOVERY",
    );
    const data = await readJsonSafe(res);
    if (!res.ok || data?.status !== "success") {
      const message = buildApiErrorMessage(
        res,
        data,
        "Không thể chạy recovery",
      );
      showToast("error", `Recovery lỗi (${res.status})`, message);
      return;
    }

    showToast(
      "success",
      "Recovery hoàn tất",
      `Đã xử lý ${data.count || 0} giao dịch treo.`,
    );
    await fetchRecentTransactions();
    const txId = document.getElementById("statusTxIdInput")?.value?.trim();
    if (txId) {
      await lookupTransactionStatus(txId, { silent: true });
    }
  } catch {
    showToast("error", "Recovery lỗi", "Không thể kết nối để chạy recovery.");
  }
}

function stopTxAutoRefresh() {
  if (txAutoRefreshTimer) {
    clearInterval(txAutoRefreshTimer);
    txAutoRefreshTimer = null;
  }
}

function startTxAutoRefresh() {
  stopTxAutoRefresh();
  txAutoRefreshTimer = setInterval(async () => {
    const dashboard = document.getElementById("dashboardScreen");
    if (!dashboard || dashboard.style.display === "none") {
      return;
    }

    await fetchRecentTransactions();
    const txId = document.getElementById("statusTxIdInput")?.value?.trim();
    if (txId) {
      await lookupTransactionStatus(txId, { silent: true });
    }
  }, 8000);
}

function toggleTxAutoRefresh() {
  const toggle = document.getElementById("txAutoRefresh");
  if (toggle?.checked) {
    startTxAutoRefresh();
  } else {
    stopTxAutoRefresh();
  }
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

async function doLogin() {
  const phone = document.getElementById("loginPhone").value.trim();
  const password = document.getElementById("loginPassword").value;
  const msgDiv = document.getElementById("loginMessage");
  msgDiv.textContent = "";

  if (!phone) {
    showToast("error", "Thiếu thông tin", "Vui lòng nhập số điện thoại");
    return;
  }

  if (!password) {
    showToast("error", "Thiếu thông tin", "Vui lòng nhập mật khẩu");
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
      persistCurrentUser();
      showDashboard();
    } else {
      const message = buildApiErrorMessage(res, data, "Đăng nhập thất bại");
      showToast("error", `Đăng nhập thất bại (${res.status})`, message);
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
  if (!currentUser) {
    document.getElementById("dashboardScreen").style.display = "none";
    document.getElementById("receiptScreen").style.display = "none";
    document.getElementById("loginScreen").style.display = "block";
    return;
  }

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
  document.getElementById("accountBadge").textContent = (
    currentUser.account_type ||
    currentUser.bank ||
    "BANK"
  ).toUpperCase();

  balanceVisible = false;
  document.getElementById("mainBalance").textContent = "******* VND";

  fetchAccounts();
  fetchRecentTransactions();
  const autoToggle = document.getElementById("txAutoRefresh");
  if (!autoToggle || autoToggle.checked) {
    startTxAutoRefresh();
  }
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
      const me = accounts.find(
        (a) => a.account_number === currentUser.account_number,
      );
      if (me) {
        currentUser.balance = parseFloat(me.balance);
        currentUser.account_type = me.account_type || currentUser.account_type;
        currentUser.bank = me.bank || currentUser.bank;
        persistCurrentUser();
        document.getElementById("accountBadge").textContent = (
          currentUser.account_type ||
          currentUser.bank ||
          "BANK"
        ).toUpperCase();
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
  pendingTransferIdempotencyKey = null;

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
        const statusPart = err.httpStatus
          ? `HTTP ${err.httpStatus}`
          : "HTTP unknown";
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

  if (!pendingTransferIdempotencyKey) {
    pendingTransferIdempotencyKey = `IDEMP-${Date.now()}-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
  }

  try {
    const response = await apiFetch(
      `${API_URL}/transfer`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": pendingTransferIdempotencyKey,
        },
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

      lookupTransactionStatus(txId);

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
      pendingTransferIdempotencyKey = null;
    } else {
      const message = buildApiErrorMessage(
        response,
        result,
        "Giao dịch thất bại",
      );

      if (result?.tx_id) {
        lookupTransactionStatus(result.tx_id);
      }

      if (result?.error_code !== "IDEMPOTENCY_REQUEST_IN_PROGRESS") {
        pendingTransferIdempotencyKey = null;
      }

      showToast("error", `Giao dịch thất bại (${response.status})`, message);
    }
  } catch (error) {
    if (error?.isResponseParseError) {
      const statusPart = error.httpStatus
        ? `HTTP ${error.httpStatus}`
        : "HTTP unknown";
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
  const loginPhoneInput = document.getElementById("loginPhone");
  const loginPasswordInput = document.getElementById("loginPassword");

  if (loginPhoneInput) {
    loginPhoneInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") doLogin();
    });
  }

  if (loginPasswordInput) {
    loginPasswordInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") doLogin();
    });
  }

  const restoredUser = restoreSessionFromStorage();
  if (restoredUser) {
    currentUser = restoredUser;
    showDashboard();
  }
});
