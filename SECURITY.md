# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.x.x   | :white_check_mark: |

## Reporting a Vulnerability

Please report security issues via [GitHub Security Advisories](https://github.com/labclaw/lab-manager/security/advisories/new).

Include:

- Description of the vulnerability
- Steps to reproduce
- Affected component (API, database, document intake, etc.)
- Potential impact assessment

## Response Timeline

| Stage              | Target            |
|--------------------|-------------------|
| Acknowledgment     | 48 hours          |
| Initial assessment | 5 business days   |
| Fix or mitigation  | 30 days           |
| Public disclosure  | After fix release |

## Scope

### In scope

- API authentication and authorization bypass
- Injection vulnerabilities (SQL, command, path traversal)
- Database access control bypass
- Document processing vulnerabilities (malicious file uploads, path traversal)
- VLM/OCR provider credential exposure
- Credential or API key exposure in logs or responses
- Privilege escalation in admin panel
- Cross-site scripting (XSS) or CSRF in web UI

### Out of scope

- Denial of service against local-only services
- Bugs in third-party dependencies (report upstream)
- Social engineering

## Data Security Considerations

Lab Manager processes sensitive laboratory documents (invoices, packing lists, certificates of analysis). Security vulnerabilities that could result in:

- **Unauthorized access to lab inventory data**
- **Document tampering or audit log manipulation**
- **Exposure of vendor/supplier information**
- **API key leakage to VLM/OCR providers**

are treated as **high severity** regardless of software impact assessment.

## Secret Rotation

- API tokens and deploy SSH keys: rotate every 90 days.
- Emergency rotation: within 24 hours of suspected compromise.
- Rotation process:
  - Generate new credential and store in secret manager.
  - Deploy with both old+new credentials accepted during a short overlap window.
  - Remove old credential and verify health checks + audit logs.
- Never log secret values or full token identifiers.
