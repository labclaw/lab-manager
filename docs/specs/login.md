# Login — Page Spec

| | |
|---|---|
| **Route** | `/login` |
| **Status** | Built — working |
| **Priority** | — (complete) |
| **Stitch Screen** | `Login — Lab Manager` |

---

## API Contract

### POST /api/auth/login
Authenticate user.
```json
// Request
{ "email": "admin@lab.org", "password": "password123" }
```
```json
// Response (200)
{ "email": "admin@lab.org", "name": "Admin", "role": "admin" }
// Sets session cookie
```
```json
// Error (401)
{ "detail": "Invalid credentials" }
```

### GET /api/auth/me
Check current session.
```json
// Response (200): user object
// Response (401): not authenticated → redirect to /login
```

---

## Component Architecture

```
LoginPage
├── BrandingHeader (Lab Manager logo + name)
├── LoginForm
│   ├── EmailInput
│   ├── PasswordInput
│   ├── RememberMeCheckbox
│   ├── SubmitButton
│   └── ErrorMessage
└── Footer
```

---

## UI States

| State | Display |
|-------|---------|
| Default | Empty form |
| Submitting | Button disabled + spinner |
| Error | Error message below form |
| Success | Redirect to `/` |

---

## Acceptance Criteria

- [x] Email + password form submits to POST /api/auth/login
- [x] Error message shown on invalid credentials
- [x] Successful login redirects to dashboard
- [x] Session persists via cookie
