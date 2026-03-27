# v0.1.10 (2026-03-26)

## Bug Fixes
- **rbac**: Check lockout in session middleware, reset counter on login (#264)
- **rbac**: Use is None check for staff id to avoid falsy 0 bug (#265)
- **tests**: Fix 7 failing RAG mock tests and BDD search path (#271)
- **security**: Add RBAC permission guards to alerts and telemetry routes (#272)
- **web**: Make header search, bell, and user name functional (#268)
- **web**: Implement Alerts page and remove Review dead buttons (#270)
- **web**: Remove dead buttons and fake data from Orders page (#269)

## Features
- **rbac**: Add permission guards to all route endpoints (Phase C) (#252)
- **team**: Team management - invite, roles, deactivate (#253)
- **web**: Mobile responsive UI (#246)
- **barcode**: Barcode/QR web camera scanning for inventory lookup (#249)
- **intake**: Email-to-intake agent for vendor email processing (#248)
- **products**: PubChem product enrichment (#245)
- **web**: Vendors and Products pages with CRUD (#242)
- **rbac**: RBAC core with 7 roles and permissions (#247)
- **import**: Bulk CSV import for inventory, products, vendors (#243)

## CI
- Add retry loop to Docker publish verify step (#239)
- Sanitize test fixtures and pin CI action SHAs (#238)
