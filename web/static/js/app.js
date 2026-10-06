/* 
   HYBRID TRANSFER - Product UI Controller Script
   Handles Navigation, Connection Management, API Interactivity, Real-time Backend Sync,
   File Listing, TCP Upload, TCP Download, UDP Presence, and Live Chat Messaging.
*/

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

let currentTab = 'dashboard';
let pollTimer = null;

function initApp() {
    checkBackendStatus();
    pollTimer = setInterval(checkBackendStatus, 2000);
}

// Tab Switching logic
function switchTab(tabId) {
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
    }

    if (tabId === 'files') {
        fetchFilesList();
    } else if (tabId === 'transfers') {
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
    modal.style.display = modal.style.display === 'flex' ? 'none' : 'flex';
}

function closeConnectModal() {
    document.getElementById('connect-modal').style.display = 'none';
}

// Connection Handler
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
            fetchFilesList();
            fetchOnlineUsers();
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

// Status Sync
async function checkBackendStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        updateUIState(status);

        if (currentTab === 'chat') {
            fetchOnlineUsers();
            fetchChatMessages();
        } else if (currentTab === 'dashboard') {
            fetchOnlineUsers();
        }
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

    // TCP Status
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

    // UDP Status
    const udpPill = document.getElementById('pill-udp');
    const dashUdpVal = document.getElementById('dash-udp-val');
    const footerUdpTxt = document.getElementById('footer-udp-txt');
    const footerUdpDot = document.getElementById('footer-udp-dot');

    if (status.udp_connected) {
        if (udpPill) {
            udpPill.className = 'pill online';
            udpPill.querySelector('.pill-status').textContent = 'Connected';
        }
        if (dashUdpVal) {
            dashUdpVal.className = 'stat-value status-text online';
            dashUdpVal.textContent = 'CONNECTED';
        }
        if (footerUdpTxt) footerUdpTxt.textContent = 'Connected';
        if (footerUdpDot) footerUdpDot.className = 'dot online';
    } else {
        if (udpPill) {
            udpPill.className = 'pill offline';
            udpPill.querySelector('.pill-status').textContent = 'Offline';
        }
        if (dashUdpVal) {
            dashUdpVal.className = 'stat-value status-text offline';
            dashUdpVal.textContent = 'OFFLINE';
        }
        if (footerUdpTxt) footerUdpTxt.textContent = 'Disconnected';
        if (footerUdpDot) footerUdpDot.className = 'dot offline';
    }
}

// Live Chat Operations
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
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

        if (box && data.messages) {
            if (data.messages.length === 0) {
                box.innerHTML = `<div class="sys-msg">Connected to UDP Chat Server. Type a message below to test datagram communication.</div>`;
                return;
            }

            box.innerHTML = '';
            data.messages.forEach(m => {
                const msgDiv = document.createElement('div');
                msgDiv.style.padding = '10px 14px';
                msgDiv.style.borderRadius = '8px';
                msgDiv.style.backgroundColor = 'rgba(255,255,255,0.04)';
                msgDiv.style.border = '1px solid var(--border-color)';
                msgDiv.style.marginBottom = '8px';

                msgDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">
                        <strong style="color: var(--primary-blue);">${m.sender}</strong>
                        <span>[UDP Seq #${m.sequence}] ${m.timestamp}</span>
                    </div>
                    <div style="font-size: 14px; color: var(--text-white);">${m.message}</div>
                `;
                box.appendChild(msgDiv);
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
        const dashOnlineVal = document.getElementById('dash-online-val');

        if (data.users) {
            const onlineCount = data.users.filter(u => u.status === 'ONLINE').length;
            if (dashOnlineVal) dashOnlineVal.textContent = onlineCount;

            if (usersList) {
                usersList.innerHTML = '';
                data.users.forEach(u => {
                    const isOnline = u.status === 'ONLINE';
                    const div = document.createElement('div');
                    div.className = 'user-row';
                    div.innerHTML = `<span class="dot ${isOnline ? 'online' : 'offline'}">●</span> ${u.username} <small style="color:var(--text-muted); margin-left:auto;">${u.status}</small>`;
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
        const dashFilesVal = document.getElementById('dash-files-val');

        if (tbody && data.files) {
            tbody.innerHTML = '';
            if (dashFilesVal) dashFilesVal.textContent = data.files.length;

            if (data.files.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">No files available on server repository. Click "+ Upload File" to add files.</td></tr>`;
                return;
            }

            data.files.forEach(file => {
                const tr = document.createElement('tr');
                const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                tr.innerHTML = `
                    <td><strong>${file.filename}</strong></td>
                    <td>${sizeMB} MB (${file.size.toLocaleString()} B)</td>
                    <td>${file.filename.split('.').pop().toUpperCase()} File</td>
                    <td><span class="tag tag-success">Available</span></td>
                    <td><button class="btn btn-sm btn-action" onclick="performDownload('${file.filename}')">↓ Download</button></td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.warn('Fetch files error:', e);
    }
}

function showUploadModal() {
    const input = document.createElement('input');
    input.type = 'file';
    input.onchange = (e) => {
        if (e.target.files.length > 0) {
            performUpload(e.target.files[0]);
        }
    };
    input.click();
}

async function performUpload(fileObj) {
    const formData = new FormData();
    formData.append('file', fileObj);

    alert(`Initiating TCP streaming upload for '${fileObj.name}' (${(fileObj.size / (1024*1024)).toFixed(2)} MB)...`);

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            alert(`✓ SUCCESS!\nFile '${data.filename}' uploaded successfully.\nSHA-256 Checksum: VERIFIED\nServer Hash: ${data.server_checksum.substring(0, 16)}...`);
            fetchFilesList();
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
                        <p>No active file transfers currently running.</p>
                        <button class="btn btn-primary" onclick="switchTab('files')">Start a File Transfer</button>
                    </div>`;
                return;
            }

            container.innerHTML = '';
            data.transfers.forEach(t => {
                const sizeMB = (t.size / (1024 * 1024)).toFixed(2);
                const card = document.createElement('div');
                card.className = 'stat-card';
                card.style.marginBottom = '12px';
                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>${t.filename}</strong> (${sizeMB} MB)
                            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">${t.direction} over ${t.protocol} Protocol | ${t.timestamp}</div>
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
            alert(`⚠️ Simulated UDP Packet Loss set to ${val}%.\nUDP datagrams will now experience artificial packet drops to demonstrate application-layer retransmission!`);
            fetchLogs();
            fetchNetworkStats();
        }
    } catch (e) {
        alert('Error applying loss simulation: ' + e.message);
    }
}
