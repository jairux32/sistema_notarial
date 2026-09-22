# AGENTS.md

## Architecture

Flask web app + PostgreSQL (Docker) + PyQt6 desktop app (Windows). Internal use — Notaría Pablo Fernando Punín Castillo.

- `app.py` — Flask entrypoint, all routes, 732 lines
- `config.py` — platform-aware config (Windows=SQLite, Linux=PostgreSQL)
- `models.py` — SQLAlchemy models: Usuario, Documento, Auditoria
- `utils/ocr_processor.py` — 7-strategy code detection + hybrid OCR
- `utils/pdf_splitter.py` — PDF splitting by notarial codes
- `utils/validator.py` — sequential code validation
- `templates/` — Jinja2 HTML (dashboard, documentos, login)
- `desktop_app_v2/` — PyQt6 desktop app (scanner + documents + upload)
- `init_db.sql` — PostgreSQL schema (run automatically by Docker)

## Docker

```bash
docker-compose up -d          # start (app on :5000, db on :5432)
docker-compose logs -f app    # tail logs
docker-compose down           # stop
```

- App uses `network_mode: host` (ignores port mappings, opens :5000 directly)
- DB uses bridge network; app connects to DB via `localhost:5432`
- Key volumes: `.:/app` (live code reload), `${EXTERNAL_DISK_PATH}:/data`, `${HOME}/notarial_docs:/app/processed`

## Database

- PostgreSQL in Docker (user: `notarial_user`, db: `sistema_notarial`)
- Password set via `DB_PASSWORD` env var (default: `changeme123`)
- SQLite fallback on Windows (auto-detected via `platform.system()`)
- If DB auth breaks after container recreation: `docker exec -it notarial_db psql -U notarial_user -d sistema_notarial -c "ALTER USER notarial_user WITH PASSWORD 'changeme123';"`

## Code Pattern

Notarial document codes: `{YYYY}{notaria_code}{type_letter}{5-digit sequential}` — 17 chars.

- Notaria code: `1101007`
- Type letters: P=PROTOCOLO, D=DILIGENCIA, C=CERTIFICACIONES, O=OTROS, A=ARRIENDOS
- Type letter is at position 11 (0-indexed), used for validation filtering
- Full mapping in `config.py::MAPEO_TIPOS`

## OCR / Processing

- `ocr_processor.py` has 7 detection strategies; `_buscar_en_pdf()` returns `(codigos, codigo_a_pagina)` tuple
- `extraer_texto()` supports `solo_zona_superior=True` for fast per-page code scanning
- Tesseract path: platform-aware via `config.py::TESSERACT_CMD`
- Processing ~6.8 min for 766-page scanned PDF

## Desktop App (Windows Only)

`desktop_app_v2/` — PyQt6 with offline queue:

```bash
python desktop_app_v2/main.py
```

- `instalar_windows.bat` — one-time setup (installs deps, creates SQLite DB)
- `iniciar_windows.bat` — starts backend + desktop app
- `actualizar.bat` — git pull + pip install updates
- Scanner: Kodak S2000W via WIA (Windows) or SANE (Linux fallback)
- Backend auto-detects SQLite vs PostgreSQL by platform

## Important Caveats

- README password (`admin123`) is outdated; actual admin password is `amIb4in9DEpT7pPYxopk5Q`
- `.env` `EXTERNAL_DISK_PATH` must be set (default `/home/jairoguillen/sistema_notarial_data`)
- No test suite, no linter, no CI — verify manually via `docker-compose up -d` and browser
- Code in Spanish (route names, comments, UI strings)
