# AI Full-Text Screening (CLI + Desktop GUI)

This repository is a local-first Python tool for AI-assisted paper screening.

It includes:
- CLI: `python -m src.main ...`
- Desktop GUI: `python -m src.gui_app`

The GUI supports two workflows:
- Full-text Screening (PDF/DOCX/TXT folder)
- Title-Abstract Screening (Excel `.xlsx`)

Both workflows reuse the same provider/config foundations and keep local SQLite databases plus export files per project workspace.

## Folder Structure

```text
config/
data/
input/
  local_papers/
output/
src/
tests/
.env.example
requirements.txt
README.md
```

## Installation

1. Use Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install dependencies.

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item config\settings.yaml.example config\settings.yaml
```

macOS/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
cp config/settings.yaml.example config/settings.yaml
```

If PowerShell blocks venv activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Windows Double-Click GUI Start

After installation, you can start the GUI by double-clicking:

- `start_gui.bat`

What the script does:
- Switches to project root
- Activates `.venv`
- Runs `python -m src.gui_app`
- Keeps the window open on exit so errors are visible

Optional hidden launcher:
- `start_gui_hidden.vbs` (no visible console window)

If startup fails, run manually in PowerShell:

```powershell
python -m src.gui_app
```

## Environment Variables

- `GEMINI_API_KEY`: Gemini key
- `GOOGLE_API_KEY`: Gemini fallback key
- `OPENAI_COMPATIBLE_API_KEY`: OpenAI-compatible key
- `DEEPSEEK_API_KEY`: DeepSeek key
- `ANTHROPIC_API_KEY`: Anthropic/Claude key
- `GEMINI_MODEL`: optional override for configured Gemini model
- `APP_ENV`: optional environment label

## Screening Modes

### Full-text Screening

- Input: folder of `.pdf` / `.docx` / `.txt`
- Default folder: `input/local_papers/`
- Prompt file: `config/criteria_prompt.txt`

### Title-Abstract Screening

- Input: `.xlsx` file
- First sheet is used
- Required format:
  - Column A = `Title`
  - Column B = `Abstract`
  - Column C+ are ignored by the current program
- Prompt file: `config/title_abstract_criteria_prompt.txt`
- Current MVP does not include column-mapping UI; if columns are different, adjust the Excel file first
- Prompt should follow the program's allowed values for `Decision` and `Exclude reason` exactly

## CLI Commands

Run from repository root:

```powershell
python -m src.main scan
python -m src.main run
python -m src.main export
python -m src.main retry-failed
python -m src.main rescreen-doi --dois "10.1000/one|10.1000/two" --delimiter "|"
python -m src.main status
```

Behavior summary:
- `scan`: discover files, register in SQLite, mark duplicates
- `run`: scan + screen queueable papers + export full log
- `retry-failed`: rerun retryable failures + export
- `export`: regenerate full Excel/CSV from SQLite
- `rescreen-doi`: rerun by exact DOI + overwrite conclusion + export
- `status`: show summary counts

Quick verification:

```powershell
python -m src.main --help
python -m src.main scan
python -m src.main status
python -m pytest
```

## Desktop GUI

Start GUI:

```powershell
python -m src.gui_app
```

GUI supports:
- Screening mode switch:
  - `Full-text Screening`
  - `Title-Abstract Screening`
- Select input folder
- Select input Excel (Title-Abstract mode)
- Choose provider (`gemini`, `deepseek`, `openai_compatible`, `anthropic`)
- Set API key, model, base URL
- Edit and save prompt
- Start Screening / Retry Failed / Auto Start / Stop Screening
- Live table refresh (file/status/decision/error)
- Export Excel/CSV
- Refresh status
- Open project output folder
- Clear current project history
- View logs

Stop behavior:
- Stop is cooperative
- The current paper finishes first
- Queue stops before the next paper
- SQLite state remains consistent for resume

## Project Workspace Isolation

### Full-text Projects

GUI uses isolated workspaces by input folder:
- One `input_dir` maps to one `project_id`
- Each project has its own SQLite, Excel/CSV, logs, and snapshots
- Switching input folder switches the current project automatically
- Switching back to an older input folder restores its history
- Export in GUI only exports the current project

Project id format:
- `<input_folder_name>_<short_hash_of_absolute_path>`
- Example: `papers_a83f21`

Output structure:

```text
output/
  projects/
    <project_id>/
      screening.sqlite
      screening_log.xlsx
      screening_log.csv
      run.log
      error.log
      criteria_prompt_snapshot.txt
      settings_snapshot.json
```

### Title-Abstract Projects

- One Excel path maps to one `ta_<...>` project id
- Project id format: `ta_<excel_stem>_<short_hash>`
- Workspace path: `output/projects/<ta_project_id>/`

Output structure:

```text
output/
  projects/
    <ta_project_id>/
      title_abstract.sqlite
      title_abstract_screening_log.xlsx
      title_abstract_screening_log.csv
      original_input_snapshot.xlsx
      title_abstract_prompt_snapshot.txt
      settings_snapshot.json
      run.log
      error.log
```

Notes:
- Switching Excel switches the current title-abstract project automatically
- Switching back restores previous history
- `Clear Current Project History` only clears the current project workspace and does not delete the original Excel
- `original_input_snapshot.xlsx` is local-only; do not upload private data, SQLite files, outputs, or API keys to GitHub

Clear Current Project History:
- Deletes the current project's SQLite, exports, logs, and snapshots
- Does not delete original papers in the input folder

## Provider Configuration

`config/settings.yaml(.example)` includes:
- `provider.name`
- `gemini`
- `openai_compatible`
- `deepseek`
- `anthropic`

Supported provider names:
- Gemini: `gemini`, `google`, `google_gemini`
- OpenAI-compatible: `openai_compatible`
- DeepSeek: `deepseek`
- Anthropic: `anthropic`, `claude`

Practical GUI defaults:
- `gemini`: leave `base_url` empty and set model explicitly
- `deepseek`: `base_url` can be empty or custom
- `openai_compatible`: usually requires explicit `base_url`
- `anthropic` / `claude`: `base_url` can be empty and model should be set explicitly

## Using Other AI Providers

Current GUI providers:
- `gemini`
- `deepseek`
- `openai_compatible`
- `anthropic`

If you want to use Kimi, GLM, Qwen, OpenRouter, Together, SiliconFlow, or other third-party platforms:
- If the platform supports OpenAI-compatible APIs, choose `openai_compatible` in the GUI
- Fill `base_url` from that platform's official docs
- Fill the model name required by that platform
- Fill the API key from that platform
- Do not commit real API keys to this repository

Examples:
- Gemini:
  - provider = `gemini`
  - base_url = empty
- DeepSeek:
  - provider = `deepseek`
  - base_url = empty or custom
- Anthropic / Claude:
  - provider = `anthropic`
  - base_url = empty or custom
- Kimi / Moonshot:
  - provider = `openai_compatible`
  - base_url/model from Moonshot docs
- GLM / Zhipu:
  - provider = `openai_compatible`
  - base_url/model from Zhipu docs
- Qwen / DashScope:
  - provider = `openai_compatible`
  - base_url/model from DashScope/Qwen docs
- Other platforms:
  - provider = `openai_compatible`
  - base_url/model/api_key from provider docs

Notes:
- Not all platforms are 100% compatible
- If errors occur, first verify `base_url`, model, API key, quota/billing, account permissions, region settings, and provider docs
- `openai_compatible` is the general integration path for unsupported providers

## GUI Run Modes

Start Screening:
- Runs the normal queue logic for the current project

Retry Failed:
- Full-text: retries `TEXT_FAILED_RETRY` / `SCREEN_FAILED_RETRY`
- Title-Abstract: retries failed retryable rows in the current Excel project
- Does not rerun `DONE`

Auto Start:
- Phase 1: retry failed papers in the current project
- Phase 2: screen `NEW` only
- Designed to avoid reprocessing retry-failed items in phase 2

## Prompt Management

- Full-text prompt: `config/criteria_prompt.txt`
- Title-Abstract prompt: `config/title_abstract_criteria_prompt.txt`
- GUI uses `PromptManager` to load/save UTF-8 prompt text by mode
- Prompt validation requires a non-empty string
- Saved prompt persists across restarts because it is written back to disk

## API Key Storage

GUI settings path:
- Windows: `%APPDATA%\ai_fulltext_screening\app_config.json`
- macOS/Linux: `~/.ai_fulltext_screening/app_config.json`

API key behavior:
- Prefer keyring when available
- If keyring is unavailable, save under `api_keys` in user `app_config.json`
- Fallback to environment variables when no saved key exists

Never commit real API keys to repository files.

## Resume Behavior

Queueable statuses:
- `NEW`
- `TEXT_FAILED_RETRY`
- `SCREEN_FAILED_RETRY`

Skipped statuses:
- `DONE`
- `MANUAL_DONE`
- `SKIPPED_DUPLICATE`

Interrupted runs recover stale `TEXT_EXTRACTED` and `SCREENING` rows into retryable states on the next run.

## Deduplication

Identity matching order:
1. DOI
2. content hash
3. file hash
4. fallback fingerprint

## Export Behavior

Exports are always fully regenerated from SQLite.

Full-text export columns:
1. `Title`
2. `DOI`
3. `Decision`
4. `Exclude reason`
5. `Construct`
6. `Note`
7. `Model`

Title-Abstract export columns:
1. `Title`
2. `Abstract`
3. `Decision`
4. `Exclude reason`
5. `Construct`
6. `Note`
7. `Model`
8. `Status`
9. `Error`

If you see `Invalid Exclude reason`:
- Model output did not match the allowed `Exclude reason` list
- Save a stricter Title-Abstract prompt and click `Retry Failed`

If Gemini returns `503 UNAVAILABLE` or high-demand errors:
- This is usually temporary provider-side load
- Those rows stay retryable; run `Retry Failed` later

Defaults:
- Excel: `output/screening_log.xlsx`
- CSV: `output/screening_log.csv`

Title-Abstract defaults inside the current `ta_...` project workspace:
- Excel: `title_abstract_screening_log.xlsx`
- CSV: `title_abstract_screening_log.csv`
- The original Excel is never modified in place

`Model` column:
- Stores the actual provider/model used for that row
- Format example: `gemini / gemini-2.5-flash`
- Legacy rows created before this feature may have an empty model

## Logging

- `output/run.log`
- `output/error.log`

Raw model responses are optionally stored in `screening_runs` when enabled.

## Local Verification Commands

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest
python -m src.main --help
python -m src.main status
python -m src.gui_app
```

Manual GUI validation checklist:
1. Choose input folder A, run Start Screening, Export.
2. Choose input folder B, run Start Screening, Export.
3. Switch back to A and confirm A history remains.
4. Click Retry Failed and verify only retryable failed rows are processed.
5. Click Auto Start and verify retry phase then new-only phase.
6. Open Project Output Folder and verify workspace files.
7. Clear Current Project History and verify only current project data is cleared.
8. Switch to Title-Abstract mode, choose a test `.xlsx`, run Start Screening.
9. Verify `title_abstract_screening_log.xlsx/.csv` are generated in the current `ta_...` project.
10. Switch to another Excel and confirm history isolation.

## Optional Packaging (PyInstaller)

For a quick local packaging attempt:

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name AI-Screening-GUI src\gui_app.py
```

Packaging behavior can vary by OS and Python environment, so test the generated app on your target machine.

## License

- **MIT License**
