const API_URL = 'http://localhost:5000/api';
let currentUser = null;
let balanceVisible = false;
let lookupTimer = null;
let resolvedToAccount = null;
let toastTimer = null;

function showToast(type, title, msg) {
    const toast = document.getElementById('toast');
    const iconMap = { success: 'fa-check-circle', error: 'fa-times-circle', info: 'fa-info-circle' };
    document.getElementById('toastTitle').textContent = title;
    document.getElementById('toastMsg').textContent = msg;
    document.getElementById('toastIconI').className = `fas ${iconMap[type] || 'fa-info-circle'}`;
    toast.className = `toast ${type}`;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(closeToast, 3500);
}

function closeToast() {
    const toast = document.getElementById('toast');
    toast.classList.remove('show');
}

function formatMoney(amount) {
    return new Intl.NumberFormat('vi-VN').format(amount) + ' VND';
}

function getGreeting() {
    const h = new Date().getHours();
    if (h < 12) return 'CHÀO BUỔI SÁNG,';
    if (h < 18) return 'CHÀO BUỔI CHIỀU,';
    return 'CHÀO BUỔI TỐI,';
}

function togglePassword() {
    const input = document.getElementById('loginPassword');
    const icon = document.querySelector('.toggle-password');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
    }
}

async function doLogin() {
    const phone = document.getElementById('loginPhone').value.trim();
    const password = document.getElementById('loginPassword').value;
    const msgDiv = document.getElementById('loginMessage');

    if (!phone || !password) {
        msgDiv.textContent = 'Vui lòng nhập đầy đủ thông tin';
        msgDiv.className = 'login-message error';
        return;
    }

    try {
        const res = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, password })
        });
        const data = await res.json();

        if (res.ok && data.status === 'success') {
            currentUser = data.user;
            showDashboard();
        } else {
            msgDiv.textContent = data.message || 'Đăng nhập thất bại';
            msgDiv.className = 'login-message error';
        }
    } catch (e) {
        msgDiv.textContent = 'Lỗi kết nối tới server!';
        msgDiv.className = 'login-message error';
    }
}

function showDashboard() {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('receiptScreen').style.display = 'none';
    document.getElementById('dashboardScreen').style.display = 'flex';

    document.getElementById('greeting').textContent = getGreeting();
    document.getElementById('dashUserName').textContent = currentUser.name;
    document.getElementById('avatarCircle').textContent = currentUser.name.charAt(0).toUpperCase();
    document.getElementById('accountNumber').textContent = currentUser.account_number;
    document.getElementById('accountBadge').textContent = currentUser.account_type;

    balanceVisible = false;
    document.getElementById('mainBalance').textContent = '******* VND';

    fetchAccounts();
}

function showReceipt(txData) {
    document.getElementById('dashboardScreen').style.display = 'none';
    document.getElementById('transferModal').style.display = 'none';
    document.getElementById('receiptScreen').style.display = 'flex';

    document.getElementById('receiptAmount').textContent = formatMoney(txData.amount);
    document.getElementById('receiptAmountRow').textContent = formatMoney(txData.amount);
    document.getElementById('receiptTxId').textContent = txData.txId;
    document.getElementById('receiptTime').textContent = txData.time;
    // document.getElementById('receiptFromName').textContent = txData.fromName;
    document.getElementById('receiptFromNum').textContent = txData.fromNum;
    document.getElementById('receiptToName').textContent = txData.toName;
    document.getElementById('receiptToNum').textContent = txData.toNum;
    document.getElementById('receiptDesc').textContent = txData.description || 'Chuyển tiền';
}

function toggleBalance() {
    const el = document.getElementById('mainBalance');
    const icon = document.getElementById('toggleBalanceEye');
    balanceVisible = !balanceVisible;
    if (balanceVisible) {
        el.textContent = formatMoney(currentUser.balance);
        icon.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
        el.textContent = '******* VND';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
    }
}

function copyAccountNumber() {
    const num = currentUser.account_number;
    navigator.clipboard.writeText(num.replace(/\s/g, ''));
}

async function fetchAccounts() {
    try {
        const response = await fetch(`${API_URL}/accounts`);
        const accounts = await response.json();

        // Update current user balance
        if (currentUser) {
            const me = accounts.find(a => a.id === currentUser.id);
            if (me) {
                currentUser.balance = parseFloat(me.balance);
                if (balanceVisible) {
                    document.getElementById('mainBalance').textContent = formatMoney(currentUser.balance);
                }
            }
        }
    } catch (error) {
        console.error("Error fetching accounts:", error);
    }
}

function openTransferModal() {
    document.getElementById('transferModal').style.display = 'flex';
    document.getElementById('amount').value = '';
    document.getElementById('toAccountInput').value = '';
    document.getElementById('toAccountResult').innerHTML = '';
    resolvedToAccount = null;

    // Show current user as "from" account
    if (currentUser) {
        document.getElementById('fromAccountName').textContent = currentUser.name;
        document.getElementById('fromAccountNum').textContent = currentUser.account_number;
        document.getElementById('description').value = `${currentUser.name} chuyen tien`;
    }
}

function onToAccountInput() {
    clearTimeout(lookupTimer);
    resolvedToAccount = null;
    const input = document.getElementById('toAccountInput').value.trim();
    const resultDiv = document.getElementById('toAccountResult');

    if (!input) {
        resultDiv.innerHTML = '';
        return;
    }

    resultDiv.innerHTML = '<span class="lookup-loading"><i class="fas fa-spinner fa-spin"></i> Đang tìm...</span>';

    lookupTimer = setTimeout(async () => {
        try {
            const res = await fetch(`${API_URL}/lookup-account`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_number: input })
            });
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                resolvedToAccount = data.account;
                resultDiv.innerHTML = `<span class="lookup-found"><i class="fas fa-check-circle"></i> ${data.account.name}</span>`;
            } else {
                resultDiv.innerHTML = `<span class="lookup-error"><i class="fas fa-times-circle"></i> Không tìm thấy tài khoản</span>`;
            }
        } catch {
            resultDiv.innerHTML = `<span class="lookup-error"><i class="fas fa-exclamation-circle"></i> Lỗi kết nối</span>`;
        }
    }, 500);
}

function closeTransferModal() {
    document.getElementById('transferModal').style.display = 'none';
}

function confirmTransfer() {
    const amountVal = document.getElementById('amount').value;
    const description = document.getElementById('description').value.trim();

    if (!resolvedToAccount) {
        showToast('error', 'Lỗi', 'Vui lòng nhập số tài khoản người nhận hợp lệ!');
        return;
    }
    if (!amountVal || amountVal <= 0) {
        showToast('error', 'Lỗi', 'Số tiền không hợp lệ!');
        return;
    }

    // Điền thông tin vào dialog
    document.getElementById('confirmToName').textContent = resolvedToAccount.name;
    document.getElementById('confirmToNum').textContent  = resolvedToAccount.account_number;
    document.getElementById('confirmAmount').textContent =
        parseInt(amountVal).toLocaleString('vi-VN') + ' đ';
    document.getElementById('confirmDesc').textContent   = description || '(Không có)';

    document.getElementById('confirmOverlay').classList.add('show');
}

function closeConfirm() {
    document.getElementById('confirmOverlay').classList.remove('show');
}

async function executeTransfer() {
    closeConfirm();
    const amountVal = document.getElementById('amount').value;
    const description = document.getElementById('description').value.trim();

    if (!resolvedToAccount) {
        showToast('error', 'Lỗi', 'Vui lòng nhập số tài khoản người nhận hợp lệ!');
        return;
    }

    if (!amountVal || amountVal <= 0) {
        showToast('error', 'Lỗi', 'Số tiền không hợp lệ!');
        return;
    }

    showToast('info', 'Đang xử lý', 'Đang thực hiện 2-Phase Commit...');

    try {
        const response = await fetch(`${API_URL}/transfer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from_account_number: currentUser.account_number,
                to_account_number: resolvedToAccount.account_number,
                amount: parseFloat(amountVal),
                description
            })
        });
        const result = await response.json();

        if (response.ok) {
            const now = new Date();
            const timeStr = now.toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' });
            const txId = result.tx_id || ('VB' + Date.now().toString().slice(-10).toUpperCase());

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
                description
            });
        } else {
            showToast('error', 'Giao dịch thất bại', result.message);
        }
    } catch (error) {
        showToast('error', 'Lỗi kết nối', 'Không thể kết nối tới server!');
    }
}

// Allow Enter key to login
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('loginPassword').addEventListener('keydown', e => {
        if (e.key === 'Enter') doLogin();
    });
});
