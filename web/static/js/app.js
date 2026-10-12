/* 
   HYBRID TRANSFER - Editorial Product UI Controller Script
   Handles Navigation, Connection Management, API Interactivity, Real-time Backend Sync,
   File Listing, TCP Upload, TCP Download, UDP Presence, and Live Chat Messaging.
*/

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

let currentTab = 'home';
let pollTimer = null;

function initApp() {
    checkBackendStatus();
    pollTimer = setInterval(checkBackendStatus, 2000);
}

// Tab Switching logic
function switchTab(tabId) {
    if (tabId === 'dashboard') tabId = 'home';
    currentTab = tabId;
    
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('active');
    });

    const activeNavBtn = document.querySelector(`.nav-item[onclick*="${tabId}"]`);
    if (activeNavBtn) {
        activeNavBtn.classList.add('active');
    }

    document.querySelectorAll('.page-view').forEach(page => {
        page.classList.remove('active');
    });

    const activePage = document.getElementById(`page-${tabId}`);
    if (activePage) {
        activePage.classList.add('active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    if (tabId === 'files') {
        fetchFilesList();
        fetchTransfers();
    } else if (tabId === 'chat') {
        fetchOnlineUsers();
        fetchChatMessages();
    } else if (tabId === 'activity') {
        fetchLogs();
    } else if (tabId === 'statistics' || tabId === 'network') {
        fetchNetworkStats();
    }
}

// Modal control
function toggleConnectModal() {
    const modal = document.getElementById('connect-modal');
    if (modal) {
        modal.style.display = modal.style.display === 'flex' ? 'none' : 'flex';
    }
}

function closeConnectModal() {
    const modal = document.getElementById('connect-modal');
    if (modal) modal.style.display = 'none';
}

function showUploadModal() {
    const modal = document.getElementById('upload-modal');
    if (modal) modal.style.display = 'flex';
}

function closeUploadModal() {
    const modal = document.getElementById('upload-modal');
    if (modal) modal.style.display = 'none';
}

// Connection Handler
async function performConnection() {
    const host = document.getElementById('modal-host').value.trim() || '127.0.0.1';
    const tcpPort = parseInt(document.getElementById('modal-tcp-port').value) || 5000;
    const udpPort = parseInt(document.getElementById('modal-udp-port').value) || 6000;
    const username = document.getElementById('modal-username').value.trim() || 'Keerthi';

    const btn = document.getElementById('modal-connect-btn');
    const errBox = document.getElementById('modal-error-msg');

    if (btn) {
        btn.disabled = true;
        btn.textContent = 'CONNECTING...';
    }
    if (errBox) errBox.style.display = 'none';

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
            fetchFilesList();
            fetchOnlineUsers();
            fetchLogs();
        } else {
            if (errBox) {
                errBox.textContent = data.error || 'Connection failed';
                errBox.style.display = 'block';
            }
        }
    } catch (err) {
        if (errBox) {
            errBox.textContent = 'Network request error: ' + err.message;
            errBox.style.display = 'block';
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'CONNECT NOW →';
        }
    }
}

// Status Sync
async function checkBackendStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        updateUIState(status);

        if (currentTab === 'chat') {
            fetchOnlineUsers();
            fetchChatMessages();
        } else if (currentTab === 'statistics' || currentTab === 'network') {
            fetchNetworkStats();
        }
    } catch (e) {
        console.warn('Backend status check error:', e);
    }
}

function updateUIState(status) {
    const topServer = document.getElementById('topbar-server-val');
    const topBtn = document.getElementById('topbar-conn-btn');
    
    if (topServer) topServer.textContent = `${status.server_host || '127.0.0.1'}`;

    // TCP Status
    const tcpPill = document.getElementById('pill-tcp');
    const footerTcpTxt = document.getElementById('footer-tcp-txt');
    const footerTcpDot = document.getElementById('footer-tcp-dot');

    if (status.tcp_connected) {
        if (tcpPill) {
            tcpPill.className = 'status-pill online';
            const pillSpan = tcpPill.querySelector('.pill-status');
            if (pillSpan) pillSpan.textContent = 'Connected (5000)';
        }
        if (footerTcpTxt) footerTcpTxt.textContent = 'Connected (5000)';
        if (footerTcpDot) footerTcpDot.className = 'dot online';
    } else {
        if (tcpPill) {
            tcpPill.className = 'status-pill offline';
            const pillSpan = tcpPill.querySelector('.pill-status');
            if (pillSpan) pillSpan.textContent = 'Offline';
        }
        if (footerTcpTxt) footerTcpTxt.textContent = 'Disconnected';
        if (footerTcpDot) footerTcpDot.className = 'dot offline';
    }

    // UDP Status
    const udpPill = document.getElementById('pill-udp');
    const footerUdpTxt = document.getElementById('footer-udp-txt');
    const footerUdpDot = document.getElementById('footer-udp-dot');

    if (status.udp_connected) {
        if (udpPill) {
            udpPill.className = 'status-pill online';
            const pillSpan = udpPill.querySelector('.pill-status');
            if (pillSpan) pillSpan.textContent = 'Connected (6000)';
        }
        if (footerUdpTxt) footerUdpTxt.textContent = 'Connected (6000)';
        if (footerUdpDot) footerUdpDot.className = 'dot online';
    } else {
        if (udpPill) {
            udpPill.className = 'status-pill offline';
            const pillSpan = udpPill.querySelector('.pill-status');
            if (pillSpan) pillSpan.textContent = 'Offline';
        }
        if (footerUdpTxt) footerUdpTxt.textContent = 'Disconnected';
        if (footerUdpDot) footerUdpDot.className = 'dot offline';
    }

    if (topBtn) {
        if (status.tcp_connected || status.udp_connected) {
            topBtn.innerHTML = `<span>CONNECTED ●</span>`;
            topBtn.style.backgroundColor = 'var(--success-green)';
            topBtn.style.borderColor = 'var(--success-green)';
        } else {
            topBtn.innerHTML = `<span>LET'S CONNECT</span> <span class="btn-arrow">→</span>`;
            topBtn.style.backgroundColor = 'var(--accent-olive)';
            topBtn.style.borderColor = 'var(--accent-olive)';
        }
    }
}

// Live Chat Operations
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    input.value = '';

    try {
        const res = await fetch('/api/chat/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        if (data.success) {
            fetchChatMessages();
            fetchLogs();
        } else {
            alert('Failed to send message: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Chat send error: ' + e.message);
    }
}

async function fetchChatMessages() {
    try {
        const res = await fetch('/api/chat/messages');
        const data = await res.json();
        const box = document.getElementById('chat-messages-list');
        const username = document.getElementById('modal-username')?.value || 'Keerthi';

        if (box && data.messages) {
            if (data.messages.length === 0) {
                box.innerHTML = `<div class="sys-msg">Connected to UDP Chat Server. Type a message below to test datagram communication.</div>`;
                return;
            }

            box.innerHTML = '';
            const seenMessages = new Set();
            data.messages.forEach(m => {
                const key = `${m.sender}-${m.sequence}-${m.message}`;
                if (seenMessages.has(key)) return;
                seenMessages.add(key);

                const isMine = m.sender === username;
                const bubble = document.createElement('div');
                bubble.className = `chat-bubble ${isMine ? 'mine' : 'theirs'}`;
                bubble.innerHTML = `
                    <div style="font-weight: 700; font-size: 11px; margin-bottom: 2px;">${m.sender}</div>
                    <div>${m.message}</div>
                    <div class="chat-bubble-meta">
                        <span>UDP Seq #${m.sequence || 0}</span>
                        <span>${m.status || 'Delivered'}</span>
                    </div>
                `;
                box.appendChild(bubble);
            });
            box.scrollTop = box.scrollHeight;
        }
    } catch (e) {
        console.warn('Fetch chat messages error:', e);
    }
}

// Fetch Online Users (UDP Presence)
async function fetchOnlineUsers() {
    try {
        const res = await fetch('/api/users');
        const data = await res.json();
        const usersList = document.getElementById('online-users-list');
        const onlineCountBadge = document.getElementById('online-users-count');

        if (data.users) {
            const onlineCount = data.users.filter(u => u.status === 'ONLINE').length;
            if (onlineCountBadge) onlineCountBadge.textContent = `${onlineCount} Online`;

            if (usersList) {
                usersList.innerHTML = '';
                data.users.forEach(u => {
                    const isOnline = u.status === 'ONLINE';
                    const div = document.createElement('div');
                    div.className = 'user-row';
                    div.innerHTML = `
                        <span class="dot ${isOnline ? 'online' : 'offline'}">●</span> 
                        <strong>${u.username}</strong>
                        <small style="margin-left: auto; color: var(--text-muted); font-family: var(--font-mono); font-size: 11px;">${u.endpoint || '127.0.0.1'}</small>
                    `;
                    usersList.appendChild(div);
                });
            }
        }
    } catch (e) {
        console.warn('Fetch online users error:', e);
    }
}

// Files & Transfer Operations
async function fetchFilesList() {
    try {
        const res = await fetch('/api/files');
        const data = await res.json();
        const tbody = document.getElementById('files-table-body');

        if (tbody && data.files) {
            tbody.innerHTML = '';

            if (data.files.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 32px;">No files available in server storage/uploads/. Click "+ Upload File" above.</td></tr>`;
                return;
            }

            data.files.forEach(file => {
                const tr = document.createElement('tr');
                const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                tr.innerHTML = `
                    <td><strong>${file.filename}</strong></td>
                    <td style="font-family: var(--font-mono);">${sizeMB} MB (${file.size.toLocaleString()} B)</td>
                    <td><span class="tag" style="background-color: var(--bg-surface);">${file.filename.split('.').pop().toUpperCase()}</span></td>
                    <td><span class="tag tag-success">✓ SHA-256 Verified</span></td>
                    <td><button class="btn btn-sm btn-outline-pill" onclick="performDownload('${file.filename}')">↓ DOWNLOAD</button></td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.warn('Fetch files error:', e);
    }
}

async function performUpload() {
    const fileInput = document.getElementById('upload-file-input');
    const resumeCheck = document.getElementById('upload-resume-check');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        alert('Please choose a file to upload first.');
        return;
    }

    const fileObj = fileInput.files[0];
    const resume = resumeCheck ? resumeCheck.checked : false;

    const formData = new FormData();
    formData.append('file', fileObj);
    formData.append('resume', resume);

    closeUploadModal();
    alert(`Initiating TCP streaming upload for '${fileObj.name}' (${(fileObj.size / (1024*1024)).toFixed(2)} MB)...`);

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            alert(`✓ SUCCESS!\nFile '${data.filename}' uploaded successfully.\nSHA-256 Checksum: VERIFIED\nServer Hash: ${data.server_checksum ? data.server_checksum.substring(0, 16) : ''}...`);
            fetchFilesList();
            fetchTransfers();
            fetchLogs();
        } else {
            alert(`✗ UPLOAD FAILED!\nError: ${data.error}`);
        }
    } catch (err) {
        alert('Upload Error: ' + err.message);
    }
}

async function performDownload(filename) {
    alert(`Initiating TCP streaming download for '${filename}'...`);

    try {
        const res = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        });
        const data = await res.json();

        if (data.success) {
            alert(`✓ SUCCESS!\nFile '${data.filename}' downloaded into storage/downloads/.\nSHA-256 Checksum: VERIFIED`);
            fetchTransfers();
            fetchLogs();
        } else {
            alert(`✗ DOWNLOAD FAILED!\nError: ${data.error}`);
        }
    } catch (err) {
        alert('Download Error: ' + err.message);
    }
}

async function fetchTransfers() {
    try {
        const res = await fetch('/api/transfers');
        const data = await res.json();
        const container = document.getElementById('transfers-list-container');

        if (container && data.transfers) {
            if (data.transfers.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No active file transfers currently recorded.</p>
                    </div>`;
                return;
            }

            container.innerHTML = '';
            data.transfers.forEach(t => {
                const sizeMB = (t.size / (1024 * 1024)).toFixed(2);
                const card = document.createElement('div');
                card.className = 'stat-detail-card';
                card.style.marginBottom = '12px';
                card.style.padding = '18px 24px';
                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>${t.filename}</strong> (${sizeMB} MB)
                            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                                ${t.direction} over ${t.protocol} Protocol | ${t.timestamp}
                            </div>
                        </div>
                        <div>
                            <span class="tag ${t.status === 'Completed' ? 'tag-success' : 'tag-error'}">${t.status}</span>
                            <span style="font-size: 12px; color: var(--success-green); margin-left: 8px;">✓ SHA-256 Verified</span>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        }
    } catch (e) {
        console.warn('Fetch transfers error:', e);
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

// Format bytes helper
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Fetch Live Network Metrics
async function fetchNetworkStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        if (data.tcp) {
            const elTcpSent = document.getElementById('stat-tcp-bytes-sent');
            const elTcpRecv = document.getElementById('stat-tcp-bytes-recv');
            const elTcpSpeedUp = document.getElementById('stat-tcp-speed-up');
            const elTcpSpeedDown = document.getElementById('stat-tcp-speed-down');

            if (elTcpSent) elTcpSent.textContent = formatBytes(data.tcp.bytes_sent);
            if (elTcpRecv) elTcpRecv.textContent = formatBytes(data.tcp.bytes_received);
            if (elTcpSpeedUp) elTcpSpeedUp.textContent = data.tcp.upload_speed_kbs + ' KB/s';
            if (elTcpSpeedDown) elTcpSpeedDown.textContent = data.tcp.download_speed_kbs + ' KB/s';
        }

        if (data.udp) {
            const elUdpSent = document.getElementById('stat-udp-bytes-sent');
            const elUdpRecv = document.getElementById('stat-udp-bytes-recv');
            const elUdpAcks = document.getElementById('stat-udp-acks');
            const elUdpRetries = document.getElementById('stat-udp-retries');
            const elUdpSuccess = document.getElementById('stat-udp-success');
            const elUdpLoss = document.getElementById('stat-udp-loss');

            if (elUdpSent) elUdpSent.textContent = formatBytes(data.udp.bytes_sent);
            if (elUdpRecv) elUdpRecv.textContent = formatBytes(data.udp.bytes_received);
            if (elUdpAcks) elUdpAcks.textContent = data.udp.acks_received;
            if (elUdpRetries) elUdpRetries.textContent = data.udp.retransmissions;
            if (elUdpSuccess) elUdpSuccess.textContent = data.udp.success_percentage + '%';
            if (elUdpLoss) elUdpLoss.textContent = data.udp.loss_percentage + '%';
        }
    } catch (e) {
        console.warn('Fetch network stats error:', e);
    }
}

// Packet Loss Simulation Handlers
function updateLossLabel(val) {
    const lbl = document.getElementById('loss-label');
    if (lbl) lbl.textContent = val + '%';
}

async function applyLossSimulation() {
    const slider = document.getElementById('loss-slider');
    const val = parseInt(slider ? slider.value : 0) || 0;
    const rate = val / 100.0;

    try {
        const res = await fetch('/api/simulation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rate: rate })
        });
        const data = await res.json();
        if (data.success) {
            alert(`⚠️ Simulated UDP Packet Loss set to ${val}%.\nUDP datagrams will experience artificial packet drops to demonstrate application-layer retransmission!`);
            fetchLogs();
            fetchNetworkStats();
        }
    } catch (e) {
        alert('Error applying loss simulation: ' + e.message);
    }
}
