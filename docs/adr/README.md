# Architecture Decision Records

Accepted ADRs are binding. To change one, write a new ADR that supersedes it (`/adr` in Claude
Code). Template: [template.md](template.md).

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-python-fastapi-single-process.md) | Python + FastAPI, one process for API and bot | Accepted |
| [0003](0003-docker-compose-on-pi.md) | Deploy with Docker Compose on the Pi | Accepted |
| [0004](0004-react-vite-tailwind-dashboard.md) | Dashboard in React + Vite + Tailwind | Accepted |
| [0005](0005-git-workflow-and-releases.md) | Git workflow, commit convention and releases | Accepted |
| [0006](0006-session-queue-scheduling.md) | The plan is an ordered queue; missed sessions shift back | Accepted |
| [0007](0007-llm-output-is-untrusted-data.md) | LLM output is untrusted data, never an action | Accepted |
| [0008](0008-groq-transcription-and-parsing.md) | Groq for transcription and fallback parsing | Accepted |
| [0009](0009-telegram-long-polling-owner-only.md) | Telegram via long polling, owner-only | Accepted; single allowed user superseded by 0059 |
| [0010](0010-sqlite-on-sd-card.md) | SQLite on the SD card, with nightly backups | Accepted |
| [0011](0011-claude-github-action-subscription.md) | Claude GitHub Action on the owner's subscription | Accepted |
| [0012](0012-dashboard-auth-and-share-links.md) | Dashboard auth via Telegram, read-only share links | Accepted; sign-in superseded by 0036, share links by 0050 |
| [0013](0013-uv-for-python-dependencies.md) | uv and pyproject.toml for Python dependencies | Accepted |
| [0014](0014-multiple-workouts-per-day.md) | Several workouts per day | Accepted |
| [0015](0015-seed-failure-does-not-block-startup.md) | A failed plan seed does not block startup | Accepted |
| [0016](0016-queue-and-target-rules.md) | Queue edge cases and target rules | Accepted (targets superseded by 0027) |
| [0017](0017-plan-follows-huberman-protocol.md) | The training plan follows Huberman's Foundational Fitness Protocol | Accepted |
| [0018](0018-develop-in-wsl2-on-windows.md) | Develop in WSL 2 on the Windows desktop | Accepted |
| [0019](0019-public-plan-endpoint.md) | The bundled training plan is public at GET /api/plan | Superseded by 0041 |
| [0020](0020-generated-api-types.md) | Dashboard API types are generated from the OpenAPI schema | Accepted |
| [0021](0021-claude-code-guardrails.md) | Claude Code guardrails: hooks, review subagents, a lean CLAUDE.md | Accepted |
| [0022](0022-swap-and-rest-buttons.md) | What Swap and Rest today do to the queue | Accepted |
| [0023](0023-model-fallback-only-suggests.md) | The model fallback only suggests; the rule parser decides | Accepted |
| [0024](0024-backups-run-in-the-app-not-the-bot.md) | Backups run in the app, not the bot, and only a complete copy counts | Accepted |
| [0025](0025-personal-bests-and-progress-prompts.md) | Personal bests and the "ready to progress" prompt | Accepted |
| [0026](0026-multi-user-direction.md) | Built for one, designed for many | Accepted |
| [0027](0027-progressive-overload-step.md) | Progressive overload step of about 10% of the range | Accepted |
| [0028](0028-training-blocks.md) | Optional 4-week strength and hypertrophy blocks | Accepted |
| [0029](0029-sessions-bound-to-a-user.md) | Per-person data is scoped by binding the session to a user | Accepted |
| [0030](0030-deploy-releases-from-a-timer.md) | The Pi deploys new releases itself, from a timer | Accepted |
| [0031](0031-exercise-pairs-and-work-order.md) | Resistance sessions are done in fixed pairs, listed set by set | Accepted |
| [0032](0032-stretching-after-resistance.md) | Stretching after a resistance session is chosen for the muscles worked | Accepted |
| [0033](0033-logging-a-past-day.md) | A past day is logged with a date line, and catching up moves the queue | Accepted; extended by 0060 |
| [0034](0034-plan-changes-keep-history-per-exercise.md) | Plan changes keep history per exercise | Accepted |
| [0035](0035-web-app-first-telegram-for-reminders.md) | The web app is the main surface; Telegram is for reminders | Accepted |
| [0036](0036-sign-in-with-passkeys-and-a-telegram-link.md) | Sign in with passkeys, started and recovered with a Telegram link | Accepted |
| [0037](0037-baseline-tests-as-test-days.md) | Baseline tests are test days, defined in plan.toml, entered in the web app | Accepted |
| [0038](0038-test-days-wait-in-front-of-the-queue.md) | Test days stand in front of the queue while a round is due | Accepted |
| [0039](0039-progress-photos-in-the-database.md) | Progress photos are kept in the database, cleaned of their metadata | Accepted |
| [0040](0040-passkey-first-sign-in-with-telegram-recovery.md) | Passkey first, Telegram for recovery, and an alert for every sign-in change | Accepted |
| [0041](0041-the-site-is-private.md) | The site is private: no public pages | Accepted |
| [0042](0042-encrypted-off-site-backups.md) | Encrypted off-site backups on Cloudflare R2, kept 35 days | Accepted |
| [0043](0043-deploy-only-releases-github-signed.md) | The Pi deploys only releases GitHub signed | Accepted |
| [0044](0044-erase-all-my-data.md) | Erasing all my data: delete the person, cascade, start fresh | Accepted |
| [0045](0045-uptime-by-heartbeat.md) | Uptime monitoring by a heartbeat to Healthchecks.io | Accepted |
| [0046](0046-readiness-questions.md) | Readiness questions that advise, not block | Accepted |
| [0047](0047-bring-your-own-ai.md) | Bring your own AI | Accepted |
| [0048](0048-undo-the-last-change.md) | Undo the last change to the plan | Accepted |
| [0049](0049-confirm-with-fingerprint.md) | Confirm it's you with your fingerprint, without signing out | Accepted |
| [0050](0050-share-as-a-picture.md) | Share progress as a picture, not a link | Accepted |
| [0051](0051-hiit-timer-like-tabata-timer.md) | The HIIT timer works like Tabata Timer, with workouts saved in the browser | Accepted |
| [0052](0052-changing-today-on-the-web.md) | Changing today on the web: Rest, Push, Swap and Undo | Accepted |
| [0053](0053-daily-check-before-training.md) | A daily check before training: sleep, soreness, energy | Accepted |
| [0054](0054-connect-my-ai-built-in.md) | Connect my AI with a hand-written MCP and OAuth server in the app | Accepted |
| [0055](0055-band-import-through-health-connect-webhook.md) | Band data through Health Connect Webhook | Accepted |
| [0056](0056-keep-the-weekly-ai-comment-7-days.md) | Keep the weekly AI comment 7 days, for the web review | Accepted |
| [0057](0057-pace-setting.md) | A pace setting for how big a step the targets take | Accepted |
| [0058](0058-ai-proposes-logs-you-confirm.md) | A connected AI proposes logs; you save or discard them | Accepted |
| [0059](0059-invites-and-members.md) | Invite-only members, behind a switch that is off by default | Accepted |
| [0060](0060-log-any-day-and-ask-before-overwriting.md) | Log any day, any session, and ask before a day gets two | Accepted |
| [0061](0061-time-guided-sessions.md) | Time each set of a guided session | Accepted |
| [0062](0062-guided-mobility-flow.md) | Guide the mobility flow one movement at a time | Accepted |
| [0063](0063-mannequin-exercise-figures.md) | Exercise pictures are mannequins we draw from two poses | Accepted |
| [0064](0064-exercise-catalogue-and-fractional-sets.md) | Exercises name fixed muscles with weights; sets count fractionally | Accepted |
| [0065](0065-rest-by-transition.md) | Rest by transition: a quick switch inside a pair, a rest after it | Accepted |
| [0066](0066-block-after-the-run.md) | A block after a cardio session's run stays open that day | Accepted |
| [0067](0067-cardio-details-and-session-rpe.md) | A cardio log carries how hard it felt, and optionally distance, heart rate and start | Accepted |
| [0068](0068-today-shows-the-days-log.md) | Today shows what a day logged, with earlier days a tap away and their habits | Accepted |
| [0069](0069-plan-page-and-session-maps.md) | Plan gets its own tab, Tests moves into Body, each session has its own body map | Accepted |
| [0070](0070-our-own-android-reader.md) | Our own Android reader replaces HC Webhook as the bridge from Health Connect | Proposed |
| [0071](0071-equipment-and-places.md) | Each person lists their home kit; a gym has everything; steps lock by kit | Accepted |
| [0072](0072-load-and-double-progression.md) | Sets record their load; loaded exercises progress by reps, then weight | Accepted |
| [0073](0073-each-person-owns-their-sessions.md) | Each person owns their sessions; exercises are a shared catalogue | Accepted |
| [0074](0074-boxing-bell-timer-sound.md) | A boxing-ring bell is everyone's timer sound, for every guided timer | Accepted |
