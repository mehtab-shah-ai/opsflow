# OpsFlow AI ⚡
### Intelligent Facility Operations, Automated Data Cleaning & Compliance Engine
> **Prototype Engineered for Grace Facility Services**  
> *Transforming messy spreadsheets, shift rosters, and multi-site facility data into trusted operational clarity.*

---

## 🌟 Executive Summary: The Problem & The Solution

In large facility management companies like **Grace Facility Services**, operations teams handle dozens of daily spreadsheets, shift logs, and client reports across multiple sites (e.g. Sydney CBD, North Sydney, Parramatta, Melbourne). 

### 🛑 The Problem
* **Messy & Inconsistent Data:** Field staff enter dates inconsistently (`2024-09-12`, `12/09/2024`, `Sept 12`), names with trailing whitespace, and inconsistent shift statuses.
* **Hidden Roster Gaps:** Uncovered shifts or supervisor shortages are buried in 2,000+ rows of spreadsheets, leading to compliance breaches and client complaints.
* **Dangerous Manual Editing:** Cleaning data directly in Excel frequently overwrites raw evidence, corrupts date calculations, and introduces spreadsheet formula errors.
* **Slow Reporting:** Preparing daily Operations MIS and data quality audit reports for management takes 2–3 hours of manual formatting every morning.

### 💡 The Solution: OpsFlow AI
OpsFlow AI is an end-to-end operational intelligence workspace that automates data intake, cleans data safely with human-in-the-loop approvals, generates interactive analytics, provides an AI Copilot that explains trends in plain day-to-day English, and produces export-ready management reports in seconds.

---

## 🚀 Key Features

| Feature | What It Does | Why It Matters |
| :--- | :--- | :--- |
| **Multi-Source Ingestion** | Upload `.csv`, `.xlsx`, `.xls`, native multi-table `.pdf`, or import public Google Sheets. | Operations teams do not need to convert files before importing. |
| **Deterministic Data Profiler** | Detects schema, types, null values, duplicates, and statistical outliers automatically. | 100% mathematical accuracy without LLM hallucination. |
| **Safe Cleaning & Audit Engine** | Side-by-side review of suggested changes with confidence ratings. Creates immutable **Version 2** while locking raw originals. | Original audit evidence is never lost. Full compliance guarantee. |
| **Interactive Analytics** | Auto-generates charts for attendance rates, site roster gaps, and shift distributions. | Instant visual answers without building pivot tables manually. |
| **AI Copilot (Streaming)** | Ask questions in natural, everyday words. Explains issues simply and generates on-demand charts. | Anyone on the operations team can query data without knowing SQL or Python. |
| **Executive Reports** | Download Operations MIS Summary (PDF), Data Quality Audit (PDF), and Exception Lists (CSV/Excel). | Ready to forward directly to general managers and site supervisors. |
| **User Data Isolation** | Complete workspace isolation with JWT tokens, Fast 1-Click Demo Login, and clean slate reset. | Multi-tenant privacy: each manager or recruiter gets their own isolated workspace. |
| **Zero Formula Injection** | Escapes spreadsheet trigger characters (`=`, `+`, `-`, `@`) upon export. | Protects corporate workstations from malicious CSV payload execution. |

---

## 🔄 How the Data Cleaning & Export Engine Works

A core requirement of OpsFlow AI is ensuring that when a user uploads messy data, they get **clean, deduplicated, verified data** back with a complete record of what happened:

```
[Raw Messy Upload] ──> [Schema & Issue Detection] ──> [Human Review Modal]
 (CSV, Excel, PDF)       (Duplicates, Nulls, Typo)       (Approve Safe Changes)
                                                               │
                                                               ▼
[Export Options] <──── [Immutable Version 2] <─────── [Audit Trail Logged]
  • Clean CSV            (Original locked untouched)   (Old Value vs New Value)
  • Clean Excel (.xlsx)
  • Executive PDF Report
```

1. **Upload:** Raw file is parsed and stored with hash verification.
2. **Detection:** OpsFlow identifies formatting errors, trailing spaces, duplicate IDs, missing critical values, and ambiguous dates.
3. **Review:** The user is shown every proposed change (e.g. *Row #14: `North Sydney ` ➔ `North Sydney` · 100% confidence*).
4. **Clean Dataset Created:** Once approved, OpsFlow creates **Version 2** of the dataset. The raw original file is retained in storage and remains downloadable at any time.
5. **Verified Download:** The user can export the clean dataset as a sanitized CSV or Excel file. The Run History and Audit Trail list every single modification made.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RENDER CLOUD DEPLOYMENT                         │
├─────────────────────────────────────┬──────────────────────────────────┤
│        STATIC SITE (FRONTEND)       │     WEB SERVICE (BACKEND)        │
│  React 18 + Vite + TypeScript       │  FastAPI (Python 3.12) + SQLite  │
│  • Instant 0-second CDN page load   │  • Resilient Multi-Provider AI   │
│  • Proactive wake-up ping           │    (Groq primary + Gemini flash) │
│  • Auto-dismissing wake modal       │  • Rule Engine & Audit Storage   │
│  • Apache ECharts visualizations    │  • ReportLab PDF Generator       │
└──────────────────┬──────────────────┴──────────────────▲───────────────┘
                   │                                     │
                   │      REST API / SSE Chat Stream     │
                   └─────────────────────────────────────┘
```

### Render Cold-Start UX Optimization
Render free-tier web services sleep after 15 minutes of inactivity:
* **The Problem:** Other apps show a blank screen or broken API errors for 30–45 seconds while the backend boots.
* **OpsFlow Solution:** 
  1. The static frontend loads instantly (0 seconds) from Render's global CDN.
  2. On first visit, the frontend proactively sends a lightweight `/health` ping to start the backend container.
  3. If the backend is sleeping, a sleek green **"Backend is Waking Up… Please Wait"** card appears with an elapsed seconds timer and progress bar.
  4. Once the backend responds, the modal turns into a green checkmark and auto-dismisses smoothly.

---

## 💻 Tech Stack

### Frontend
* **Core:** React 18, TypeScript, Vite
* **State & Data Fetching:** TanStack React Query (polling & dynamic retry)
* **Visuals & Charts:** Apache ECharts (`echarts-for-react`)
* **Animations:** Framer Motion
* **Icons:** Lucide React
* **Styling:** Custom Vanilla CSS Design System with dark mode support

### Backend
* **API Framework:** FastAPI, Uvicorn (Asynchronous Python 3.12)
* **Data Processing:** Pandas, NumPy
* **Spreadsheet & PDF Engines:** OpenPyXL, XLRD, PDFPlumber
* **PDF Report Generation:** ReportLab (Clean corporate executive styling)
* **Database & Persistence:** SQLite with Write-Ahead Logging (WAL) & connection pooling
* **AI Engine:**
  * **Primary:** Groq Cloud API (`openai/gpt-oss-20b` running at 500+ tokens/sec)
  * **Secondary Fallback:** Google Gemini API (`gemini-2.5-flash`)
  * **Deterministic Fallback:** Statistical calculations remain 100% functional even when offline

---

## 🚀 Deployment to Render (Step-by-Step)

OpsFlow AI is pre-configured with a `render.yaml` blueprint. You can deploy it in two ways:

### Method A: 1-Click Blueprint (Recommended)
1. Push this repository to your GitHub account:
   ```bash
   git remote add origin https://github.com/mehtab-shah-ai/opsflow.git
   git branch -M main
   git push -u origin main
   ```
2. Log in to [dashboard.render.com](https://dashboard.render.com/).
3. Click **New +** ➔ **Blueprint**.
4. Connect your `opsflow` GitHub repository. Render will automatically read `render.yaml` and configure both the backend Web Service and frontend Static Site.
5. In the environment variables prompt, enter your `GROQ_API_KEY_1` or `GEMINI_API_KEY`.
6. Click **Apply**. Both services will build and deploy automatically!

---

### Method B: Manual Deployment (Two Services)

#### 1. Backend Web Service
1. On Render, click **New +** ➔ **Web Service**.
2. Select repository `opsflow`.
3. Fill in the following settings:
   * **Name:** `opsflow-backend`
   * **Language:** `Python 3`
   * **Root Directory:** `backend`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   * **Plan:** Free
4. Add **Environment Variables**:
   * `PYTHON_VERSION`: `3.12.0`
   * `RUNTIME_DIR`: `/tmp/opsflow_runtime`
   * `GROQ_API_KEY_1`: `<your-groq-api-key>`
   * `GEMINI_API_KEY`: `<your-gemini-api-key>`
5. Click **Create Web Service**. Note down the URL (e.g. `https://opsflow-backend.onrender.com`).

#### 2. Frontend Static Site
1. On Render, click **New +** ➔ **Static Site**.
2. Select repository `opsflow`.
3. Fill in the following settings:
   * **Name:** `opsflow-frontend`
   * **Root Directory:** `frontend`
   * **Build Command:** `npm install && npm run build`
   * **Publish Directory:** `dist`
4. Add **Environment Variable**:
   * `VITE_API_BASE_URL`: `https://opsflow-backend.onrender.com` *(use your backend URL from step 1)*
5. Under **Redirects/Rewrites**:
   * OpsFlow includes a `public/_redirects` file that automatically rewrites all routes (`/* ➔ /index.html 200`) for seamless client-side SPA routing.
6. Click **Create Static Site**.

---

## 🛠️ Local Development Quickstart

### Prerequisites
* Python 3.11 or 3.12
* Node.js 18+ and npm

### 1. Clone the Repository
```bash
git clone https://github.com/mehtab-shah-ai/opsflow.git
cd opsflow
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp ../.env.example .env
# Edit .env and paste your Groq or Gemini API key
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Backend health check is available at: `http://127.0.0.1:8000/health`  
Interactive Swagger docs: `http://127.0.0.1:8000/docs`

### 3. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at `http://127.0.0.1:5173/`.

### 4. Running Backend Tests
OpsFlow includes a comprehensive 23-test suite covering domain math, safe cleaning, formula injection prevention, and user data isolation:
```bash
cd backend
pytest
```
All 23 tests pass cleanly in under 10 seconds.

---

## 🔒 Security & Compliance
* **Isolated User Sessions:** Data uploaded in one session or account is completely isolated from others using cryptographically secure tokens.
* **Formula Injection Prevention:** Any cell starting with `=, +, -, @` is automatically escaped with a leading single quote before CSV export.
* **Audit Trail Preservation:** Cell modifications are versioned and logged with user, timestamp, previous value, new value, and rule reason.
* **Safe Chat Guardrails:** The AI Copilot has read-only access to datasets and cannot mutate database records through conversation.

---

## 👥 Credits & Prototype Context
This project was conceptualized and built by **Mehtab Shah** as a specialized operational intelligence prototype for **Grace Facility Services**.
* **Repository:** [https://github.com/mehtab-shah-ai/opsflow](https://github.com/mehtab-shah-ai/opsflow)
* **Author:** Mehtab Shah
