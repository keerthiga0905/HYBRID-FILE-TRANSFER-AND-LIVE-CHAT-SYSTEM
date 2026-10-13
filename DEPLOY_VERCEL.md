# 🚀 Vercel Deployment Guide: Hybrid File Transfer & Live Chat System

This document provides a comprehensive, step-by-step walkthrough for deploying the **Hybrid File Transfer and Live Chat System** web application to **Vercel** from scratch.

---

## 📋 Table of Contents
1. [Architecture Overview: Vercel Serverless & Python Sockets](#1-architecture-overview)
2. [Vercel Project Structure](#2-vercel-project-structure)
3. [Prerequisites](#3-prerequisites)
4. [Method 1: One-Click Deployment via GitHub & Vercel Dashboard (Recommended)](#4-method-1-deploying-via-github--vercel-dashboard-recommended)
5. [Method 2: Command-Line Deployment via Vercel CLI](#5-method-2-deploying-via-vercel-cli)
6. [Connecting Real TCP (5000) & UDP (6000) Sockets to Vercel](#6-connecting-real-tcp--udp-sockets-to-vercel)
7. [Post-Deployment Verification & Testing](#7-post-deployment-verification--testing)
8. [Troubleshooting & Common Questions](#8-troubleshooting--common-questions)

---

## 1. Architecture Overview

### How the Application Runs on Vercel
* **Frontend Web Dashboard (HTML5 / Vanilla CSS / Vanilla JS SPA)**:
  Delivered through **Vercel's Global Edge Network (CDN)** with ultra-fast latency, caching, and responsive modern styling.
* **Backend API & Web Controller (Flask Python Engine)**:
  Runs as an ephemeral **Serverless WSGI Function** via `@vercel/python` using `api/index.py`. Vercel automatically installs the dependencies from `requirements.txt` and manages serverless scaling.
* **File Storage**:
  On Vercel serverless instances, the root filesystem is read-only. The system automatically detects the `VERCEL` environment and switches storage staging to `/tmp/storage` and logs to `/tmp/logs`.
* **TCP & UDP Socket Connectivity**:
  Because Vercel is a serverless HTTP platform, background processes cannot listen on raw socket ports (e.g. `0.0.0.0:5000` or `0.0.0.0:6000`) inside Vercel itself. You can point the dashboard to:
  * Your local PC running `python server/server.py` via **ngrok** tunnel.
  * A free cloud VPS / container (AWS EC2, Render, Railway, DigitalOcean).
  * Or use the dashboard in standalone evaluation mode.

---

## 2. Vercel Project Structure

The project has been structured specifically for Vercel compatibility:

```text
CN-project/
├── api/
│   └── index.py               <-- Vercel serverless entrypoint (exposes Flask app)
├── vercel.json                <-- Routing rules & URL rewrites for Vercel
├── .vercelignore              <-- Excludes test files, caches, and local logs
├── requirements.txt           <-- Dependencies installed by Vercel (flask>=3.0.0)
├── public/                    <-- Static assets served directly by Vercel Edge CDN
│   └── static/
│       ├── css/style.css
│       ├── js/app.js
│       └── images/hybrid_network_monolith.jpg
├── app.py                     <-- Main Flask application
├── web/
│   ├── templates/index.html   <-- Luxury editorial split-screen UI
│   └── static/                <-- Local static assets fallback
├── client/                    <-- TCP and UDP client socket logic
│   ├── client_controller.py
│   ├── tcp_client.py
│   └── udp_client.py
├── server/                    <-- Real TCP (5000) and UDP (6000) socket servers
│   ├── server.py
│   ├── tcp_server.py
│   └── udp_server.py
└── shared/                    <-- Shared protocols, checksums, stats & config
    ├── config.py              <-- Auto-adapts to /tmp on Vercel
    ├── protocol.py
    ├── checksum.py
    └── stats.py
```

---

## 3. Prerequisites

Before starting, ensure you have:
1. A **GitHub account** ([github.com](https://github.com)).
2. A **Vercel account** ([vercel.com](https://vercel.com) — free hobby plan).
3. **Git** installed on your machine.
4. Your repository committed and pushed to GitHub:
   `https://github.com/keerthiga0905/HYBRID-FILE-TRANSFER-AND-LIVE-CHAT-SYSTEM`

---

## 4. Method 1: Deploying via GitHub & Vercel Dashboard (Recommended)

This is the easiest, zero-installation method with automated CI/CD (updates automatically on every `git push`).

### Step 1: Push Latest Changes to GitHub
Open your terminal in the project directory and verify all files are committed and pushed:
```bash
git status
git add .
git commit -m "feat: configure project structure and entrypoints for Vercel deployment"
git push origin main
```

### Step 2: Log into Vercel
1. Go to [https://vercel.com/](https://vercel.com/)
2. Click **"Log In"** and select **"Continue with GitHub"**.

### Step 3: Import the GitHub Repository
1. On your Vercel Dashboard, click the **"Add New..."** button (top right) and choose **"Project"**.
2. Find `HYBRID-FILE-TRANSFER-AND-LIVE-CHAT-SYSTEM` in the list of GitHub repositories.
3. Click the blue **"Import"** button next to the repository.

### Step 4: Configure Project Settings
In the **Configure Project** screen:
* **Project Name**: Keep as `hybrid-file-transfer-and-live-chat-system` (or any custom name).
* **Framework Preset**: Select **"Other"** (Vercel automatically detects the Python runtime via `vercel.json` and `api/index.py`).
* **Root Directory**: `./` (leave default).
* **Build and Output Settings**:
  * Leave all build commands empty/default. Vercel automatically runs `pip install -r requirements.txt`.
* **Environment Variables**: None required by default.

### Step 5: Click Deploy
1. Click the **"Deploy"** button.
2. Vercel will start building the project:
   * Cloning repository.
   * Installing Python dependencies (`flask`).
   * Packaging serverless function `api/index.py`.
   * Uploading static assets to Vercel Global CDN.
3. Within **30 to 45 seconds**, you will see confetti and a preview screenshot!
4. Click **"Continue to Dashboard"** or click the domain link (e.g. `https://hybrid-file-transfer-and-live-chat-system.vercel.app`).

---

## 5. Method 2: Deploying via Vercel CLI

If you prefer deploying directly from your command line / PowerShell:

### Step 1: Install Vercel CLI
Ensure Node.js is installed, then run:
```bash
npm install -g vercel
```

### Step 2: Log into Vercel via CLI
```bash
vercel login
```
Select your login method (e.g., GitHub or Email) and confirm in your browser.

### Step 3: Deploy Preview Build
In your project directory:
```bash
cd "c:\Users\KEERTHIGA M\Desktop\CN-project"
vercel
```
Answer the interactive prompts:
* `Set up and deploy?` **y**
* `Which scope do you want to deploy to?` Select your personal account
* `Link to existing project?` **N**
* `What's your project's name?` `hybrid-transfer` (or press Enter)
* `In which directory is your code located?` `./` (press Enter)
* `Want to modify settings?` **N** (press Enter)

Vercel will output a preview URL (e.g., `https://hybrid-transfer-xxx.vercel.app`).

### Step 4: Deploy Directly to Production
Once confirmed, promote to production:
```bash
vercel --prod
```
Your live production URL will be displayed in the terminal output.

---

## 6. Connecting Real TCP & UDP Sockets to Vercel

The Vercel deployment provides the full user interface, API endpoints, network statistics tracker, and packet loss simulator. To connect to an active TCP (5000) and UDP (6000) socket server:

### Option A: Tunnel your Local PC Server using ngrok (Free & Instant)
If `server/server.py` is running on your laptop / PC:
1. Download and install [ngrok](https://ngrok.com/).
2. Start the local server:
   ```bash
   python server/server.py
   ```
3. Expose the TCP server port:
   ```bash
   ngrok tcp 5000
   ```
   ngrok will give you a forwarding URL like `tcp://0.tcp.ngrok.io:12345`.
4. On your live Vercel web page:
   * Click **"LET'S CONNECT"** (or go to **"Online User"** / **"Login & Session"**).
   * Enter the Server IP (`0.tcp.ngrok.io`) and Port (`12345`).
   * Click **"Connect"**!

### Option B: Host `server.py` on a Free Cloud VM (AWS EC2 / Render / Railway)
1. Deploy `server/server.py` on a long-running Linux VM (such as an AWS EC2 t4g.nano/micro or Render Background Worker).
2. Allow inbound rules on TCP port `5000` and UDP port `6000`.
3. In the Vercel web UI, enter the VM's Public IPv4 address.

---

## 7. Post-Deployment Verification & Testing

Verify that all endpoints and assets are loading properly on your live Vercel URL:

| Component | URL Path | Expected Result |
| :--- | :--- | :--- |
| **Home Page** | `https://<your-app>.vercel.app/` | 50/50 split luxury UI with Monolith image |
| **CSS Stylesheet** | `/static/css/style.css` | HTTP 200 via Edge CDN |
| **Product Image** | `/static/images/hybrid_network_monolith.jpg` | HTTP 200 via Edge CDN |
| **Status API** | `/api/status` | JSON response with TCP/UDP connection state |
| **Network Stats API** | `/api/stats` | JSON response with throughput and RTT metrics |
| **Online Users API** | `/api/users` | JSON response from presence registry |
| **File Repository API**| `/api/files` | JSON response with stored files |

---

## 8. Troubleshooting & Common Questions

### Q1: Why does Vercel show "TCP: Offline" and "UDP: Offline" when I first open the site?
> **Answer**: This is expected behavior! Vercel is a serverless HTTP host. The status pills reflect the live state of the Python sockets. Once you click **"LET'S CONNECT"** and point to an active server IP (or run your backend server with ngrok/EC2), the status indicators update to **"Online"** with green glowing indicators.

### Q2: Did Vercel experience a "Read-only file system" error during file upload?
> **Answer**: No. `shared/config.py` automatically detects when the application is running in Vercel's serverless environment and redirects all uploads, downloads, and logs to the writable `/tmp/storage` directory.

### Q3: How do I update my Vercel deployment after editing code?
> **Answer**: If you connected via GitHub (Method 1), simply run:
> ```bash
> git add .
> git commit -m "update: improvements"
> git push origin main
> ```
> Vercel will automatically detect the push and deploy a new build in ~30 seconds.

---

**Congratulations! Your Hybrid TCP/UDP Transfer & Live Chat System is now deployed on Vercel.** 🌐
