/* 
   HYBRID TRANSFER - Product UI Controller Script
   Handles Navigation, Connection Management, API Interactivity, and Real-time Backend Sync
*/

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

let currentTab = 'dashboard';
let pollTimer = null;

function initApp() {
    checkBackendStatus();
    pollTimer = setInterval(checkBackendStatus, 3000);
}

// Tab Switching logic
function switchTab(tabId) {
    currentTab = tabId;
    
    // Update Sidebar button active state
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('active');
    });

    const activeNavBtn = document.querySelector(`.nav-item[onclick*="${tabId}"]`);
    if (activeNavBtn) {
        activeNavBtn.classList.add('active');
    }

    // Update Page View visibility
    document.querySelectorAll('.page-view').forEach(page => {
        page.classList.remove('active');
    });

    const activePage = document.getElementById(`page-${tabId}`);
    if (activePage) {
        activePage.classList.add('active');
    }

    if (tabId === 'activity') {
        fetchLogs();
    }
}

// Modal control
function toggleConnectModal() {
    const modal = document.getElementById('connect-modal');
    if (modal.style.display === 'flex') {
        modal.style.display = 'none';
    } else {
        modal.style.display = 'flex';
    }
}

function closeConnectModal() {
    document.getElementById('connect-modal').style.display = 'none';
}

// Perform Connection via Python Backend API
async function performConnection() {
    const host = document.getElementById('modal-host').value.trim() || '127.0.0.1';
    const tcpPort = parseInt(document.getElementById('modal-tcp-port').value) || 5000;
    const udpPort = parseInt(document.getElementById('modal-udp-port').value) || 6000;
    const username = document.getElementById('modal-username').value.trim() || 'Keerthi';

    const btn = document.getElementById('modal-connect-btn');
    const errBox = document.getElementById('modal-error-msg');

    btn.disabled = true;
    btn.textContent = 'CONNECTING...';
    errBox.style.display = 'none';

    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                host: host,
                tcp_port: tcpPort,
                udp_port: udpPort,
                username: username
            })
        });

        const data = await response.json();

        if (data.success) {
            closeConnectModal();
            updateUIState(data);
            fetchLogs();
        } else {
            errBox.textContent = data.error || 'Connection failed';
            errBox.style.display = 'block';
        }
    } catch (err) {
        errBox.textContent = 'Network request error: ' + err.message;
        errBox.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.textContent = 'CONNECT TO SERVER';
    }
}

// Status Sync with Real Python Backend
async function checkBackendStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        updateUIState(status);
    } catch (e) {
        console.warn('Backend status check error:', e);
    }
}

function updateUIState(status) {
    const topServer = document.getElementById('topbar-server-val');
    const userName = document.getElementById('user-name-display');
    const userGreeting = document.getElementById('dash-greeting');
    
    if (topServer) topServer.textContent = `${status.server_host}:${status.tcp_port}`;
    if (userName) userName.textContent = status.username || 'Keerthi';
    if (userGreeting) userGreeting.textContent = status.username || 'Keerthi';

    // TCP Pill & Dashboard Status
    const tcpPill = document.getElementById('pill-tcp');
    const dashTcpVal = document.getElementById('dash-tcp-val');
    const footerTcpTxt = document.getElementById('footer-tcp-txt');
    const footerTcpDot = document.getElementById('footer-tcp-dot');

    if (status.tcp_connected) {
        if (tcpPill) {
            tcpPill.className = 'pill online';
            tcpPill.querySelector('.pill-status').textContent = 'Connected';
        }
        if (dashTcpVal) {
            dashTcpVal.className = 'stat-value status-text online';
            dashTcpVal.textContent = 'CONNECTED';
        }
        if (footerTcpTxt) footerTcpTxt.textContent = 'Connected';
        if (footerTcpDot) footerTcpDot.className = 'dot online';
    } else {
        if (tcpPill) {
            tcpPill.className = 'pill offline';
            tcpPill.querySelector('.pill-status').textContent = 'Offline';
        }
        if (dashTcpVal) {
            dashTcpVal.className = 'stat-value status-text offline';
            dashTcpVal.textContent = 'OFFLINE';
        }
        if (footerTcpTxt) footerTcpTxt.textContent = 'Disconnected';
        if (footerTcpDot) footerTcpDot.className = 'dot offline';
    }
}

// Fetch Activity Logs
async function fetchLogs() {
    try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        const logsBox = document.getElementById('logs-console-box');
        
        if (logsBox && data.logs) {
            logsBox.innerHTML = '';
            data.logs.forEach(log => {
                const line = document.createElement('div');
                line.className = 'log-line';
                line.textContent = `[${log.timestamp}] [${log.level}] ${log.message}`;
                logsBox.appendChild(line);
            });
            logsBox.scrollTop = logsBox.scrollHeight;
        }
    } catch (e) {
        console.warn('Fetch logs error:', e);
    }
}
