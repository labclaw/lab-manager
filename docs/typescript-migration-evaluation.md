# TypeScript Migration Evaluation

**Date**: 2026-03-26
**Status**: Not recommended

## Current Architecture

| Layer    | Language   | Framework          |
|----------|------------|--------------------|
| Frontend | TypeScript | React 19 + Vite 8  |
| Backend  | Python     | FastAPI + SQLModel  |

The project is already a **TypeScript frontend + Python backend** stack.
"Migrating to TypeScript" would mean rewriting the backend in Node.js/TS.

## Why NOT to migrate the backend

### 1. Ecosystem fit

The backend relies heavily on Python-native libraries with no equivalent in
the Node.js ecosystem:

- **SQLModel / SQLAlchemy** - The most mature Python ORM; Prisma and Drizzle
  are not comparable in capability (composite keys, complex joins, raw SQL
  escape hatches, async session management).
- **Alembic** - Battle-tested migration framework; Node alternatives
  (knex, Prisma Migrate) are less flexible.
- **instructor / litellm / google-genai** - AI extraction pipeline depends on
  Python-first SDKs; JS equivalents are less mature.
- **Pydantic** - Powers both validation and OpenAPI schema generation; Zod is
  comparable but switching gains nothing.

### 2. Scale of effort

| Metric            | Value     |
|-------------------|-----------|
| Python files      | ~220      |
| Python LOC        | ~10,400   |
| Test files        | ~123      |
| API endpoints     | 82        |
| DB models         | 14        |

A full rewrite would take weeks to months with high regression risk.

### 3. Type safety already exists

- Backend: `mypy` + Pydantic (via SQLModel) provide static + runtime type checks.
- Frontend: TypeScript with hand-written interfaces in `web/src/lib/api.ts`.

### 4. AI/ML pipeline

The document intake pipeline (OCR, VLM extraction, consensus) uses Python
CLI tools (`claude`, `gemini`, `codex`) and Python SDKs. Porting this to
Node.js would be a separate, larger project with no benefit.

## Recommended Alternative: OpenAPI Type Generation

Instead of migrating, **auto-generate frontend TypeScript types from the
backend's OpenAPI schema**. This gives the same end result (full-stack type
safety) without rewriting anything.

### Setup (implemented in this PR)

1. `openapi-typescript` generates TS interfaces from `/openapi.json`
2. `openapi-fetch` provides a type-safe HTTP client using those interfaces
3. `npm run generate-types` regenerates types when backend models change

### Benefits

| Aspect         | Before (hand-written)        | After (generated)            |
|----------------|------------------------------|------------------------------|
| Type drift     | Silent runtime errors        | Compile-time errors          |
| New endpoints  | Manual type + client code    | Regenerate + auto-complete   |
| Maintenance    | Grows with endpoint count    | Zero marginal cost           |

### Migration path for existing code

The hand-written types in `web/src/lib/api.ts` (~155 LOC) can be gradually
replaced by imports from `types/api.generated.ts`. Both can coexist during
transition — no big-bang rewrite needed.

## Conclusion

The backend is Python because the problem domain (lab data, AI extraction,
complex relational models) demands Python's ecosystem. The frontend is already
TypeScript. OpenAPI type generation bridges the two with zero rewrite risk.
