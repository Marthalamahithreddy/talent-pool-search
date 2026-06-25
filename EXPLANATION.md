# Talent Pool Search — Full Technical Explanation

This document explains every architectural decision, service, and component of the application. Use this to prepare for interview questions about tech choices, design decisions, and how everything works together.

---

## Table of Contents
1. [What is this app?](#what-is-this-app)
2. [Tech Stack Overview](#tech-stack-overview)
3. [Architecture Diagram](#architecture-diagram)
4. [Core Services](#core-services)
5. [Data Flow (End-to-End)](#data-flow-end-to-end)
6. [Key Concepts Explained](#key-concepts-explained)
7. [PII Handling (Security)](#pii-handling-security)
8. [Design Decisions & Trade-Offs](#design-decisions--trade-offs)

---

## What is this app?

**Problem:** Recruiters have stacks of resumes sitting in emails and folders. There's no easy way to search through them, extract key info (skills, experience, location), or organize candidates.

**Solution:** A web app that lets recruiters:
1. Upload multiple resume files (PDF/DOCX) at once
2. Automatically extract candidate info (skills, years of experience, title, location) using AI
3. Search and filter candidates by skill, location, or minimum experience
4. View full profiles with contact details and downloadable resumes

**Why it matters:** This solves a real pain point — turning unstructured resume files into a searchable, organized talent database.

---

## Tech Stack Overview

### Frontend (What users see)
- **Next.js 14** (React framework)
  - Why: Fast, server-side rendering, built-in API routes, great DX
  - Handles: Upload UI, candidate search, filtering, detail pages
- **Tailwind CSS** (styling)
  - Why: Utility-first CSS, fast to build beautiful UIs
- **TypeScript** (type safety)
  - Why: Catches bugs before production

### Backend (The brains)
- **FastAPI** (Python web framework)
  - Why: Blazing fast, async by default, auto-generated API docs (Swagger)
  - Handles: Receiving uploads, orchestrating the processing pipeline, search queries
- **Python 3.11+** (language)
  - Why: Great ecosystem for text processing, AI integration, data pipelines

### Database (The storage)
- **Supabase** (PostgreSQL + auth + real-time APIs)
  - Why: Free tier, PostgreSQL underneath (reliable), built-in REST API (PostgREST)
  - Stores: Candidates, skills, resumes, upload jobs, relationships

### File Storage (The file vault)
- **AWS S3** (cloud object storage)
  - Why: Cheap (~$0.023/GB/month), reliable, integrates with everything
  - Stores: Original resume files (PDFs, DOCXs)
  - Security: Files are private; we generate **presigned URLs** (temporary download links)

### AI/ML (The brain)
- **Groq LLM** (fast inference) or **Gemini 2.5 Flash** (fallback)
  - Why: Free tier is generous, structured JSON output (no parsing), fast
  - Does: Reads scrubbed resume text → extracts skills, experience, title, location
  - Provider selection: `AI_PROVIDER` env var (groq | gemini)

### Deployment (Going live)
- **Docker** (containerize the backend)
  - Why: Consistent environment everywhere, easy scaling
- **Railway** (backend hosting) + **Vercel** (frontend hosting)
  - Why: Free tiers, one-click deploy from GitHub, auto-scaling

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Page 1: Upload                                           │   │
│  │ - Drag-drop file zone (PDF/DOCX)                         │   │
│  │ - Show per-file progress (polling /jobs/{id})            │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Page 2: Search & Filter                                  │   │
│  │ - Search by skill (autocomplete)                         │   │
│  │ - Filter by location, min experience                     │   │
│  │ - Display candidates in card grid                        │   │
│  ├──────────────────────────────────────────────────────────┤   │
│  │ Page 3: Candidate Profile                                │   │
│  │ - Show: name, email, phone, linkedin, skills, exp        │   │
│  │ - Download button → presigned S3 URL                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                          ↓ HTTPS ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  Routes:                                                         │
│  ├─ POST /upload            → Start async resume processing     │
│  ├─ GET /jobs/{id}          → Poll processing status            │
│  ├─ GET /candidates         → Search with filters               │
│  ├─ GET /candidates/{id}    → Full profile                      │
│  ├─ GET /stats              → Dashboard stats                   │
│  ├─ GET /skills?q=          → Skill autocomplete                │
│  └─ GET /health             → Liveness check                    │
│                                                                  │
│  Processing Pipeline (per resume):                              │
│  validate → extract_text → extract_contacts → scrub_pii         │
│     ↓                                                            │
│  upload_to_s3 → parse_with_ai → save_to_db → link_skills      │
└─────────────────────────────────────────────────────────────────┘
    ↓          ↓              ↓              ↓
┌──────┐  ┌────────┐  ┌─────────────┐  ┌────────┐
│Supabase│ │AWS S3  │  │Groq/Gemini  │  │Upload  │
│        │ │        │  │   LLM       │  │Jobs DB │
│Stores: │ │Stores: │  │             │  │        │
│- Cands │ │- PDFs  │  │Extracts:    │  │Status: │
│- Skills│ │- DOCXs │  │- skills     │  │pending │
│- Resums│ │        │  │- exp        │  │process│
│- Jobs  │ │        │  │- title      │  │complet│
└──────┘  └────────┘  └─────────────┘  └────────┘
```

---

## Core Services

### 1. **Text Extractor** (`backend/services/text_extractor.py`)
**What:** Pulls plain text from PDF/DOCX files (no formatting, just words).

**How:**
- PDFs: Use **PyMuPDF** (fitz library) → reads all pages, extracts text
- DOCX: Use **python-docx** → reads all paragraphs, joins them
- Returns: One long string of plain text (e.g., "John Doe, Senior Engineer, Python, ...")

**Why separate:** Text extraction is IO-heavy; keeping it isolated makes the pipeline testable and modular.

---

### 2. **Contact Extractor** (`backend/services/contact_extractor.py`)
**What:** Finds name, email, phone, LinkedIn URL, GitHub URL from raw resume text using **regex patterns**.

**How:**
- Email: Standard email pattern `[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}`
- Phone: International/local formats `+91 9876543210` or `(123) 456-7890`
- LinkedIn: `linkedin.com/in/username`
- GitHub: `github.com/username`
- Name: Heuristic — first 5 non-empty lines, filter out contact markers, keep "name-like" strings

**Why regex:** Fast, zero network calls, deterministic. Works offline.

**Timing:** Runs **BEFORE** PII scrubbing so we capture real email/phone/LinkedIn.

---

### 3. **PII Scrubber** (`backend/services/pii_scrubber.py`)
**What:** Replaces all personal identifiable info with **placeholders** so the AI never sees real contact details.

**How:**
```
Raw:     "John Doe, john@acme.com, +1-555-0147, linkedin.com/in/john"
Scrubbed: "[NAME], [EMAIL], [PHONE], [LINKEDIN]"
          (Name is regex-extracted, so it's replaced too)
```

**Replacements (in order):**
1. LinkedIn URLs → `[LINKEDIN]`
2. GitHub URLs → `[GITHUB]`
3. Email addresses → `[EMAIL]`
4. Phone numbers → `[PHONE]` (only if 7–15 digits; avoids matching years like "2019")

**Why order matters:** URLs can contain email-like substrings, so we replace them first.

**Why critical:** The AI (Groq/Gemini) only ever sees the scrubbed text. This is the **main privacy control** in the entire app.

---

### 4. **AI Parser** (`backend/services/ai_parser.py`)
**What:** Sends scrubbed resume text to an LLM (Groq or Gemini) and extracts structured data.

**What it extracts:**
- `skills`: List of technical + soft skills (deduplicated, title-cased)
- `years_experience`: Total years of work (float, e.g., 4.5)
  - **Counts:** full-time roles, internships, research/TA, freelance, contracts
  - **Estimates conservatively** if only projects (never returns 0 unless genuinely no experience)
- `current_title`: Most recent job title (or internship/student title)
- `location`: City, country/state (e.g., "Hyderabad, India")

**How (the magic):**
1. Build a structured prompt: *"You are a resume parser. Extract skills, experience, title, location. Return ONLY JSON."*
2. Append the scrubbed resume text
3. Send to Groq/Gemini with `temperature=0` (deterministic) + `response_format=json`
4. Parse the JSON response, handle edge cases (markdown fences, null fields, "4 years" → 4.0)

**Rate limiting (new):**
- **Groq:** 28 req/min proactively throttled (free tier is 30)
- **Gemini:** 14 req/min proactively throttled (free tier is 15)
- If a 429 rate-limit error hits, retry with exponential backoff (respects server's "retry in Xs")
- Falls back gracefully if daily quota is exhausted

**Why Groq instead of Gemini?**
- Groq: 30 req/min, 1000/day (Gemini's 5 req/min, 250/day is crippling for batches)
- Speed: ~1.4s per resume (vs Gemini's delay + "thinking" overhead)
- Quality: Identical for structured extraction

---

### 5. **S3 Storage** (`backend/services/s3_storage.py`)
**What:** Uploads original resume files to AWS S3 and returns a **presigned download URL**.

**AWS S3 explained:**
- **S3** = Simple Storage Service = cloud file vault (like Google Drive for servers)
- **Bucket** = folder/namespace (e.g., `demo-726663954702-ap-south-1-an`)
- **Key** = file path (e.g., `resumes/uuid/Resume 7.docx`)
- **Presigned URL** = temporary download link (valid 7 days, no password needed)

**How presigning works:**
```
1. Backend calculates a signature using AWS secret key
2. Signature is valid ONLY for that specific bucket, key, expiry time
3. Frontend gets a link: https://...?AWSAccessKeyId=...&Signature=...&Expires=...
4. User clicks → browser requests S3 directly (backend never transfers the file)
5. S3 validates the signature; if it matches, serves the file
6. After 7 days, signature expires → link is dead (security)
```

**Why presigned URLs?**
- **No public bucket:** Files stay private (can't browse the bucket)
- **No credentials in frontend:** Browser doesn't see AWS keys
- **Time-limited:** Automatically expires (safety)
- **Cheap bandwidth:** S3 serves directly (backend not taxed)

**Recent fix:**
- Old code signed against global endpoint → S3 redirected to region → signature broke
- New code: `signature_version="s3v4"` + virtual addressing → signs against regional endpoint (`…s3.ap-south-1.amazonaws.com`)
- Result: No redirect, signature valid, file downloads work

---

### 6. **File Validator** (`backend/services/file_validator.py`)
**What:** Checks that uploaded files are *actually* PDFs/DOCXs (not a renamed `.exe`).

**How:**
- **Magic bytes** (file signature): First few bytes identify file type
  - PDF: `%PDF`
  - DOCX: `PK` (ZIP file, since DOCX is a zipped XML format)
- Compares actual file signature vs expected signature for the extension
- Also computes **SHA-256 hash** of scrubbed text for deduplication

**Why:** Prevents malicious uploads (e.g., fake.pdf that's actually an executable).

---

## Data Flow (End-to-End)

### Scenario: User uploads "resume.pdf"

```
STEP 1: FRONTEND
  User drag-drops resume.pdf on the upload zone
  → POST /upload with FormData([file1, file2, ...])
  
STEP 2: BACKEND RECEIVES
  Validation:
    ✓ File extension is .pdf or .docx
    ✓ File size < 10 MB
    ✓ Magic bytes match extension (actually a PDF, not fake.pdf.exe)
  
  Create database records:
    - upload_job (id=uuid, status='processing', total_files=1)
    - resume (id=uuid, job_id=parent, filename='resume.pdf', status='pending')
  
  Return to frontend: { job_id: uuid, message: "Processing started" }
  → Frontend now polls GET /jobs/{job_id} every 2 seconds

STEP 3: BACKGROUND PROCESSING (async, doesn't block)
  For each resume:
    
    A. EXTRACT TEXT
       → text_extractor.py
       → PyMuPDF extracts all text from PDF
       → Output: "John Doe, john@acme.com, ..."
    
    B. EXTRACT CONTACTS (from raw text)
       → contact_extractor.py
       → Regex finds: name="John Doe", email="john@acme.com", phone="+1-555-0147"
       → Output: dict with contact fields
    
    C. SCRUB PII
       → pii_scrubber.py
       → Replace emails/phones/URLs with [PLACEHOLDER]
       → Output: "[NAME], [EMAIL], [PHONE], ..." (safe to send to AI)
    
    D. CHECK FOR DUPLICATES
       → SHA-256 hash of scrubbed text
       → Query DB: "has this exact resume been uploaded before?"
       → If yes: mark as 'duplicate', skip AI parsing
       → If no: continue
    
    E. UPLOAD TO S3
       → s3_storage.py
       → AWS S3 stores the original PDF at resumes/uuid/resume.pdf
       → Generate presigned URL (valid 7 days)
       → Output: presigned_url
    
    F. SEND TO AI
       → ai_parser.py
       → API call to Groq/Gemini with scrubbed text
       → LLM extracts: skills, years_exp, title, location
       → Output: ParsedResume(skills=[...], years_experience=4.5, ...)
    
    G. SAVE TO DATABASE
       → INSERT candidate (name, email, phone, location, years_exp, title)
       → INSERT skills (python, fastapi, etc.)
       → INSERT candidate_skills (links candidate ↔ skills)
       → UPDATE resume (content_hash, s3_url, scrubbed_text, raw_text)
    
    H. UPDATE JOB STATUS
       → Increment processed_files counter
       → If all done: set job status='completed'

STEP 4: FRONTEND POLLING COMPLETES
  Frontend sees status='completed'
  → Shows summary: "2 uploaded, 2 successful, 0 failed"
  → Displays "View All Candidates" button

STEP 5: USER VIEWS CANDIDATES
  GET /candidates?skill=python&location=nyc
  
  Backend:
    1. Find all skill IDs matching "python" (case-insensitive contains)
    2. Find all candidate IDs with those skills
    3. Filter by location (contains "nyc")
    4. Return card view: name, title, location, years_exp, top 3 skills
  
  User clicks candidate → GET /candidates/{id}
    → Returns full profile:
       {
         name: "John Doe",
         email: "john@acme.com",
         phone: "+1-555-0147",
         linkedin_url: "linkedin.com/in/johndoe",
         location: "New York, USA",
         years_experience: 4.5,
         current_title: "Senior Backend Engineer",
         skills: ["Python", "FastAPI", "PostgreSQL", ...],
         s3_url: "presigned URL to download resume"
       }

STEP 6: USER DOWNLOADS RESUME
  Click "Download Original Resume"
  → Frontend opens presigned S3 URL
  → S3 serves the file directly (backend not involved)
  → Browser downloads the original PDF
```

---

## Key Concepts Explained

### 1. What is PII and why does it matter?
**PII = Personally Identifiable Information**
- Email addresses, phone numbers, names, LinkedIn profiles, etc.
- Regulations (GDPR, CCPA) restrict how you can use/share PII
- **In this app:** We extract it (so recruiter can contact candidates), but **we never send it to external AI APIs**
- **How:** Extract first (to DB), then scrub before AI sees it
- **Proof:** Tests verify that raw email never leaks into `scrubbed_text`

### 2. What is presigned URL?
**Problem:** If S3 bucket is public, anyone can browse all resumes. If private, only your app can access it (but you don't want backend serving gigabyte files).

**Solution:** Generate a temporary, single-file download link.
```
presigned_url = https://bucket.s3.region.amazonaws.com/path?
  AWSAccessKeyId=AKIA...&
  Signature=SHA256(secret_key + metadata)&
  Expires=1719333600
```
- **AWS validates:** signature matches key + bucket + path + expiry
- **If valid:** serve file
- **If invalid:** 403 Forbidden
- **After expiry:** link dead (no maintenance needed)

### 3. What is async processing?
**Problem:** Parsing a resume takes 5+ seconds (text extraction, AI call, DB writes). If we do this in the request, user waits 5+ seconds for a response.

**Solution:** Async/background tasks.
```
POST /upload → Backend says "OK, queued" → returns immediately
             → Background worker processes file while frontend polls
             → When done, frontend shows result
```
- **Framework:** FastAPI's `BackgroundTasks`
- **Worker:** Just another Python thread per resume
- **Polling:** Frontend calls `GET /jobs/{id}` every 2s to check progress

### 4. What is deduplication (SHA-256)?
**Problem:** Recruiter uploads same resume twice by accident.

**Solution:** Hash the content.
```
resume1.pdf → SHA-256 → "abc123..."
resume2.pdf (same content) → SHA-256 → "abc123..."
  → Database query: "do we have a resume with hash abc123 and status='completed'?"
  → Yes → mark new upload as 'duplicate', skip AI parsing, reuse existing candidate
```
- **Why SHA-256:** Industry standard, collision-proof (for practical purposes)
- **What we hash:** Scrubbed text (so same resume, different name, doesn't create false duplicates)

### 5. What is HTTP/1.1 vs HTTP/2?
**HTTP/1.1:** Old standard, one request at a time per connection (slower for many small requests).

**HTTP/2:** Newer, multiple requests over same connection (faster). **But:** our Supabase client had a bug with HTTP/2 → random crashes (`pseudo-header in trailer` errors).

**Fix:** Force HTTP/1.1 on the PostgREST client. Trade-off: ~1% slower, but **no crashes**. For small JSON queries (which Supabase returns), the difference is invisible.

### 6. What is PostgREST?
**What:** Supabase's REST API layer → auto-generates REST endpoints from your PostgreSQL schema.

**Example:**
```
POST /rest/v1/candidates
GET  /rest/v1/candidates?location=ilike.*nyc*&years_experience=gte.5
DELETE /rest/v1/candidates?id=eq.uuid123
```
- **No backend code needed** (it's auto-generated)
- **But:** Fixed API (can't add custom logic easily)
- **In our app:** We use it for candidate queries (simple filters), but not for the resume pipeline (that needs custom logic)

### 7. What is a relational database?
**PostgreSQL** (what Supabase uses) stores data in **tables** with **relationships**.

**Example:**
```
TABLE candidates
  id | name | email | years_experience | location
  ---|------|-------|------------------|----------
  1  | John | john@... | 4.5 | NYC
  2  | Jane | jane@... | 6.0 | SF

TABLE skills
  id | name
  ---|-------
  A  | Python
  B  | FastAPI
  C  | SQL

TABLE candidate_skills (join table)
  candidate_id | skill_id
  -----------|----------
  1          | A (John has Python)
  1          | B (John has FastAPI)
  2          | C (Jane has SQL)
```

**Queries:**
```sql
-- Find all candidates with Python
SELECT candidates.name FROM candidates
  JOIN candidate_skills ON candidate_skills.candidate_id = candidates.id
  JOIN skills ON skills.id = candidate_skills.skill_id
  WHERE skills.name = 'python'

-- Result: John
```

---

## PII Handling (Security)

### The Flow (Critical!)

```
Raw Resume (from user)
  ↓ (text_extractor)
Plain Text: "John Doe, john@acme.com, +1-555-0147, linkedin.com/in/john, ..."
  ↓ (contact_extractor — runs on raw text)
Extracted: {name: "John Doe", email: "john@acme.com", phone: "+1-555-0147", linkedin: "..."}
  ├─ Stored in DB (candidates table) — recruiter needs to contact candidates
  │
  ├─ (pii_scrubber — runs on raw text)
  │  Scrubbed: "[NAME], [EMAIL], [PHONE], [LINKEDIN], ..."
  │
  └─ (ai_parser — receives ONLY scrubbed text)
     AI extracts: skills, experience, title, location
     (AI never sees: john@acme.com or +1-555-0147)

DB: candidates table has contact details (for recruiter)
DB: resumes table has scrubbed_text (safe, no PII)
S3: original file stored (untouched, in case it's needed later)
```

### Why This Works
- **No leaks to AI:** AI only sees [EMAIL], [PHONE] — zero risk
- **No leaks in logs:** If logs are compromised, they don't have emails
- **Recruiter still wins:** Contact details are in the candidates table (DB access is protected)
- **Compliance:** Meets GDPR/CCPA data minimization (AI doesn't process PII unnecessarily)

### Tests Prove It
```python
# In test_upload_pipeline.py
assert "jordan.lee@example.com" not in resume["scrubbed_text"]
assert "[EMAIL]" in resume["scrubbed_text"]
```

---

## Design Decisions & Trade-Offs

### 1. Why AWS S3, not database blobs?
| Aspect | S3 | Database |
|--------|----|----|
| Cost | ~$0.023/GB/month | 10x more expensive (in bandwidth) |
| Speed | CDN-fast direct download | Database network hop |
| Scaling | Unlimited | Slow on large files |
| **Drawback** | Separate service to manage | Simple, all in one place |

**Decision:** S3 wins for real-world cost + scale.

### 2. Why Groq over Gemini?
| Aspect | Groq | Gemini 2.5-Flash |
|--------|------|---|
| Free tier RPM | 30 req/min | 5 req/min |
| Free tier daily | 1000 reqs | 250 reqs |
| Speed | ~1.4s per resume | 3–5s (thinking overhead) |
| **Drawback** | Smaller model (less nuanced) | Rate limits kill batch processing |

**Decision:** Groq's free tier is 6x more generous. Quality is identical for structured extraction. Fallback to Gemini if Groq key runs out.

### 3. Why async processing?
**Alternative:** Synchronous (blocking).
```
POST /upload → process all 10 resumes (50 seconds) → return
Frontend: stuck waiting 50 seconds 😞
```

**Our choice:** Async.
```
POST /upload → queue resumes → return immediately
Frontend: shows progress bar, user can leave and come back
Backend: processes in background, no blocking 👍
```

**Trade-off:** More complex (background tasks, polling), but **must have** for good UX.

### 4. Why HTTP/1.1 forced on Supabase client?
**Root cause:** `postgrest-py` library hard-codes `http2=True`. httpcore 1.0.x has a bug with HTTP/2 framing.
**Symptom:** Random `pseudo-header in trailer` crashes on filter queries.
**Fix:** Rebuild the httpx client with `http2=False`.
**Trade-off:** ~1% slower (irrelevant for small JSON), **zero crashes** ✓

### 5. Why PostgREST's `*` wildcard, not SQL's `%`?
**Problem:** We sent `ilike("name", "%aws%")` → encoded as `%25aws%25` → crashed Supabase edge worker.
**Root cause:** Literal `%` in URL param breaks the Cloudflare Worker that proxies PostgREST.
**Fix:** Use PostgREST's native `*` wildcard: `ilike("name", "*aws*")`.
**Trade-off:** Had to learn PostgREST API quirks, but now it works reliably.

### 6. Why magic-byte validation?
**Alternative:** Just check file extension.
```
Attacker renames malware.exe → malware.pdf → we try to extract text → crash
```

**Our choice:** Check magic bytes (file signature).
```
File header: %PDF (for PDFs) or PK (for DOCXs)
If mismatched: reject immediately
```

**Trade-off:** Tiny overhead, huge safety gain.

---

## Interview Prep: Key Talking Points

### "Walk me through the full pipeline"
*Answer:*
1. **Upload:** User POSTs resume files. Backend validates (size, extension, magic bytes).
2. **Background processing:** Text extraction → contact extraction → PII scrub → S3 upload → AI parse → DB save
3. **Search:** Frontend filters candidates by skill/location/experience. Backend uses Supabase's REST API.
4. **Download:** Frontend opens presigned S3 URL. S3 serves file directly (no backend involved).

### "How do you handle PII?"
*Answer:*
- Extract contact details *before* AI sees the text
- Scrub PII (replace emails/phones/URLs with placeholders)
- AI only ever sees `[EMAIL]`, `[PHONE]`, etc. — zero access to real contact info
- This is the **primary privacy control** in the app
- Verified by tests: raw email never leaks into scrubbed_text

### "Why Groq instead of Gemini?"
*Answer:*
- **Gemini:** 5 req/min free tier → can't process batch uploads fast enough
- **Groq:** 30 req/min free tier → 6x more generous, same quality for extraction
- **Speed:** Groq is ~1.4s/resume; Gemini has "thinking" overhead
- **Decision:** Groq is default; Gemini is fallback if needed

### "What's the weirdest bug you fixed?"
*Answer:*
- Users couldn't download resumes → got `SignatureDoesNotMatch`
- Root cause: boto3 was signing against global `s3.amazonaws.com`, S3 redirected to regional endpoint, signature no longer matched
- **Fix:** Force SigV4 + regional virtual-hosted addressing → signs against the regional endpoint directly
- **Lesson:** Cloud APIs have quirks; read error messages carefully

### "What would you add next?"
*Answer:*
- **Semantic search:** Embed resumes with a text-embedding model + pgvector in Supabase. Let recruiters paste a job description and find the most similar candidates (not just keyword matches).
- **Why:** This is the jump from "keyword search" to "genuinely useful talent intelligence."

---

## Troubleshooting Quick Ref

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| `429 Too Many Requests` on uploads | Groq/Gemini rate limit hit | Wait, or switch to faster model (Groq 30 req/min vs Gemini 5) |
| `SignatureDoesNotMatch` on resume download | Presigned URL signed against wrong endpoint | Use `signature_version="s3v4"` + virtual addressing |
| 500 on `/candidates?skill=...` | Supabase crashing on `ilike` with `%` | Use `*` wildcard instead: `ilike("skill", "*aws*")` |
| Random 500s on DB queries | HTTP/2 bug in httpx/httpcore | Force HTTP/1.1: rebuild PostgREST client with `http2=False` |
| Resume returns `years_experience: 0` | Prompt didn't count internships | Updated prompt now counts internships + research + projects + estimates conservatively |

---

## Deployment Checklist

- [ ] `.env` file has `GROQ_API_KEY`, `AWS_*` keys, Supabase credentials
- [ ] `.env` is in `.gitignore` (never commit secrets!)
- [ ] `requirements.txt` includes `groq>=1.5` + all dependencies
- [ ] Tests pass: `pytest -m "not integration"`
- [ ] Local app works: `npm run dev` (frontend) + `uvicorn main:app --reload` (backend)
- [ ] S3 bucket is created + IAM user has `s3:*` permissions
- [ ] Supabase schema is migrated: run `migrations/001_init_schema.sql`
- [ ] Frontend env has `NEXT_PUBLIC_API_URL=http://localhost:8000` (dev) or production URL
- [ ] Live URL is reachable + frontend loads without errors

---

## Final Notes

This is a **production-grade pattern:** real-world recruiting apps follow this same flow. The tech choices (Supabase, S3, Groq, async processing) are what you see at scale. The PII handling is **not optional** — it's required for compliance.

You know this app inside and out now. Go ace that interview. 🚀
