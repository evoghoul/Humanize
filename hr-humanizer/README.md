# HR Communication Humanizer

An AI-powered writing assistant specifically built for human resources professionals. It rewrites rough drafts into natural, empathetic, and professional workplace communication while strictly preserving all underlying facts, numbers, dates, negations, uncertainty, and intent.

Built with **GoHumanize Open Humanizer** + **Local Ollama** + **FastAPI** + **React/TypeScript**.

---

## Key Highlights

- **Dual-Engine Workflow (Gemini First ➔ Local Fallback)**: Uses Google Gemini (`gemini-2.5-flash`) as the primary high-throughput cloud engine. If Gemini reaches its rate limits (HTTP 429) or encounters network/service errors, the local Ollama AI model automatically takes charge with zero downtime.
- **Improve Wording, Not Facts**: Evaluates rewrites using a layered fact-preservation engine to prevent the model from converting uncertainty into certainty (e.g. converting *"may be suitable"* into *"good fit"*) or hallucinating subjective judgments (e.g. *"a red flag"*).
- **Resilient Offline / Local Capability**: Can run completely offline using local Ollama (`hf.co/gohumanize/gohumanize-open-humanizer:Q4_K_M` or `llama3.1:8b`) or rule-based deterministic processing whenever internet/cloud access is unavailable.
- **Dual Workspace with Diff Viewer**: Side-by-side comparison of original drafts and humanized rewrites with highlighted metric preservation and word changes.
- **Deterministic Fact Checks & Targeted Retries**: Automatically extracts numbers, dates, negations, and hedges; flags discrepancies; and triggers targeted retries when necessary.


---

## Architecture Overview

```
hr-humanizer/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application & static frontend server
│   │   ├── humanizer.py     # Ollama OpenAI-compatible client, cleanup & retry logic
│   │   ├── fact_checks.py   # Multi-layer factual fidelity & negation validation
│   │   ├── prompts.py       # HR communication templates & tone instructions
│   │   ├── schemas.py       # Pydantic request & response data models
│   │   └── config.py        # Local application settings
│   ├── tests/
│   │   ├── test_fact_checks.py  # Unit tests covering Cases A through J
│   │   ├── test_api.py          # API integration tests
│   │   └── test_live_ollama.py  # Live Ollama end-to-end integration test
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/      # Header, EditorWorkspace, ValidationCard, DiffViewer, Presets
│   │   ├── App.tsx          # Main React state & API orchestrator
│   │   ├── index.css        # Modern executive slate UI design system
│   │   └── types.ts         # TypeScript schema definitions
│   ├── package.json
│   ├── vite.config.ts
│   └── dist/                # Pre-built production assets served by FastAPI
├── run-local.ps1            # Automated Windows PowerShell startup script
└── README.md
```

---

## Windows PowerShell Setup & Running

### Prerequisites
1. **Python 3.9+** (Tested on Python 3.11.9)
2. **Ollama** installed and running on Windows (`http://localhost:11434`)
3. The GoHumanize model pulled in Ollama:
   ```powershell
   ollama pull hf.co/gohumanize/gohumanize-open-humanizer:Q4_K_M
   ```

### Method 1: 1-Click Automated Launch (Easiest - All Services in One)

Simply double-click or run `start.bat` (or `python start.py`) from either the root folder or `hr-humanizer`:

- **Windows Double-Click**: Double-click `start.bat` in Windows Explorer.
- **Or from Terminal**:
  ```cmd
  start.bat
  ```
  or
  ```bash
  python start.py
  ```

This automatically:
1. Validates and starts the local **Ollama AI service** and ensures the GoHumanize model is loaded.
2. Checks dependencies and launches the **FastAPI Backend Server** (`http://127.0.0.1:8000`).
3. Launches the **React/Vite Frontend** (`http://localhost:5173`).
4. Automatically opens your default web browser to the app.
5. Cleanly stops all background services when you press `Ctrl+C`.

---

### Method 2: PowerShell Script

In Windows PowerShell, navigate to the `hr-humanizer` directory and run:

```powershell
cd "C:\Users\EVO GHOUL\Downloads\gohumanize-open-humanizer\hr-humanizer"
.\run-local.ps1
```

---

### Method 3: Manual Terminal Launch

If you prefer to run the backend and frontend separately:

**Window 1: Start Backend**
```powershell
cd "C:\Users\EVO GHOUL\Downloads\gohumanize-open-humanizer\hr-humanizer\backend"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Window 2: Start Frontend (Optional Development Mode)**
```powershell
cd "C:\Users\EVO GHOUL\Downloads\gohumanize-open-humanizer\hr-humanizer\frontend"
npm install
npm run dev
```
Open **http://localhost:5173** in your browser.

---

## Fact-Checking & Validation Architecture

The GoHumanize model can occasionally introduce unsupported evaluations (such as labeling a missing skill *"a red flag"*) or upgrading tentative assessments (*"may be suitable"* into *"is a strong fit"*). 

The HR Humanizer includes a dedicated validation engine in `app/fact_checks.py`:

| Layer | What is Checked | What Triggers a Warning / Review |
|---|---|---|
| **Numbers & Metrics** | Scores (`78/100`), percentages (`6.5%`), salaries (`₹8,00,000`), counts (`7 of 10`, `four of six`) | Missing or altered figures |
| **Dates & Deadlines** | Dates (`August 1 to September 30`), weekdays (`Friday`), relative ranges | Missing dates or invented deadlines |
| **Negation Polarity** | Negations (`has not worked with Kubernetes`, `does not hold certification`, `offer not approved`) | Dropping, flipping, or softening a negative claim |
| **Modality & Hedges** | Tentative wording (`may be`, `might`, `proposed`, `estimated`, `unconfirmed`) | Upgrading uncertainty into certainty or endorsements |
| **Prohibited Hallucinations** | Subjective labels (`red flag`, `showstopper`, `good fit`, `poor performance`, `stellar`) | Introducing evaluative opinions not in original draft |
| **Speech Acts** | Inquiries & polite requests (`Could you please send...?`) | Turning polite requests into commands or demands |

If a critical discrepancy is identified, the backend automatically performs a **single targeted retry** reinforcing the violated constraint. If issues persist, the UI surfaces clear, human-readable warnings and labels the draft **"Requires HR Review"** rather than falsely claiming verification.

---

## Running Automated Tests

To run the complete test suite:

```powershell
cd "C:\Users\EVO GHOUL\Downloads\gohumanize-open-humanizer\hr-humanizer\backend"
python -m pytest tests/test_fact_checks.py tests/test_api.py -v
```

To run the live Ollama generation test:
```powershell
python -m pytest tests/test_live_ollama.py -s
```

---

## API Endpoints

- `GET /api/health` — Returns status of application and local Ollama model.
- `GET /api/config` — Returns available communication types, tones, models, and length limits.
- `POST /api/humanize` — Humanizes an HR draft with fact preservation and optional targeted retries.
- `POST /api/validate` — Re-validates any edited draft against the original source text.
