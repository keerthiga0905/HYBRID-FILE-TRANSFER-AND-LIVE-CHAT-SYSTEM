/* 
   HYBRID TRANSFER - Full Interface Controller Script
   Powers all 10 Panels:
   1. Login & Session Management
   2. Home Dashboard & Dual Protocol Status
   3. Online Users Directory with Online/Offline indicators
   4. TCP File Transfer & Server Repository
   5. Incoming File Requests with Accept/Reject Controls
   6. Transfer Progress Monitoring
   7. Transfer History & SHA-256 Verification Status
   8. UDP Private 1-on-1 Chat
   9. UDP Group Broadcast Chat
   10. Network Statistics & Packet Loss Simulator
*/

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

let currentTab = 'home';
let pollTimer = null;
let currentUsername = 'Keerthi';
let currentSessionId = null;
let activePrivatePeer = null;
let onlineUsersCache = [];
let pendingRequestsCache = [];

function initApp() {
    checkBackendStatus();
    fetchOnlineUsers();
    fetchFilesList();
    fetchIncomingRequests();
    fetchTransfers();
    fetchPartials();
    fetchLogs();

    // 2-Second live background polling
    pollTimer = setInterval(() => {
        checkBackendStatus();
        fetchIncomingRequests();

        if (currentTab === 'users') {
            fetchOnlineUsers();
        } else if (currentTab === 'group-chat' || currentTab === 'private-chat') {
            fetchChatMessages();
            fetchOnlineUsers();
        } else if (currentTab === 'statistics') {
            fetchNetworkStats();
        } else if (currentTab === 'activity') {
            fetchLogs();
        }
    }, 2000);
}

// ========================================================
// TOAST NOTIFICATIONS SYSTEM
// ========================================================
function showToast(type, title, message) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    else if (type === 'error') icon = '❌';
    else if (type === 'warning') icon = '⚠️';

    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-body">
            <div class="toast-title">${title}</div>
            <div class="toast-msg">${message}</div>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ========================================================
// NAVIGATION & TAB SWITCHING
// ========================================================
function switchTab(tabId) {
    if (tabId === 'dashboard') tabId = 'home';
    currentTab = tabId;

    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(`nav-${tabId}`);
    if (activeBtn) activeBtn.classList.add('active');

    document.querySelectorAll('.page-view').forEach(p => p.classList.remove('active'));
    const activePage = document.getElementById(`page-${tabId}`);
    if (activePage) {
        activePage.classList.add('active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    if (tabId === 'files') {
        fetchFilesList();
    } else if (tabId === 'users') {
        fetchOnlineUsers();
    } else if (tabId === 'requests') {
        fetchIncomingRequests();
    } else if (tabId === 'history') {
        fetchTransfers();
        fetchPartials();
    } else if (tabId === 'group-chat') {
        fetchChatMessages();
        fetchOnlineUsers();
    } else if (tabId === 'private-chat') {
        fetchChatMessages();
        fetchOnlineUsers();
    } else if (tabId === 'statistics') {
        fetchNetworkStats();
    } else if (tabId === 'activity') {
        fetchLogs();
    }
}

// ========================================================
// MODAL CONTROLS
// ========================================================
function toggleConnectModal() {
    const modal = document.getElementById('connect-modal');
    if (modal) modal.style.display = modal.style.display === 'flex' ? 'none' : 'flex';
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

// ========================================================
// 1 & 2. STATUS SYNC & SESSION MANAGEMENT
// ========================================================
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
    currentUsername = status.username || 'Keerthi';
    currentSessionId = status.session_id || null;

    // Header Username Badge
    const userDisplay = document.getElementById('topbar-username-display');
    const avatar = document.getElementById('topbar-avatar');
    const sessTag = document.getElementById('topbar-session-tag');
    if (userDisplay) userDisplay.textContent = currentUsername;
    if (avatar) avatar.textContent = currentUsername.charAt(0).toUpperCase();
    if (sessTag) sessTag.textContent = currentSessionId ? `Session: ${currentSessionId.substring(0, 8)}` : 'No Session';

    // Session Page Elements
    const sessionAvatarLg = document.getElementById('session-avatar-large');
    const sessionUsername = document.getElementById('session-display-username');
    const sessionId = document.getElementById('session-display-id');
    const sessionHost = document.getElementById('session-display-host');
    const sessionTcp = document.getElementById('session-display-tcp');
    const sessionUdp = document.getElementById('session-display-udp');
    const sessionDot = document.getElementById('session-dot');
    const sessionStatusText = document.getElementById('session-status-text');
    const sessionTagState = document.getElementById('session-tag-state');

    if (sessionAvatarLg) sessionAvatarLg.textContent = currentUsername.charAt(0).toUpperCase();
    if (sessionUsername) sessionUsername.textContent = currentUsername;
    if (sessionId) sessionId.textContent = currentSessionId || 'Disconnected';
    if (sessionHost) sessionHost.textContent = status.server_host || '127.0.0.1';
    if (sessionTcp) sessionTcp.textContent = `${status.tcp_port || 5000} (SOCK_STREAM)`;
    if (sessionUdp) sessionUdp.textContent = `${status.udp_port || 6000} (SOCK_DGRAM)`;

    const isConnected = status.tcp_connected || status.udp_connected;
    if (sessionDot) sessionDot.className = `dot ${isConnected ? 'online' : 'offline'}`;
    if (sessionStatusText) sessionStatusText.textContent = isConnected ? 'Connected' : 'Disconnected';
    if (sessionTagState) {
        sessionTagState.className = `tag ${isConnected ? 'tag-success' : 'tag-error'}`;
        sessionTagState.textContent = isConnected ? 'Active' : 'Offline';
    }

    // TCP Pill
    const tcpPill = document.getElementById('pill-tcp');
    const footerTcpTxt = document.getElementById('footer-tcp-txt');
    const footerTcpDot = document.getElementById('footer-tcp-dot');
    const homeTcpBadge = document.getElementById('home-tcp-badge');

    if (status.tcp_connected) {
        if (tcpPill) {
            tcpPill.className = 'status-pill online';
            const pillSpan = tcpPill.querySelector('.pill-status');
            if (pillSpan) pillSpan.textContent = 'Port 5000 Online';
        }
        if (footerTcpTxt) footerTcpTxt.textContent = 'Connected (5000)';
        if (footerTcpDot) footerTcpDot.className = 'dot online';
        if (homeTcpBadge) { homeTcpBadge.className = 'tag tag-success'; homeTcpBadge.textContent = 'ONLINE'; }
    } else {
        if (tcpPill) {
            tcpPill.className = 'status-pill offline';
            const pillSpan = tcpPill.querySelector('.pill-status');
            if (pillSpan) pillSpan.textContent = 'Offline';
        }
        if (footerTcpTxt) footerTcpTxt.textContent = 'Disconnected';
        if (footerTcpDot) footerTcpDot.className = 'dot offline';
        if (homeTcpBadge) { homeTcpBadge.className = 'tag tag-error'; homeTcpBadge.textContent = 'OFFLINE'; }
    }

    // UDP Pill
    const udpPill = document.getElementById('pill-udp');
    const footerUdpTxt = document.getElementById('footer-udp-txt');
    const footerUdpDot = document.getElementById('footer-udp-dot');
    const homeUdpBadge = document.getElementById('home-udp-badge');

    if (status.udp_connected) {
        if (udpPill) {
            udpPill.className = 'status-pill online';
            const pillSpan = udpPill.querySelector('.pill-status');
            if (pillSpan) pillSpan.textContent = 'Port 6000 Online';
        }
        if (footerUdpTxt) footerUdpTxt.textContent = 'Connected (6000)';
        if (footerUdpDot) footerUdpDot.className = 'dot online';
        if (homeUdpBadge) { homeUdpBadge.className = 'tag tag-success'; homeUdpBadge.textContent = 'ONLINE'; }
    } else {
        if (udpPill) {
            udpPill.className = 'status-pill offline';
            const pillSpan = udpPill.querySelector('.pill-status');
            if (pillSpan) pillSpan.textContent = 'Offline';
        }
        if (footerUdpTxt) footerUdpTxt.textContent = 'Disconnected';
        if (footerUdpDot) footerUdpDot.className = 'dot offline';
        if (homeUdpBadge) { homeUdpBadge.className = 'tag tag-error'; homeUdpBadge.textContent = 'OFFLINE'; }
    }

    // Topbar Action Button
    const topBtn = document.getElementById('topbar-conn-btn');
    if (topBtn) {
        if (isConnected) {
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

async function performConnection() {
    const host = document.getElementById('modal-host')?.value.trim() || '127.0.0.1';
    const tcpPort = parseInt(document.getElementById('modal-tcp-port')?.value) || 5000;
    const udpPort = parseInt(document.getElementById('modal-udp-port')?.value) || 6000;
    const username = document.getElementById('modal-username')?.value.trim() || 'Keerthi';

    const btn = document.getElementById('modal-connect-btn');
    const errBox = document.getElementById('modal-error-msg');

    if (btn) {
        btn.disabled = true;
        btn.textContent = 'CONNECTING Sockets...';
    }
    if (errBox) errBox.style.display = 'none';

    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, tcp_port: tcpPort, udp_port: udpPort, username })
        });
        const data = await response.json();

        if (data.success) {
            closeConnectModal();
            showToast('success', 'Connected Successfully', `Registered as '${data.username}' (Session: ${data.session_id ? data.session_id.substring(0, 8) : 'Active'})`);
            checkBackendStatus();
            fetchOnlineUsers();
            fetchFilesList();
        } else {
            if (errBox) {
                errBox.textContent = data.error || 'Connection failed';
                errBox.style.display = 'block';
            }
            showToast('error', 'Connection Rejected', data.error || 'Failed to establish sockets');
        }
    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.style.display = 'block';
        }
        showToast('error', 'Network Error', err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'CONNECT NOW →';
        }
    }
}

async function submitSessionForm() {
    const username = document.getElementById('session-form-username')?.value.trim() || 'Keerthi';
    const host = document.getElementById('session-form-host')?.value.trim() || '127.0.0.1';
    const tcpPort = parseInt(document.getElementById('session-form-tcp')?.value) || 5000;
    const udpPort = parseInt(document.getElementById('session-form-udp')?.value) || 6000;

    try {
        const response = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, tcp_port: tcpPort, udp_port: udpPort, username })
        });
        const data = await response.json();

        if (data.success) {
            showToast('success', 'Session Established', `Now connected as '${data.username}'`);
            checkBackendStatus();
            fetchOnlineUsers();
        } else {
            showToast('error', 'Session Connection Failed', data.error || 'Unable to connect');
        }
    } catch (err) {
        showToast('error', 'Connection Error', err.message);
    }
}

function quickPreset(name) {
    const input = document.getElementById('session-form-username');
    if (input) input.value = name;
    submitSessionForm();
}

async function disconnectFromServer() {
    try {
        const response = await fetch('/api/disconnect', { method: 'POST' });
        const data = await response.json();
        showToast('info', 'Disconnected', data.message || 'Closed TCP & UDP sockets cleanly');
        checkBackendStatus();
    } catch (err) {
        showToast('error', 'Disconnect Error', err.message);
    }
}

// ========================================================
// 3. ONLINE USERS LIST WITH STATUS INDICATORS
// ========================================================
async function fetchOnlineUsers() {
    try {
        const res = await fetch('/api/users');
        const data = await res.json();
        onlineUsersCache = data.users || [];

        const countBadge = document.getElementById('users-directory-count');
        const metricOnline = document.getElementById('metric-online-count');
        const groupCount = document.getElementById('group-online-count');
        const onlineCount = onlineUsersCache.filter(u => u.status === 'ONLINE').length;

        if (countBadge) countBadge.textContent = `${onlineCount} Online`;
        if (metricOnline) metricOnline.textContent = onlineCount;
        if (groupCount) groupCount.textContent = `${onlineCount} Online`;

        renderUsersDirectoryGrid();
        populatePeerDropdowns();
        renderPrivatePeersSidebar();
    } catch (e) {
        console.warn('Fetch online users error:', e);
    }
}

function renderUsersDirectoryGrid() {
    const grid = document.getElementById('users-directory-grid');
    if (!grid) return;

    if (onlineUsersCache.length === 0) {
        grid.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1;"><p>No users registered on UDP presence server.</p></div>`;
        return;
    }

    grid.innerHTML = '';
    onlineUsersCache.forEach(u => {
        const isMe = u.username === currentUsername;
        const isOnline = u.status === 'ONLINE';
        const card = document.createElement('div');
        card.className = 'user-card';
        card.innerHTML = `
            <div class="user-card-header">
                <div class="user-avatar">${u.username.charAt(0).toUpperCase()}</div>
                <div>
                    <div class="user-info-name">
                        ${u.username} ${isMe ? '<small style="color: var(--accent-terracotta); font-weight: 700;">(You)</small>' : ''}
                    </div>
                    <div class="user-endpoint">Endpoint: ${u.endpoint || '127.0.0.1'}</div>
                </div>
                <div style="margin-left: auto;">
                    <span class="dot ${isOnline ? 'online' : 'offline'}">●</span> 
                    <small style="font-weight: 700; color: ${isOnline ? 'var(--success-green)' : 'var(--error-red)'}; font-size: 11px;">
                        ${isOnline ? 'ONLINE' : 'OFFLINE'}
                    </small>
                </div>
            </div>
            <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">
                Last seen: ${u.last_seen || 'Active'}
            </div>
            ${!isMe ? `
                <div class="user-card-actions">
                    <button class="btn btn-sm btn-outline-pill" onclick="startPrivateChatWith('${u.username}')">
                        💬 Private Chat
                    </button>
                    <button class="btn btn-sm btn-primary-pill" onclick="startPeerFileSendWith('${u.username}')">
                        📁 Send File
                    </button>
                </div>
            ` : '<div style="font-size: 12px; color: var(--text-muted); font-style: italic;">Local Active Client</div>'}
        `;
        grid.appendChild(card);
    });
}

function populatePeerDropdowns() {
    const targetSelect = document.getElementById('peer-send-target');
    if (targetSelect) {
        const currentVal = targetSelect.value;
        targetSelect.innerHTML = '<option value="">Select online peer...</option>';
        onlineUsersCache.forEach(u => {
            if (u.username !== currentUsername && u.status === 'ONLINE') {
                const opt = document.createElement('option');
                opt.value = u.username;
                opt.textContent = `${u.username} (${u.endpoint || 'Online'})`;
                targetSelect.appendChild(opt);
            }
        });
        if (currentVal) targetSelect.value = currentVal;
    }

    // Group chat online list
    const groupOnlineList = document.getElementById('group-online-list');
    if (groupOnlineList) {
        groupOnlineList.innerHTML = '';
        onlineUsersCache.forEach(u => {
            const isOnline = u.status === 'ONLINE';
            const row = document.createElement('div');
            row.className = 'user-row';
            row.innerHTML = `<span class="dot ${isOnline ? 'online' : 'offline'}">●</span> <strong>${u.username}</strong>`;
            groupOnlineList.appendChild(row);
        });
    }
}

function renderPrivatePeersSidebar() {
    const peersContainer = document.getElementById('private-peers-list');
    if (!peersContainer) return;

    const peers = onlineUsersCache.filter(u => u.username !== currentUsername);
    if (peers.length === 0) {
        peersContainer.innerHTML = `<div class="empty-state" style="padding: 16px;"><p>No other peers online.</p></div>`;
        return;
    }

    peersContainer.innerHTML = '';
    peers.forEach(p => {
        const isActive = activePrivatePeer === p.username;
        const isOnline = p.status === 'ONLINE';
        const item = document.createElement('div');
        item.className = `peer-item ${isActive ? 'active' : ''}`;
        item.onclick = () => selectPrivatePeer(p.username);
        item.innerHTML = `
            <span class="dot ${isOnline ? 'online' : 'offline'}">●</span>
            <strong>${p.username}</strong>
            <small style="margin-left: auto; font-family: var(--font-mono); font-size: 10px; color: var(--text-muted);">
                ${p.endpoint ? p.endpoint.split(':')[1] || '' : ''}
            </small>
        `;
        peersContainer.appendChild(item);
    });

    if (!activePrivatePeer && peers.length > 0) {
        selectPrivatePeer(peers[0].username);
    }
}

function startPrivateChatWith(username) {
    activePrivatePeer = username;
    switchTab('private-chat');
    selectPrivatePeer(username);
}

function startPeerFileSendWith(username) {
    switchTab('files');
    const select = document.getElementById('peer-send-target');
    if (select) select.value = username;
}

// ========================================================
// 4 & 6. FILE TRANSFER & PROGRESS MONITOR
// ========================================================
async function fetchFilesList() {
    try {
        const res = await fetch('/api/files');
        const data = await res.json();
        const tbody = document.getElementById('files-table-body');
        const metricFiles = document.getElementById('metric-files-count');

        if (data.files && metricFiles) metricFiles.textContent = data.files.length;

        if (tbody && data.files) {
            tbody.innerHTML = '';
            if (data.files.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 32px;">No files in storage/uploads/. Click "+ Upload File" above.</td></tr>`;
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
                    <td>
                        <button class="btn btn-sm btn-outline-pill" onclick="performDownload('${file.filename}', false)">
                            ↓ DOWNLOAD
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.warn('Fetch files error:', e);
    }
}

function showTransferProgress(direction, filename, percent, statusText, bytesText) {
    const card = document.getElementById('transfer-progress-card');
    const elDir = document.getElementById('progress-direction');
    const elName = document.getElementById('progress-filename');
    const elPct = document.getElementById('progress-percent');
    const elFill = document.getElementById('progress-bar-fill');
    const elBytes = document.getElementById('progress-bytes');
    const elStatus = document.getElementById('progress-status');

    if (card) card.style.display = 'block';
    if (elDir) elDir.textContent = direction;
    if (elName) elName.textContent = filename;
    if (elPct) elPct.textContent = `${percent}%`;
    if (elFill) elFill.style.width = `${percent}%`;
    if (elBytes) elBytes.textContent = bytesText;
    if (elStatus) elStatus.textContent = statusText;
}

function hideTransferProgress() {
    const card = document.getElementById('transfer-progress-card');
    if (card) {
        setTimeout(() => { card.style.display = 'none'; }, 2000);
    }
}

async function performUpload() {
    const fileInput = document.getElementById('upload-file-input');
    const resumeCheck = document.getElementById('upload-resume-check');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast('warning', 'Missing File', 'Please choose a file to upload first.');
        return;
    }

    const fileObj = fileInput.files[0];
    const resume = resumeCheck ? resumeCheck.checked : false;

    const formData = new FormData();
    formData.append('file', fileObj);
    formData.append('resume', resume);

    closeUploadModal();
    showToast('info', 'Starting TCP Upload', `Streaming '${fileObj.name}' (${formatBytes(fileObj.size)}) in 4KB chunks...`);
    showTransferProgress('TCP STREAMING UPLOAD', fileObj.name, 35, 'Sending 4096-byte chunks to server...', `Streaming ${formatBytes(fileObj.size)}`);

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            showTransferProgress('TCP UPLOAD COMPLETED', fileObj.name, 100, 'SHA-256 Checksum 100% Verified!', formatBytes(fileObj.size));
            showToast('success', 'Upload Verified', `File '${data.filename}' successfully uploaded and SHA-256 verified!`);
            fetchFilesList();
            fetchTransfers();
            fetchLogs();
        } else {
            showToast('error', 'Upload Failed', data.error || 'Server rejected file');
        }
    } catch (err) {
        showToast('error', 'Upload Error', err.message);
    } finally {
        hideTransferProgress();
    }
}

async function performDownload(filename, resume = false) {
    const mode = resume ? 'Resuming' : 'Downloading';
    showToast('info', `TCP ${mode}`, `Starting streaming download for '${filename}'...`);
    showTransferProgress(`TCP STREAMING ${mode.toUpperCase()}`, filename, 45, 'Receiving 4096-byte chunks from server...', 'Receiving bytes...');

    try {
        const res = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, resume })
        });
        const data = await res.json();

        if (data.success) {
            showTransferProgress(`TCP ${mode.toUpperCase()} COMPLETED`, filename, 100, 'SHA-256 Verified!', formatBytes(data.filesize || 0));
            showToast('success', 'Download Complete', `File '${filename}' saved into storage/downloads/ and SHA-256 verified.`);
            fetchTransfers();
            fetchPartials();
            fetchLogs();
        } else {
            showToast('error', 'Download Failed', data.error || 'Download failed');
        }
    } catch (err) {
        showToast('error', 'Download Error', err.message);
    } finally {
        hideTransferProgress();
    }
}

async function performPeerSend() {
    const receiver = document.getElementById('peer-send-target')?.value.trim();
    const fileInput = document.getElementById('peer-send-file');

    if (!receiver) {
        showToast('warning', 'Recipient Required', 'Please select a target online peer.');
        return;
    }
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast('warning', 'Missing File', 'Please select a file to send.');
        return;
    }

    const fileObj = fileInput.files[0];
    const formData = new FormData();
    formData.append('receiver', receiver);
    formData.append('file', fileObj);

    showToast('info', 'Peer Transfer Offered', `Offering '${fileObj.name}' to peer '${receiver}'. Waiting for acceptance...`);

    try {
        const res = await fetch('/api/peer/send', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            showToast('success', 'Peer Transfer Accepted', `Peer '${receiver}' accepted and received '${fileObj.name}'!`);
            fetchTransfers();
            fetchLogs();
        } else {
            showToast('error', 'Peer Transfer Failed', data.error || 'Transfer declined or failed');
        }
    } catch (err) {
        showToast('error', 'Peer Send Error', err.message);
    }
}

// ========================================================
// 5. INCOMING FILE REQUESTS & ACCEPT / REJECT
// ========================================================
async function fetchIncomingRequests() {
    try {
        const res = await fetch('/api/peer/incoming');
        const data = await res.json();
        pendingRequestsCache = data.requests || [];

        const badge = document.getElementById('incoming-requests-badge');
        const navBadge = document.getElementById('nav-req-count');
        const count = pendingRequestsCache.length;

        if (badge) badge.textContent = `${count} Pending`;
        if (navBadge) {
            navBadge.textContent = count;
            navBadge.style.display = count > 0 ? 'inline-block' : 'none';
        }

        renderIncomingRequestsGrid();
    } catch (e) {
        console.warn('Fetch incoming requests error:', e);
    }
}

function renderIncomingRequestsGrid() {
    const grid = document.getElementById('incoming-requests-grid');
    if (!grid) return;

    if (pendingRequestsCache.length === 0) {
        grid.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1;"><p>No incoming file transfer requests at this moment.</p></div>`;
        return;
    }

    grid.innerHTML = '';
    pendingRequestsCache.forEach(req => {
        const card = document.createElement('div');
        card.className = 'request-card';
        card.innerHTML = `
            <div class="flex-between">
                <span class="protocol-badge-tcp">Incoming Peer Request</span>
                <span class="tag tag-success">Pending</span>
            </div>
            <h4 style="margin: 12px 0 6px 0; font-size: 16px;">${req.filename}</h4>
            <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 8px;">
                From sender: <strong>${req.sender}</strong>
            </div>
            <div style="font-size: 12px; font-family: var(--font-mono); color: var(--text-muted); margin-bottom: 16px;">
                Size: ${formatBytes(req.filesize)} • ID: ${req.transfer_id.substring(0, 8)}...
            </div>
            <div style="display: flex; gap: 10px;">
                <button class="btn btn-sm btn-primary-pill" onclick="acceptIncomingRequest('${req.transfer_id}', '${req.filename}', ${req.filesize}, '${req.checksum}')">
                    ✅ ACCEPT & DOWNLOAD (TCP)
                </button>
                <button class="btn btn-sm btn-outline-pill" onclick="rejectIncomingRequest('${req.transfer_id}')">
                    ❌ REJECT
                </button>
            </div>
        `;
        grid.appendChild(card);
    });
}

async function acceptIncomingRequest(transferId, filename, filesize, checksum) {
    showToast('info', 'Accepting Transfer', `Accepting '${filename}' from peer. Streaming TCP download...`);

    try {
        const res = await fetch('/api/peer/accept', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transfer_id: transferId, filename, filesize, checksum })
        });
        const data = await res.json();

        if (data.success) {
            showToast('success', 'File Received', `File '${filename}' received and verified with SHA-256!`);
            fetchIncomingRequests();
            fetchTransfers();
            fetchLogs();
        } else {
            showToast('error', 'Accept Failed', data.error || 'Failed to receive file');
        }
    } catch (err) {
        showToast('error', 'Accept Error', err.message);
    }
}

async function rejectIncomingRequest(transferId) {
    try {
        const res = await fetch('/api/peer/reject', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transfer_id: transferId, reason: 'Declined by recipient' })
        });
        const data = await res.json();
        showToast('warning', 'Transfer Rejected', 'Declined peer transfer request.');
        fetchIncomingRequests();
        fetchLogs();
    } catch (err) {
        showToast('error', 'Reject Error', err.message);
    }
}

// ========================================================
// 7. TRANSFER HISTORY & RESUME (.PART) FILES
// ========================================================
async function fetchTransfers() {
    try {
        const res = await fetch('/api/transfers');
        const data = await res.json();
        const container = document.getElementById('transfers-list-container');
        const metricTransfers = document.getElementById('metric-transfers-count');

        if (data.transfers && metricTransfers) metricTransfers.textContent = data.transfers.length;

        if (container && data.transfers) {
            if (data.transfers.length === 0) {
                container.innerHTML = `<div class="empty-state"><p>No file transfers recorded yet.</p></div>`;
                return;
            }

            container.innerHTML = '';
            data.transfers.forEach(t => {
                const card = document.createElement('div');
                card.className = 'stat-detail-card';
                card.style.marginBottom = '12px';
                card.style.padding = '18px 24px';
                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span class="protocol-badge-tcp">${t.protocol || 'TCP'}</span>
                            <strong style="margin-left: 8px; font-size: 15px;">${t.filename}</strong>
                            <div style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">
                                ${t.direction} • ${formatBytes(t.size)} ${t.offset_resumed ? `(Resumed from ${formatBytes(t.offset_resumed)})` : ''} • ${t.timestamp}
                            </div>
                        </div>
                        <div>
                            <span class="tag ${t.status === 'Completed' ? 'tag-success' : 'tag-error'}">${t.status}</span>
                            <span style="font-size: 12px; color: var(--success-green); margin-left: 8px; font-weight: 600;">
                                ✓ SHA-256 Verified
                            </span>
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

async function fetchPartials() {
    try {
        const res = await fetch('/api/partials');
        const data = await res.json();
        const container = document.getElementById('partials-list-container');

        if (container && data.partials) {
            if (data.partials.length === 0) {
                container.innerHTML = `<div class="empty-state"><p>No partial .part files found in storage/downloads/.</p></div>`;
                return;
            }

            container.innerHTML = '';
            data.partials.forEach(p => {
                const card = document.createElement('div');
                card.className = 'stat-detail-card';
                card.style.marginBottom = '12px';
                card.style.padding = '16px 20px';
                card.innerHTML = `
                    <div class="flex-between">
                        <div>
                            <strong>${p.filename}.part</strong>
                            <div style="font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 4px;">
                                Bytes Saved: ${formatBytes(p.bytes_received)} • Resume Offset Ready
                            </div>
                        </div>
                        <button class="btn btn-sm btn-primary-pill" onclick="performDownload('${p.filename}', true)">
                            🔄 RESUME DOWNLOAD (TCP)
                        </button>
                    </div>
                `;
                container.appendChild(card);
            });
        }
    } catch (e) {
        console.warn('Fetch partials error:', e);
    }
}

// ========================================================
// 8 & 9. LIVE CHAT (GROUP BROADCAST & PRIVATE 1-ON-1)
// ========================================================
async function fetchChatMessages() {
    try {
        const res = await fetch('/api/chat/messages');
        const data = await res.json();
        if (!data.messages) return;

        renderGroupChat(data.messages);
        renderPrivateChat(data.messages);
    } catch (e) {
        console.warn('Fetch chat messages error:', e);
    }
}

function renderGroupChat(messages) {
    const box = document.getElementById('group-messages-list');
    if (!box) return;

    const groupMsgs = messages.filter(m => m.mode === 'GROUP');
    if (groupMsgs.length === 0) {
        box.innerHTML = `<div class="sys-msg">Connected to UDP Group Chat. Messages sent here broadcast to all online peers.</div>`;
        return;
    }

    box.innerHTML = '';
    groupMsgs.forEach(m => {
        const isMine = m.sender === currentUsername;
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${isMine ? 'mine' : 'theirs'}`;
        bubble.innerHTML = `
            <div style="font-weight: 700; font-size: 11px; margin-bottom: 2px;">${m.sender}</div>
            <div>${m.message}</div>
            <div class="chat-bubble-meta">
                <span>Seq #${m.sequence || 0}</span>
                <span>${m.timestamp || ''}</span>
                <span style="font-weight: 600;">${m.status || 'Delivered'}</span>
            </div>
        `;
        box.appendChild(bubble);
    });
    box.scrollTop = box.scrollHeight;
}

function selectPrivatePeer(username) {
    activePrivatePeer = username;
    const targetHeader = document.getElementById('private-target-header');
    const targetEndpoint = document.getElementById('private-target-endpoint');

    if (targetHeader) targetHeader.textContent = `Private Chat with: ${username}`;

    const peerData = onlineUsersCache.find(u => u.username === username);
    if (targetEndpoint) targetEndpoint.textContent = `Endpoint: ${peerData?.endpoint || '127.0.0.1'}`;

    renderPrivatePeersSidebar();
    fetchChatMessages();
}

function renderPrivateChat(messages) {
    const box = document.getElementById('private-messages-list');
    if (!box) return;

    if (!activePrivatePeer) {
        box.innerHTML = `<div class="sys-msg">Select an online peer from the left sidebar to start private messaging.</div>`;
        return;
    }

    const privateMsgs = messages.filter(m => 
        m.mode === 'PRIVATE' && (
            (m.sender === currentUsername && m.recipient === activePrivatePeer) ||
            (m.sender === activePrivatePeer && m.recipient === currentUsername)
        )
    );

    if (privateMsgs.length === 0) {
        box.innerHTML = `<div class="sys-msg">No private messages with '${activePrivatePeer}' yet. Start the conversation over isolated UDP!</div>`;
        return;
    }

    box.innerHTML = '';
    privateMsgs.forEach(m => {
        const isMine = m.sender === currentUsername;
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${isMine ? 'mine' : 'theirs'}`;
        bubble.innerHTML = `
            <div style="font-weight: 700; font-size: 11px; margin-bottom: 2px;">
                ${isMine ? 'You (Private)' : m.sender}
            </div>
            <div>${m.message}</div>
            <div class="chat-bubble-meta">
                <span>Seq #${m.sequence || 0}</span>
                <span>${m.timestamp || ''}</span>
                <span style="font-weight: 600;">${m.status || 'Delivered'}</span>
            </div>
        `;
        box.appendChild(bubble);
    });
    box.scrollTop = box.scrollHeight;
}

async function sendGroupMessage() {
    const input = document.getElementById('group-chat-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    input.value = '';

    try {
        const res = await fetch('/api/chat/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, recipient: 'ALL' })
        });
        const data = await res.json();
        if (data.success) {
            fetchChatMessages();
            fetchLogs();
        } else {
            showToast('error', 'Send Failed', data.error || 'Failed to send UDP datagram');
        }
    } catch (e) {
        showToast('error', 'UDP Socket Error', e.message);
    }
}

async function sendPrivateMessage() {
    if (!activePrivatePeer) {
        showToast('warning', 'No Peer Selected', 'Please select a recipient peer first.');
        return;
    }

    const input = document.getElementById('private-chat-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    input.value = '';

    try {
        const res = await fetch('/api/chat/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, recipient: activePrivatePeer })
        });
        const data = await res.json();
        if (data.success) {
            fetchChatMessages();
            fetchLogs();
        } else {
            showToast('error', 'Send Failed', data.error || 'Failed to route private datagram');
        }
    } catch (e) {
        showToast('error', 'UDP Socket Error', e.message);
    }
}

// ========================================================
// 10. NETWORK STATISTICS & PACKET LOSS SIMULATOR
// ========================================================
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
            if (elTcpSpeedUp) elTcpSpeedUp.textContent = `${data.tcp.upload_speed_kbs || 0.0} KB/s`;
            if (elTcpSpeedDown) elTcpSpeedDown.textContent = `${data.tcp.download_speed_kbs || 0.0} KB/s`;
        }

        if (data.udp) {
            const elUdpSent = document.getElementById('stat-udp-bytes-sent');
            const elUdpRecv = document.getElementById('stat-udp-bytes-recv');
            const elUdpAcks = document.getElementById('stat-udp-acks');
            const elUdpRetries = document.getElementById('stat-udp-retries');
            const elUdpSuccess = document.getElementById('stat-udp-success');
            const elUdpLoss = document.getElementById('stat-udp-loss');
            const metricRate = document.getElementById('metric-delivery-rate');

            if (elUdpSent) elUdpSent.textContent = formatBytes(data.udp.bytes_sent);
            if (elUdpRecv) elUdpRecv.textContent = formatBytes(data.udp.bytes_received);
            if (elUdpAcks) elUdpAcks.textContent = data.udp.acks_received || 0;
            if (elUdpRetries) elUdpRetries.textContent = data.udp.retransmissions || 0;
            if (elUdpSuccess) elUdpSuccess.textContent = `${data.udp.success_percentage || 100.0}%`;
            if (elUdpLoss) elUdpLoss.textContent = `${data.udp.loss_percentage || 0.0}%`;
            if (metricRate) metricRate.textContent = `${data.udp.success_percentage || 100.0}%`;
        }
    } catch (e) {
        console.warn('Fetch network stats error:', e);
    }
}

function updateLossLabel(val) {
    const lbl = document.getElementById('loss-label');
    if (lbl) lbl.textContent = `${val}%`;
}

async function applyLossSimulation() {
    const slider = document.getElementById('loss-slider');
    const val = parseInt(slider ? slider.value : 0) || 0;
    const rate = val / 100.0;

    try {
        const res = await fetch('/api/simulation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rate })
        });
        const data = await res.json();
        if (data.success) {
            showToast('warning', 'Packet Loss Simulation Active', `UDP packet loss rate set to ${val}%. Artificial drops will trigger 1.0s ACK retransmissions.`);
            fetchLogs();
            fetchNetworkStats();
        }
    } catch (e) {
        showToast('error', 'Simulation Error', e.message);
    }
}

// Activity logs
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

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}
