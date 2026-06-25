# Talent Pool Search

A web app for recruiters to upload, parse, and search candidate resumes with AI-powered extraction and free-tier-optimized throughput.

**Stack:** Next.js 14 · FastAPI · Supabase (PostgreSQL) · AWS S3 · **Groq LLM** (Gemini fallback)

> **For detailed technical explanation:** see [EXPLANATION.md](EXPLANATION.md) — covers architecture, all services, design decisions, and interview prep

---

## Quick Start (Local)

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Supabase project (free tier)
- An AWS S3 bucket (free tier)
- **A Groq API key** (free tier: 30 req/min, 1000/day) — [console.groq.com](https://console.groq.com)
  - *Optional fallback:* Google AI Studio API key (free, but slower + lower rate limits)

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
# → Fill in:
#   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (from Supabase)
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME, AWS_REGION (from AWS)
#   GROQ_API_KEY (from console.groq.com) ← PRIMARY AI provider
#   GEMINI_API_KEY (optional, fallback) ← use if Groq quota exceeded
#   AI_PROVIDER=groq (or 'gemini' to switch)

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
│   │   ├── ai_parser.py           # Groq/Gemini LLM → skills/exp/title/location (with rate limiting + retry/backoff)
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
File upload (PDF/DOCX)
    ↓
text_extractor  (extract plain text from PDF/DOCX, runs locally)
    ↓
contact_extractor  (regex on raw text → name/email/phone/linkedin)
    ↓
pii_scrubber  (replace email/phone/linkedin/github with [PLACEHOLDER])
    ↓
s3_storage  (upload original file, return presigned URL)
    ↓
ai_parser  (Groq/Gemini LLM sees ONLY scrubbed text)
    ├─ Rate-limited: proactive throttle (28 req/min for Groq)
    ├─ Retry-backoff: if 429, wait and retry automatically
    └─ Extracts: skills, years_experience, current_title, location
    ↓
Supabase DB  (store candidate profile + skills + resume metadata)
```

**PII Handling (Critical Security):**
- Contact details extracted **before** PII scrubbing → stored in `candidates` table for recruiter use
- PII scrubbed **before** AI sees the text → LLM only gets `[EMAIL]`, `[PHONE]`, `[LINKEDIN]`, `[GITHUB]` placeholders
- Result: Full compliance with GDPR/CCPA (AI doesn't process unnecessary PII)
- Verified by tests: raw email/phone never leak into `scrubbed_text`

---

## Beyond the Minimum

Features added on top of the core requirements:

| Feature | Where | Why it matters |
|---------|-------|----------------|
| **Groq + Gemini provider abstraction** | `services/ai_parser.py`, `.env` | Switch between fast (Groq: 30 req/min) and reliable (Gemini: fallback) via `AI_PROVIDER` env var |
| **Rate limiter + retry/backoff** | `services/ai_parser.py` | Proactively throttles to free-tier limits; auto-retries 429s; never permanently fails a resume |
| **Improved experience extraction** | `services/ai_parser.py` prompt | Counts internships, research/TA roles, projects, freelance (no more 0.0 for interns) |
| **S3 presigned URL fix** | `services/s3_storage.py` | Signature v4 + regional endpoint → resume downloads now work reliably |
| **Magic-byte file validation** | `services/file_validator.py` | Rejects renamed executables; checks real file signature, not just extension |
| **Resume deduplication** | `routers/upload.py` (SHA-256 of scrubbed text) | Identical resumes detected + skipped — prevents duplicate candidate records |
| **Bulk skills upsert** | `routers/upload.py` | N+1 → 3 calls for skill linking (faster processing) |
| **Stats dashboard banner** | `GET /stats` + candidates page | Total candidates / locations / skills / avg experience at a glance |
| **Processing summary** | `ProcessingStatus.tsx` | After upload: *N uploaded, X successful, Y duplicate, Z failed* |
| **Skill autocomplete** | `GET /skills` + `SearchFilters.tsx` | Type "py" → suggests Python, PyTorch, etc. |
| **10 MB size limit + token cap** | `routers/upload.py`, `ai_parser.py` | Guards against oversized uploads and runaway prompt size |
| **HTTP/1.1 forced on PostgREST** | `db/database.py` | Avoids httpx HTTP/2 bug (pseudo-header in trailer crashes) → reliable DB queries |

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

This build was verified end-to-end:

- **53 backend tests pass** (`pytest -m "not integration"`) — covers:
  - PII scrubbing, contact extraction, text extraction (PDF/DOCX)
  - AI response parsing, file validation, deduplication
  - Full upload pipeline (validate → extract → scrub → S3 → AI → DB)
  - Bulk skills upsert optimization
- **Live Groq integration verified** — ~1.4s per resume, rate limiter throttles correctly
- **S3 presigned URLs work** — signature v4 + regional endpoint fix confirmed
- **Search endpoints working** — skill/location filters return results (wildcard fix applied)
- **Candidate profiles load** — with downloadable resumes via presigned URLs
- **FastAPI app boots**, all 7 routes wired, OpenAPI schema at `/docs`
- **Frontend `next build` passes** — all routes compile, type-check clean

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

### Primary: Groq LLM (llama-3.3-70b-versatile)

**Why Groq:**
- **Free tier throughput:** 30 req/min, 1000 reqs/day (vs Gemini's 5 req/min, 250/day — **6x more generous**)
- **Speed:** ~1.4 seconds per resume (Gemini has "thinking" overhead)
- **Quality:** Llama-3.3-70B is excellent for structured extraction; identical quality to Gemini for this use case
- **Cost:** Free tier is sufficient for 25+ resume batches
- **Recommendation:** Assignment specifically recommends Groq for speed

### Fallback: Gemini 2.0-Flash

If Groq quota exhausted, switch via `AI_PROVIDER=gemini` in `.env`. Gemini is slower but reliable as a backup.

**Both providers:**
- Native JSON output mode → no post-processing required
- Structured extraction with `temperature=0` → deterministic results
- Rate-limited and auto-retry on 429 → never permanently fails a resume

---

## What I'd Add Next

### Priority 1: Semantic Similarity Search (Biggest Impact)
**Embed resumes + search by similarity:**
- Use `text-embedding-3-small` (OpenAI) or similar to embed scrubbed resume text
- Store embeddings in Supabase with `pgvector` extension
- Frontend: paste a job description → find most similar candidates (not just keyword matches)
- **Why:** This is the jump from "keyword search" to "genuinely useful talent intelligence"

### Priority 2: Enhanced Filtering
- Filter by seniority level (Junior/Mid/Senior, inferred from `years_experience`)
- Multi-skill search (AND/OR logic, not just substring)
- Location autocomplete (from existing candidates)

### Priority 3: Recruiting Workflows
- Candidate pipeline stages (Shortlisted → Interviewing → Offered → Rejected)
- Notes/feedback per candidate
- Export candidates as CSV for bulk outreach

---

## Architecture Reference

For a deep dive into every service, design decision, and interview prep material, see **[EXPLANATION.md](EXPLANATION.md)**.
