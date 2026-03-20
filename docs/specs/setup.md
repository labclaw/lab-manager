# Setup Wizard — Page Spec

| | |
|---|---|
| **Route** | `/setup` (auto-shown when `needs_setup=true`) |
| **Status** | Built — working |
| **Priority** | — (complete) |
| **Stitch Screen** | `One-Click Setup Wizard` |

---

## API Contract

### GET /api/setup/status
Check if setup is needed.
```json
// Response
{ "needs_setup": true }
```

### POST /api/setup/complete
Create admin account.
```json
// Request
{
  "lab_name": "My Research Lab",
  "admin_name": "Dr. Smith",
  "admin_email": "smith@lab.org",
  "admin_password": "securepassword"
}
```
```json
// Response (200)
{ "message": "Setup complete", "email": "smith@lab.org" }
```
```json
// Error (400)
{ "detail": "Setup already completed" }
```

---

## Component Architecture

```
SetupPage
├── BrandingHeader
├── SetupForm
│   ├── LabNameInput
│   ├── AdminNameInput
│   ├── AdminEmailInput
│   ├── AdminPasswordInput
│   ├── ValidationMessages
│   └── SubmitButton ("Complete Setup")
└── SuccessRedirect (→ /login)
```

---

## UI States

| State | Display |
|-------|---------|
| Default | Empty form |
| Submitting | Button disabled + spinner |
| Validation error | Inline field errors |
| Complete | Redirect to /login |

---

## Acceptance Criteria

- [x] Form validates all fields before submit
- [x] POST /api/setup/complete creates admin account
- [x] Redirects to /login after success
- [x] Shows error if setup already completed
