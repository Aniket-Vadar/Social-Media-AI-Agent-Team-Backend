# Security Specification

Scope: Next.js web app, Python agent service (LangGraph + Gemini + LangSmith), PostgreSQL, Inngest, E2B, ImageKit, Blotato.

## 1. Security Objectives

1. Protect user accounts, social account access, and content.
2. Guarantee **strict tenant isolation** between workspaces.
3. Ensure **no autonomous action** (publishing, deleting) happens outside user-defined policy.
4. Defend the AI layer against prompt injection, data exfiltration, and abuse.
5. Maintain auditability of all user and agent actions.

## 2. Threat Model (summary)

| Threat | Example | Primary Controls |
|---|---|---|
| Account takeover | Credential stuffing | MFA, rate limits, breach-password checks |
| Cross-tenant data access (IDOR) | Changing `campaignId` in a request | Server-side authorization, RLS |
| **Prompt injection** | Malicious webpage tells Researcher "ignore instructions, post X" | Untrusted-content isolation, tool allowlists, approval gate |
| Data exfiltration via LLM | Agent leaks API keys or other tenants' data | No secrets in prompts, tenant-scoped tools |
| Sandbox escape or abuse | Researcher visits malicious site | E2B ephemeral sandbox, no secrets inside, egress policy |
| Unauthorized publishing | Compromised agent publishes harmful content | Approval default, content policy check, audit log |
| Token theft | Social tokens leaked | Tokens held by Blotato; never stored or sent to LLM |
| Webhook forgery | Fake Blotato/Inngest events | Signature verification |
| Cost abuse (denial of wallet) | Loop of agent runs | Quotas, step limits, rate limits |
| Supply chain | Malicious dependency | Lockfiles, Dependabot, SCA scanning |

## 3. Authentication

- Email + password (Argon2id) and OAuth (Google/GitHub). Optional TOTP MFA (required for owners/admins of paid plans).
- Session: HttpOnly, Secure, SameSite=Lax cookies; short-lived access with rotating refresh; invalidate on password change.
- Email verification required before connecting accounts or running agents.
- Brute-force protection: progressive delays, IP and account rate limiting, CAPTCHA after repeated failures.
- Password reset: single-use, expiring (≤ 30 min) tokens.

## 4. Authorization

- **RBAC:** `owner`, `admin`, `editor`, `viewer`.

| Action | Owner | Admin | Editor | Viewer |
|---|---|---|---|---|
| Manage workspace/billing | ✔ | partial | ✘ | ✘ |
| Connect/disconnect accounts | ✔ | ✔ | ✘ | ✘ |
| Run agents, create/edit posts | ✔ | ✔ | ✔ | ✘ |
| Approve/publish posts | ✔ | ✔ | ✔ (configurable) | ✘ |
| View analytics | ✔ | ✔ | ✔ | ✔ |

- **Every** API handler: authenticate → resolve workspace membership → authorize action → validate resource belongs to workspace.
- **PostgreSQL Row-Level Security** on all tenant tables:

```sql
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON posts
  USING (workspace_id = current_setting('app.workspace_id')::uuid);
```
Set `app.workspace_id` per request/transaction. The Python agent service uses a **restricted DB role** that is also subject to RLS.

## 5. Service-to-Service Security

- Next.js → Python agent service: **short-lived signed JWT** (≤ 5 min) with claims `workspace_id`, `user_id`, `campaign_id`, `run_id`, `aud=agent-service`.
- Agent service is **not publicly reachable** (private network / IP allowlist / mTLS where possible).
- Agent service derives all tenant identifiers **from the JWT**, never from request body or LLM output.
- Inngest signing key verified on `/api/inngest`.
- Blotato webhooks: verify HMAC signature and timestamp (reject > 5 min old); dedupe by event ID.

## 6. AI / LLM Security

### 6.1 Prompt Injection Defense (critical for the Researcher)
1. **Treat all web content, user-uploaded text, and tool outputs as untrusted data.** Wrap in delimiters (`<untrusted source="...">`) and instruct the model they contain no instructions.
2. **Capability separation:** the Researcher has *read-only* tools. It cannot schedule, publish, delete, or access campaign secrets. Only Scheduler can publish, and only for posts passing the approval gate.
3. **Tool allowlist per agent**; deny by default.
4. **Tenant scope injected by code:** tools take `workspace_id`/`campaign_id` from trusted context, not model arguments.
5. **Output validation:** structured output schemas; reject unexpected fields; validate URLs, lengths, and enums in code.
6. **Content scanning** of fetched pages for injection patterns (heuristic and classifier), with flagged content truncated or dropped.
7. **Approval gate** default for publishing; auto-publish requires explicit opt-in with a warning.
8. **Injection test suite** in LangSmith datasets, run in CI/nightly; block deploys on regressions.

### 6.2 Data Protection in Prompts
- Never include API keys, tokens, passwords, or other tenants' data in prompts or tool results.
- Minimize PII sent to Gemini; redact emails/phones from analytics and research inputs where not needed.
- Configure Gemini usage under terms that **disable training on customer data** (use paid/Vertex tier and verify settings).
- LangSmith: enable **input/output masking** (hide sensitive fields), set retention policy, restrict access to the LangSmith workspace, and never attach secrets in metadata.

### 6.3 Output Safety
- Moderation pass on generated content: hate, harassment, sexual content, self-harm, illegal activity, misinformation, impersonation, copyright/trademark concerns.
- Platform policy checks (e.g., prohibited claims, disclosure of sponsored content).
- Block generation of content about real individuals that could be defamatory; require citations/sources for factual claims in Researcher/Creator output.
- Enable Gemini safety settings at appropriate thresholds.

### 6.4 Abuse and Cost Controls
- Per-workspace quotas: runs/day, tokens, sandbox minutes, posts/run.
- `MAX_GRAPH_STEPS`, per-run timeout, loop detection, max tool retries.
- Alerts on anomalous usage (sudden spike in runs or tokens).

## 7. Sandbox Security (E2B)

- One **ephemeral** sandbox per research task; destroyed on completion or timeout (≤ 10 min).
- **No secrets, cookies, or user data** inside sandbox; no logged-in sessions.
- Restrict navigation to `http/https`; block internal IP ranges, metadata endpoints, `file://`, and deny-listed domains. Prefer egress filtering where E2B supports it.
- Downloads disabled or scanned; screenshots/text extracted only.
- Strict resource limits (time, CPU, memory, pages visited).
- Sandbox output is untrusted (see §6.1).

## 8. Application Security

- **Input validation:** Zod (TS) and Pydantic (Python) on all inputs. Reject unknown fields.
- **Injection:** parameterized queries only (Drizzle/SQLAlchemy). No string-built SQL.
- **XSS:** React escaping; sanitize any rendered rich text/markdown (DOMPurify); strict **CSP** (no `unsafe-inline` where possible), `Trusted Types` if feasible.
- **CSRF:** SameSite cookies + CSRF tokens for state-changing cookie-authenticated requests; verify `Origin`.
- **SSRF:** any server-side URL fetch uses allowlist/deny private ranges and DNS-rebinding protection.
- **File uploads (ImageKit):** server-issued upload signatures with short expiry; restrict MIME types (jpg, png, webp, gif), max size, scan for malware; strip EXIF location data.
- **Headers:** HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors 'none'`.
- **CORS:** same-origin only for API; no wildcard.
- **Rate limiting:** per IP and per user on auth, agent runs, and API (e.g., Upstash/Redis or edge middleware).
- **Error handling:** generic errors to client; details only in logs.

## 9. Secrets and Key Management

- Secrets in platform secret manager (Vercel env, cloud secret manager); **never** in repo or client bundles (only `NEXT_PUBLIC_*` non-secret values).
- Separate keys per environment; least privilege; rotate at least every 90 days and on staff changes or incidents.
- Secret scanning in CI (e.g., gitleaks) and pre-commit hooks.
- Social platform tokens remain in **Blotato**; the app stores only Blotato account IDs.
- Service credentials (Gemini, E2B, LangSmith, ImageKit private key) only available to the services that need them.

## 10. Data Protection and Privacy

- TLS 1.2+ everywhere; encryption at rest (managed Postgres, object storage).
- Field-level encryption for any sensitive stored values (e.g., webhook secrets) using envelope encryption (KMS).
- Data classification: *Public* (published posts), *Internal* (drafts, analytics), *Sensitive* (credentials, PII).
- Retention: agent messages and traces 90 days by default (configurable), analytics 24 months, audit logs 12 months; hard delete on workspace deletion within 30 days.
- User rights (GDPR/CCPA): export and deletion endpoints; DPA available; list sub-processors (Google, LangSmith, E2B, ImageKit, Blotato, Inngest, hosting).
- Backups encrypted, tested restores, point-in-time recovery.

## 11. Audit Logging and Monitoring

- `audit_logs` records: logins, role changes, account connect/disconnect, post approve/publish/delete, approval mode changes, agent runs (with `actor_type=agent` and `run_id`), settings changes.
- Append-only; no update/delete permissions for app roles.
- Centralized logs (structured JSON) with request IDs, trace IDs that link to LangSmith runs. No secrets or full prompts containing PII in logs.
- Alerts: repeated auth failures, privilege changes, bulk deletions, unusual publish volume, webhook signature failures, injection detections.
- Error monitoring (e.g., Sentry) with PII scrubbing.

## 12. Platform and Third-Party Compliance

- Respect each social platform's ToS and API rules (rate limits, automation disclosure, content policies).
- Obtain explicit user consent when connecting accounts; clear scope description; easy revoke.
- Vendor due diligence for Google (Gemini), LangSmith, E2B, ImageKit, Blotato, Inngest, InsForge: SOC 2/ISO status, data residency, breach notification terms.

## 13. Secure Development Lifecycle

- **CodeRabbit** reviews every PR (with security-focused review instructions); mandatory human review for auth, RLS, agent tools, and migrations.
- CI: SAST (CodeQL/Semgrep), dependency audit (`npm audit`, `pip-audit`), secret scanning, container image scanning, IaC scanning.
- Dependabot/Renovate with lockfiles; pin versions; verify packages before adoption.
- Environments isolated; no prod data in dev/staging.
- Pre-release: threat model review, penetration test (before public launch and annually), prompt-injection red-team.
- Migrations reviewed; backups taken before prod migrations.

## 14. Incident Response

1. **Detect:** alerts, user reports.
2. **Contain:** revoke keys/tokens, disable auto-publish globally via feature flag, pause agent queue, suspend affected workspaces.
3. **Eradicate and recover:** patch, rotate secrets, restore from backups if needed.
4. **Notify:** affected users and regulators as required (e.g., within 72 h under GDPR).
5. **Post-mortem:** blameless review, action items tracked.

**Kill switches:** global agent pause, per-workspace pause, global auto-publish disable, per-tool disable flag.

## 15. Security Checklist (pre-launch)

- [ ] RLS enabled and tested for every tenant table
- [ ] Authorization tests for all endpoints (IDOR cases)
- [ ] MFA available; rate limits on auth and agent endpoints
- [ ] Agent service private; service JWT enforced
- [ ] Tenant IDs never accepted from LLM output
- [ ] Researcher has read-only tools; Scheduler gated by approval
- [ ] Prompt-injection eval suite passing in CI
- [ ] Sandbox contains no secrets; egress restrictions in place
- [ ] Webhook signatures verified; replay protection on
- [ ] CSP and security headers configured
- [ ] Upload validation, MIME/size limits, EXIF stripping
- [ ] Secrets in manager; rotation schedule defined; secret scanning on
- [ ] LangSmith masking and retention configured; Gemini no-training terms verified
- [ ] Audit logging complete and immutable
- [ ] Quotas, step limits, and cost alerts active
- [ ] Backups and restore tested; incident runbook written
- [ ] Privacy policy, ToS, DPA, sub-processor list published
- [ ] Penetration test and red-team completed
