# Talent Pool Search

A web app for recruiters to upload, parse, and search candidate resumes.

**Stack:** Next.js 14 · FastAPI · Supabase (PostgreSQL) · AWS S3 · Gemini 2.5 Flash

---

## Quick Start (Local)

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Supabase project (free tier)
- An AWS S3 bucket (free tier)
- A Google AI Studio API key (free)

---

### 1. Database — run the migration in Supabase

1. Open your Supabase project → **SQL Editor**
2. Paste the contents of `migrations/001_init_schema.sql`
3. Click **Run**

---

### 2. Backend (FastAPI)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# → Fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME, GEMINI_API_KEY

# Start the server
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

### 3. Frontend (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Configure environment variables
cp .env.local.example .env.local
# → Set NEXT_PUBLIC_API_URL=http://localhost:8000

# Start the dev server
npm run dev
```

Open: http://localhost:3000

---

### 4. Run backend tests

```bash
cd backend
pytest -v -m "not integration"
```

---

## Project Structure

```
talent-pool-search/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── routers/
│   │   ├── upload.py              # POST /upload
│   │   ├── jobs.py                # GET /jobs/{id}  (polling)
│   │   └── candidates.py          # GET /candidates, /candidates/{id}, /stats, /skills
│   ├── services/
│   │   ├── text_extractor.py      # PDF + DOCX → raw text
│   │   ├── contact_extractor.py   # regex → name/email/phone/linkedin
│   │   ├── pii_scrubber.py        # replace PII with [EMAIL] etc.
│   │   ├── file_validator.py      # magic-byte validation + SHA-256 hashing
│   │   ├── ai_parser.py           # Gemini 2.5 Flash → skills/exp/title/location
│   │   └── s3_storage.py          # upload file to S3, return presigned URL
│   ├── db/database.py             # Supabase client singleton
│   ├── models/schemas.py          # Pydantic request/response models
│   └── tests/                     # pytest unit tests
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Upload page
│   │   └── candidates/
│   │       ├── page.tsx           # Search & filter
│   │       └── [id]/page.tsx      # Candidate profile
│   ├── components/
│   │   ├── UploadZone.tsx
│   │   ├── ProcessingStatus.tsx
│   │   ├── CandidateCard.tsx
│   │   └── SearchFilters.tsx
│   └── lib/
│       ├── api.ts                 # All fetch calls
│       └── types.ts               # TypeScript types
└── migrations/
    └── 001_init_schema.sql        # Supabase schema
```

---

## Data Pipeline

```
File upload
    → text_extractor   (PDF/DOCX → raw text, runs locally)
    → contact_extractor (regex on raw text → name/email/phone/linkedin)
    → pii_scrubber     (replace PII with placeholders)
    → s3_storage       (upload original file)
    → ai_parser        (Gemini sees only scrubbed text)
    → Supabase DB      (store candidate + skills)
```

**PII handling:** Contact details are extracted via regex on the server before the text reaches any external API. Gemini only ever sees anonymised text with `[EMAIL]`, `[PHONE]`, `[LINKEDIN]`, and `[GITHUB]` in place of real identifiers.

---

## Beyond the Minimum

Features added on top of the core requirements:

| Feature | Where | Why it matters |
|---------|-------|----------------|
| **Magic-byte file validation** | `services/file_validator.py` | Rejects a renamed `.exe → .pdf`; checks real file signature, not just the extension |
| **Resume deduplication** | `routers/upload.py` (SHA-256 of scrubbed text) | Identical resumes are detected and skipped — a real ATS feature |
| **Stats dashboard banner** | `GET /stats` + candidates page | Candidates / Locations / Skills / Avg Experience at a glance |
| **Processing summary** | `ProcessingStatus.tsx` | After upload: *N uploaded, X successful, Y duplicate, Z failed* |
| **Skill autocomplete** | `GET /skills` + `SearchFilters.tsx` | Type "py" → suggests Python, PyTorch |
| **10 MB size limit + token cap** | `routers/upload.py`, `ai_parser.py` | Guards against oversized uploads and runaway prompt size |

### API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/upload` | Upload PDF/DOCX files, returns `job_id` |
| GET | `/jobs/{job_id}` | Poll batch processing progress |
| GET | `/candidates` | Search/filter candidates (`skill`, `location`, `min_exp`) |
| GET | `/candidates/{id}` | Full candidate profile |
| GET | `/stats` | Global talent-pool stats |
| GET | `/skills?q=` | Skill autocomplete suggestions |
| GET | `/health` | Liveness probe |

---

## Verification

This build was verified end-to-end before submission:

- **53 backend unit + integration tests pass** (`pytest`) — covers PII scrubbing, contact extraction, PDF/DOCX text extraction, AI-response parsing, file validation, and the full upload pipeline incl. deduplication
- **Real PDF + DOCX pipeline check** — confirmed all PII is removed from the text the AI sees while skills/experience survive
- **FastAPI app boots**, all 7 routes wired, OpenAPI schema validates
- **Frontend `next build` passes** — all 4 routes compile, type-check clean

---

## Deployment

### Backend → Railway (recommended)

1. Push repo to GitHub
2. New project → Deploy from GitHub → select `backend/` folder
3. Add environment variables in Railway dashboard
4. Railway auto-detects `Dockerfile` and deploys

### Frontend → Vercel

1. New project → Import from GitHub → select `frontend/` folder
2. Add `NEXT_PUBLIC_API_URL` pointing to your Railway backend URL
3. Deploy

---

## AI Model Choice

**Gemini 2.5 Flash** was chosen because:
- Fastest response in the Gemini family (important for batches of 25+ resumes)
- Native JSON output mode — no post-processing required
- Generous free tier on Google AI Studio
- Accurate structured extraction with temperature=0

---

## What I'd Add Next

**Semantic similarity search** — embed each scrubbed resume with `text-embedding-004` and store vectors in Supabase `pgvector`. This lets recruiters paste a job description and find the most similar candidates, not just keyword matches. This is the single biggest upgrade from keyword search to genuinely useful talent intelligence.
