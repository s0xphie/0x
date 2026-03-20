# Codeletteria: PDF Archive Ingestor + Networked Progress Journal

**Date Created:** March 18, 2026  
**Status:** Archive + Network Service Ready  
**Scope:** PDF ingestion, analysis, artifact detection, and progress journaling

---

## What is This?

This repository is a **general-purpose PDF ingestion and tracking system**. It is designed to:

1. **Ingest any PDF archive** (research papers, reports, manuals, etc.)
2. **Extract text and detect extraction artifacts** (especially math formatting issues)
3. **Produce structured progress output** (JSON event stream + `archive_progress.pdf`)
4. **Expose a network API** so other agents can query status and subscribe to events

It includes:

- **Archive:** A set of sample PDFs for analysis
- **Analysis tools:** Python scripts for extraction, comparison, and reporting
- **Runtime service:** A Rust service that discovers PDFs, parses them, and emits JSON events
- **Progress journal:** A writable JSON/PDF log that agents can append to for tracking progress

### The Story

Three mathematical papers (on sandpile groups, integer linear programming for sandpile configurations, and recursive functions) were extracted to text using automated tools. The tools partially succeeded—basic math symbols were recovered (ℓ, ∞, →, ≃), but **embedded font codes got mangled** (`/circleplustextt`, `/summationdisplay`, etc.).

This archive documents those findings in detail, **and provides a Rust program that transforms the archive itself into a service**: a network-aware system that discovers, processes, and streams JSON descriptions of the PDFs to interested clients, announcing itself as it works.

### Use Cases

- 📚 **Research archive ingestion**: Automatically discover and extract text from science papers.
- 🧪 **Extraction quality monitoring**: Track when OCR/extraction fails and what tokens are mangled.
- 🤖 **Agent coordination**: Multiple tools can write to the same progress journal.
- 🔁 **Data pipeline staging**: Use the event stream to trigger downstream processing or validation.

---

## Quick Reference

| Component | Purpose | Language | Status |
|-----------|---------|----------|--------|
| **PDFs** | Source documents (sample archive) | N/A | ✅ Present |
| **Python Scripts** | Extract, compare, and report on text quality | Python 3.12 | ✅ Complete |
| **Analysis Reports** | Detailed findings + artifacts | JSON/Text | ✅ Generated |
| **Rust Service** | Networked PDF ingestor + API | Rust | ✅ Running |
| **Progress Journal** | Writable JSON + auto-generated PDF log | JSON/PDF | ✅ Enabled |

---

## The PDFs

### PDF Inventory

| File | Pages | Extraction Status | Math Issues | Quality |
|------|-------|------------------|-------------|---------|
| `Sandpile_groups_of_supersingular_isogeny_graphs.pdf` | 25+ | ⚠️ Partial | 121 artifacts on 18 pages | Fair |
| `Computing_sandpile_configurations_using_integer_li.pdf` | 8 | ⚠️ Partial | 19 artifacts on 5 pages | Fair |
| `Recursive_Functions.pdf` | ? | ✅ Clean | 0 artifacts | Good |

### Extraction Quality Findings

**What worked:**
- ✅ Unicode math symbols (ℓ, ∞, ≃, →, ∈, Δ)
- ✅ Numbered equations and theorem statements
- ✅ Main text flow and paragraph structure
- ✅ pdftotext method outperformed PyPDF2

**What didn't:**
- ❌ Embedded font glyphs → mangled LaTeX codes
- ❌ Complex multi-line formulas had spacing issues
- ❌ ~140 total artifact tokens across problematic pages

**Root cause:** PDFs embed custom fonts for math rendering. When PyPDF2's glyph mapping fails, it returns literal PostScript/LaTeX codes instead of Unicode characters.

---

## Archive Contents

### Debug Folder

`debug/` contains troubleshooting resources and a command-oriented debug guide.

- `debug/debug_troubleshoot.md` — step-by-step command checklist for running, debugging, and inspecting the service.
- `debug/debug_troubleshoot.pdf` — the same guide in PDF form (for quick reading or printing).

> Note: Rust debug logging (via `RUST_LOG=debug`) is often the fastest way to understand how the service is progressing and why it may not be writing `archive_progress.*` correctly.

---

## Archive Contents

### Analysis Reports (Python-generated)

```
scripts/
├── ocr_summary_report.txt          ⭐ START HERE (human-readable)
├── ocr_summary_report.json         (structured artifact data)
├── problem_pages.json              (which pages have artifacts)
├── compare_report.json             (detailed PyPDF2 vs pdftotext)
├── extract_pypdf2.json             (raw PyPDF2 extraction)
├── pdftotext_supersingular.txt     (clean extraction, Sandpile)
└── pdftotext_alfaro.txt            (clean extraction, Computing)
```

### Python Utilities

```
scripts/
├── extract_pdfs.py                 (PyPDF2 wrapper)
├── find_problem_pages.py           (artifact detection)
├── compare_texts.py                (extraction comparison)
├── generate_summary_report.py      (report generator)
└── ocr_paddle.py                   (OCR wrapper - not completed)
```

### Environment

```
.venv/                              (Python virtual environment)
└── packages: PyPDF2, pdf2image, paddleocr
```

---

## Progress Journal (JSON + PDF)

This project maintains an **append-only progress journal** that agents can read and write to.

- `archive_progress.json` — a growing event log in JSON (one array of events).
- `archive_progress.pdf` — auto-generated human-readable report that updates whenever new events are appended.

Agents can contribute by appending events to `archive_progress.json`, and the service regenerates the PDF automatically on each update.

---

## The Rust Service: PDF Ingestor + Network Journal

### Why Rust?

The **PDF Network Digester** is a Rust-based service that turns your PDF archive into a **networked ingestion and tracking system**. Instead of static files, your archive becomes a **living, talking node** that:

- 🔍 **Discovers** all PDFs on startup
- 📊 **Processes** each one, extracting text and detecting artifacts
- 📡 **Streams** every action as JSON events
- 📝 **Maintains a progress journal** (JSON log + generated PDF)
- 🌐 **Broadcasts** state via HTTP API
- 🤝 **Announces** itself to the network

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  PDF Network Digester (Rust)                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Discover    │───→│ Process PDFs  │───→│ Extract Text │   │
│  │ PDFs        │    │ Detect Math   │    │ Metadata     │   │
│  └─────────────┘    └──────────────┘    └──────────────┘   │
│         │                                          │         │
│         └──────────────────┬───────────────────────┘        │
│                            │ Events (JSON)                   │
│                            ↓                                 │
│                  ┌─────────────────────┐                     │
│                  │ Event Stream        │                     │
│                  │ → stdout (real-time)│                     │
│                  │ → HTTP API (query)  │                     │
│                  └─────────────────────┘                     │
│                    ↓                                         │
│            ┌──────────────────────┐                          │
│            │ HTTP API (port 3000) │                          │
│            ├──────────────────────┤                          │
│            │ GET /health          │                          │
│            │ GET /state           │                          │
│            │ GET /events          │                          │
│            └──────────────────────┘                          │
│                    ↓                                         │
│            Network / Clients                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Features

✅ **Recursive PDF Discovery** — walks entire directory tree  
✅ **Automated Artifact Detection** — finds the `/circleplustextt` tokens  
✅ **Fallback Extraction** — pdftotext first, then PyPDF2  
✅ **JSON Event Stream** — every action emitted as structured JSON  
✅ **HTTP API** — real-time state queries + event log  
✅ **Self-Describing** — generates unique ID, announces capabilities  
✅ **Async / Fast** — Tokio-based concurrent processing  

### Running the Program

#### Setup (first time)

```bash
# Install Rust (if not present)
bash setup.sh

# This will:
# - Install Rust via rustup
# - Install pdftotext (poppler-utils)
# - Build the release binary
```

#### Run

```bash
# Option 1: Via cargo
cargo run --release

# Option 2: Direct binary
./target/release/pdf-digester
```

Server listens on `http://127.0.0.1:3000`.

#### Inspect Events (streaming)

```bash
# Watch real-time JSON events
cargo run --release 2>&1 | grep '^\{'

# Or capture to file (JSONL format)
cargo run --release 2>&1 | grep '^\{' > events.jsonl
```

### HTTP API

#### GET /health
```bash
curl http://localhost:3000/health
```
**Response:** `{"status":"ok"}`

#### GET /state
```bash
curl http://localhost:3000/state | jq
```
**Response:**
```json
{
  "id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
  "version": "0.1.0",
  "status": "running",
  "created_at": "2026-03-18T14:32:00Z",
  "uptime_secs": 125,
  "pdfs_found": 3,
  "pdfs_processed": 3,
  "current_file": null,
  "total_text_extracted": 450000,
  "errors": []
}
```

#### GET /events
```bash
curl http://localhost:3000/events | jq '.[0:5]'
```
**Response:** Array of all events (limited sample shown):
```json
[
  {
    "id": "evt-001",
    "timestamp": "2026-03-18T14:32:00Z",
    "event_type": {"type": "startup"},
    "source": "a1b2c3d4",
    "data": {"version": "0.1.0"}
  },
  {
    "id": "evt-002",
    "timestamp": "2026-03-18T14:32:00.1Z",
    "event_type": {"type": "pdf_discovered", "path": "./Sandpile_groups...pdf"},
    "source": "a1b2c3d4",
    "data": {"path": "./Sandpile_groups...pdf"}
  },
  {
    "id": "evt-005",
    "timestamp": "2026-03-18T14:32:01.2Z",
    "event_type": {"type": "pdf_parsing_complete", "path": "...", "pages": 25, "text_length": 45000},
    "source": "a1b2c3d4",
    "data": {"pages": 25, "text_length": 45000}
  },
  {
    "id": "evt-006",
    "timestamp": "2026-03-18T14:32:01.3Z",
    "event_type": {"type": "math_artifact_detected", "source": "...", "artifact": "/circleplustextt", "count": 121},
    "source": "a1b2c3d4",
    "data": {"artifact": "/circleplustextt", "count": 121}
  }
]
```

### Event Types

The Rust program emits structured events for every action:

| Event | When | Payload |
|-------|------|---------|
| `startup` | Program starts | version |
| `pdf_discovered` | PDF file found | path |
| `pdf_parsing_start` | Starting to extract | path |
| `pdf_parsing_complete` | Extraction done | pages, text_length |
| `pdf_parsing_error` | Extraction failed | path, error |
| `math_artifact_detected` | Found mangled token | artifact, count |
| `scan_complete` | All PDFs processed | total_files, succeeded, failed |

---

## How They Work Together

### Python Scripts (Archive Analysis)

1. **One-time setup:** Discover and analyze PDFs
2. **Output:** Reports on extraction quality + comparison metrics
3. **Run once:** Results saved to `scripts/*.json` and `scripts/*.txt`
4. **Purpose:** Understand the problem (mangled math artifacts)

```bash
.venv/bin/python scripts/find_problem_pages.py
.venv/bin/python scripts/generate_summary_report.py
```

### Rust Program (Live Service)

1. **Continuous operation:** Service runs and listens on HTTP
2. **Real-time discovery:** Finds and processes PDFs as they're accessed
3. **Event stream:** Every action announced as JSON
4. **Network-aware:** Can broadcast state and accept queries from clients
5. **Purpose:** Transform the archive into an intelligent, self-describing system

```bash
cargo run --release
# Listens on http://127.0.0.1:3000
# Streams events to stdout
```

### Integration

The Rust program **uses** the Python infrastructure:

- Falls back to `scripts/extract_pdfs.py` if `pdftotext` isn't available
- Detects the same artifact tokens that Python scripts identified
- Benefits from the analysis already done (knows which pages are problematic)

It also maintains a **progress journal** that agents can read/write:

- `archive_progress.json` is append-only and can be modified by external agents
- `archive_progress.pdf` is regenerated automatically after each new entry
- This allows multiple tools/agents to cooperatively document processing state

---

## Repository Layout

```
./
├── Cargo.toml                  # Rust service dependencies
├── README.md                   # This document
├── archive_progress.json       # Live event journal (generated)
├── archive_progress.pdf        # Generated progress report (PDF)
├── scripts/                    # Python analysis tools
├── src/                        # Rust service source
└── *.pdf                       # Sample PDFs to ingest
```

## Extending the System / Agent Integration

- Agents can append to `archive_progress.json` to record progress or annotations.
- The Rust service generates `archive_progress.pdf` for easy human inspection whenever the journal updates.
- Agents can read `/state` and `/events` via HTTP to react to progress in real time.

---

## Next Steps

1. Add more PDFs to the archive and watch the service process them.
2. Build agent(s) that append structured entries to `archive_progress.json` (e.g. validation results).
3. Enhance extraction (OCR, layout parsing, metadata extraction) and log findings in the journal.
