# Auto-generated API Types

This directory contains TypeScript types auto-generated from the FastAPI OpenAPI schema.

## Usage

```bash
# Generate from running dev server
npm run generate-types

# Generate from a saved openapi.json file
npm run generate-types:file
```

## How it works

1. FastAPI automatically produces an OpenAPI schema at `/openapi.json`
2. `openapi-typescript` converts that schema into TypeScript interfaces
3. `openapi-fetch` provides a type-safe fetch client using those interfaces

The generated `api.generated.ts` file should be committed so CI and other
developers don't need a running backend to build the frontend.

Re-run `npm run generate-types` whenever backend models or endpoints change.
