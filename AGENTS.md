# Repository Guidelines

## Project Structure & Module Organization
Keep the public entry point `index.html` in the repository root so contributors can open the blog without tooling. Reusable layout snippets belong in `partials/`, and site-wide styles in `styles/` (e.g., `styles/main.css` plus component-specific files such as `styles/header.css`). Place the runtime bootstrap files under `src/runtime/` (e.g., `src/runtime/app.js`) and feature sections under `src/sections/`. Commit media assets to `assets/` (subfolders for `img/`, `fonts/`, `icons/`) to keep binary files out of the root. Add demos or reference material under `examples/` or `tests/fixtures/` rather than mixing them into production paths.

## Build, Test, and Development Commands
The site is static, so no build step is required. For predictable previews start a lightweight server from the project root with `python -m http.server 8000` or `npx serve .`. When preparing deployment-ready files, you can generate a compressed bundle via `npx html-minifier --input-dir . --output-dir dist`. Only run `npm install` if you introduce new tooling, and commit the matching config files (`.htmlhintrc`, `.stylelintrc`, etc.).

## Coding Style & Naming Conventions
Indent HTML, CSS, and JS with two spaces; tabs tend to create noisy diffs in mixed editors. Use BEM-flavored selectors for CSS components (`.hero__title`, `.hero__cta`) and reserve utility classes in `styles/utilities.css` for repeated patterns. Stick to lowercase-kebab filenames (`blog-post.html`, `dark-mode.css`), camelCase for JavaScript identifiers, and SCREAMING_SNAKE_CASE for constants. Keep inline scripts short; anything longer than five lines should live in `src/runtime/` and be included with `<script defer>`.

## Iconography
Source every UI icon (except the primary logo) from the iconfont assets under `assets/icons/`. Define reusable utilities in `styles/utilities.css` and reference those classes in markup instead of embedding emoji or bespoke SVG paths.

## Testing Guidelines
Automate regressions as they appear: smoke tests and accessibility checks should live in `tests/`. Run `npx htmlhint .` and `npx stylelint "styles/**/*.css"` before every pull request; update the corresponding configs when you change rules. Document manual QA steps in `tests/README.md`, and verify the blog renders correctly in Chromium, Firefox, and a mobile viewport before sign-off.

## Commit & Pull Request Guidelines
There is no existing history, so adopt Conventional Commits (`feat: add hero carousel`, `fix: correct nav focus states`). Group related work into focused commits and wrap message bodies at 72 characters. Pull requests must include a concise summary, screenshots or GIFs for UI changes, and a checklist covering local verifications (`python -m http.server`, `npx htmlhint .`). Reference related issues with `Closes #ID`, and request review once linting passes locally.

## Content & Assets Workflow
Draft new articles in `posts/YYYY-MM-DD-title.md`, then link them through `index.html` or dedicated listing pages. Compress imagery below 200 KB using `npx imagemin-cli assets/raw --out-dir assets/img` to protect load times. Never commit secrets; keep environment-specific tokens in `.env.local` and document required variables in `docs/configuration.md` without committing the file itself.
