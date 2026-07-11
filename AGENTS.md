# Repository Guidelines

## Project Structure & Module Organization

HeadScroll is a Windows-only Python desktop application. `src/main.py` is the entry point and coordinates capture, inference, control, and the PySide6 UI. Keep domain code in the existing packages: `capture/`, `tracking/`, `calibration/`, `processing/`, `control/`, `injection/`, `ui/`, and `utils/`. Default settings live in `config/default_config.json`; local overrides belong in the ignored `config/config.json`. Store icons and MediaPipe models under `assets/`, and maintenance scripts under `tools/`. Architecture and product notes are the Markdown documents at the repository root.

## Build, Test, and Development Commands

Run commands from the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\main.py
python -m compileall -q src
python -m pip install -r requirements-dev.txt
pyinstaller --noconfirm src\EyeScroll.spec
```

The first three commands create the environment, install runtime dependencies, and launch the app. `compileall` is the lightweight syntax check. Install development dependencies before using PyInstaller; it produces the Windows bundle in `dist/` and temporary files in `build/`.

## Coding Style & Naming Conventions

Use Python 3.10+ features, four-space indentation, UTF-8, and existing type hints. Follow PEP 8 naming: `snake_case` for functions, modules, and variables; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants. Keep UI code in `src/ui` and platform-specific input handling in `src/injection`. Prefer small changes that reuse existing helpers and dependencies. No formatter or linter is configured, so preserve the surrounding style and avoid unrelated formatting.

## Testing Guidelines

There is currently no automated test suite or coverage threshold. For logic changes, add focused `test_*.py` tests under a new `tests/` directory when practical, using the standard-library `unittest` module unless the project adopts another runner. Always run `python -m compileall -q src`. For camera, calibration, scrolling, or UI changes, also perform a Windows smoke test and document the tested mode and target application in the pull request.

## Commit & Pull Request Guidelines

Recent history uses short imperative subjects, such as `Update usage instructions in README.md`, with occasional Conventional Commit prefixes such as `chore:`. Keep each commit focused and describe the user-visible outcome. Pull requests should include a concise summary, verification steps, linked issues when applicable, and screenshots or a short recording for UI changes. Do not commit `config/config.json`, logs, virtual environments, `build/`, or `dist/`.
