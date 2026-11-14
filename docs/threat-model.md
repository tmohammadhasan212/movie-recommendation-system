# Threat model

| Threat | Current control | Remaining limitation |
|---|---|---|
| Credential theft | Argon2id, HttpOnly cookies, short access lifetime, refresh rotation, session revocation, single-flight browser renewal | No password recovery flow; renewal coordination is scoped to one browser tab |
| CSRF | SameSite cookies plus per-session double-submit token checked server-side | Origin checking could add defense in depth |
| Account enumeration | Registration always returns a generic accepted response | Timing has not been formally tested |
| Brute force | Atomic Redis-backed shared limits fail closed, expose bounded metrics, alert on outages, and return `Retry-After` | Fixed windows are coarser than sliding-window limits |
| Broken object authorization | User ID comes only from the authenticated session | More negative API tests are needed |
| Forged analytics | Event allowlist, CSRF, consent, bounded timestamps, server-selected user | No anonymous event ingestion |
| Dependency compromise | Exact direct versions, resolved lockfiles, CI audit and secret scan | Container SBOM/signing not implemented |
| Model poisoning/corruption | Training boundary excludes app users; artifact schema and SHA-256 validation; safetensors | Source archive is trusted after published MD5/operator SHA-256 |
| Sensitive logs | Structured fields avoid email, token, query text and event payload | Reverse-proxy access-log retention is operator controlled |

Security review should include authorization, rate-limit outage, session replay, duplicate delivery, malformed artifacts, and deletion/export tests before public deployment.
