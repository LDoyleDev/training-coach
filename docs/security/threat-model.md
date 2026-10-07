# Threat model

Principle: models only produce data that is validated and shown to the user; they never run
actions (ADR-0007). Only three things are reachable from outside: the Telegram bot (owner
only), the dashboard (Cloudflare), and in phase 3 the MCP endpoint (Cloudflare, OAuth).

## Assets

Workout history, body measurements and photos (personal), bot token, Groq key, Claude OAuth
token, session cookies, the Pi itself (shared with Vybe).

## Threats and controls

| Threat | Entry point | Controls | Tests / checks |
| --- | --- | --- | --- |
| T1: Strangers using the bot | Telegram commands, button presses and typed text | Commands carry the `owner_only` filter; typed text combines it with `TEXT & ~COMMAND`; it answers a pending /settings question or is parsed as a workout log by the bounded rule parser and shown for confirmation before anything is saved (ADR-0007); log buttons carry only a random draft token; button presses (which can't take a filter) check the sender first and get no answer otherwise. Queue buttons name their session and are re-checked against the queue; settings buttons carry the value they set, so an old or forged press can't act on another session or flip a setting the wrong way | Stranger tests for every command, button and typed text (`tests/bot/`); stale-button tests |
| Voice notes leave the Pi | Voice -> Groq transcription | Only the owner's voice notes are sent (owner filter), with the plan's exercise names as a spelling prompt; capped at 2 min / 5 MB and refused if the size is unknown; a 45 s deadline per transcription; held in memory only, never written to disk; transcripts shown to the owner but never logged; dedicated Groq key; voice is off until the key is set | Voice tests: strangers ignored, transcript and key absent from logs, caps refused before download |
| Prompt injection in a log | Voice/text -> rule parser (and the model fallback, #59) | Owner-only bot; transcripts and text reach only the bounded rule parser; the model fallback gets no tools, answers a strict schema whose names are an enum of the plan, and its output is re-parsed by the same rules and used only if clean (ADR-0023); confirm before save | Parser hostile-input tests; hostile transcript test (`tests/bot/test_voice.py`); invented, extreme, smuggled and injected model answers (`tests/bot/test_model_fallback.py`) |
| One person seeing or changing another's data (ADR-0026) | Every per-person table | Sessions are bound to a user (ADR-0029): every ORM select and delete on an owned table (sets included) is filtered to that user, new rows are stamped with them, and writing another user's row, a set on another's workout, changing a row's owner, or a bulk insert/update raises. An unbound session refuses to read or bulk-change per-person rows unless a shared check asks for every user explicitly; rows it adds must name their user. String SQL and `session.connection()` are not covered and not used for per-person data. The bot's sessions are bound to the owner, linked to the allowed Telegram account. Until invites exist there is one user | Two-user scope tests (`tests/db/test_user_scope.py`): reads, sets alone, lookups by id, cached statements, refused writes, bulk deletes; per-user seed test |
| Prompt injection via other Claude connectors | Phase 3 MCP | Narrow tools (read, log, propose); no delete; plan changes need Telegram approval; audit log | MCP tool tests; audit log assertions |
| Injected instructions in issues/PRs | Claude GitHub Action | OWNER-only triggers; no forks; no `pull_request_target`; restricted tools; secrets never in prompts | Workflow review in PRs |
| Secret leakage | Repo, logs, chats | `.env` ignored; gitleaks pre-commit + CI; Claude Code denied `.env`; `SecretStr`; httpx URL logging silenced | CI gitleaks; config repr test |
| Web attacks | Dashboard | Cloudflare WAF + rate limits; HMAC-verified Telegram auth with freshness; HttpOnly/Secure/SameSite cookies; CSP and security headers; ORM only | Security header test; auth tests |
| Share-link abuse | Share URLs | 32-byte random, hashed at rest, expiry, revocable, read-only, no measurements/photos | Share view tests |
| Container escape / lateral movement to Vybe | App container | Non-root, read-only FS, cap_drop ALL, no-new-privileges, own network, localhost-only port | Compose review |
| Host compromise | Pi | SSH over Tailscale only; firewall deny inbound; unattended security upgrades | Deploy runbook checklist |
| Supply chain | PyPI, npm, Actions | Lockfiles; Dependabot; pip-audit + npm audit; Actions pinned to SHAs; CodeQL | CI security job |
| Bot token theft | Telegram | Allowlist blocks data access; rotate via BotFather | Rotation runbook |
| Data loss | SD card | WAL, nightly backups, off-device copy, restore drill | Restore rehearsal per release |

## Review cadence

Revisit this document at the start of each phase and whenever a new external surface is added.
