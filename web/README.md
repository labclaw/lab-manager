# Lab Manager React Frontend

This directory contains the React + TypeScript frontend for Lab Manager.

Current status:
- It is an in-progress replacement for the backend-served UI in [`../src/lab_manager/static/`](../src/lab_manager/static/).
- FastAPI only serves the React app when build output exists in [`../src/lab_manager/static/dist/`](../src/lab_manager/static/dist/).
- The browser setup flow documented in the main release notes still assumes the backend-served UI is the canonical surface.

## Commands

```bash
cd web
bun install
bun run dev
```

Development proxy targets the backend on `http://localhost:8000`.

To produce a build that FastAPI can serve:

```bash
cd web
bun run build
```

This writes assets into `../src/lab_manager/static/dist`.

## Release Guidance

Do not treat `web/` as the default shipping surface until feature parity is explicit.
Before shipping the React app, verify at minimum:
- first-run setup
- login and logout
- dashboard, documents, review, inventory, and orders flows
- asset serving from `/assets`
