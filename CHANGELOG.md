# Changelog

All notable changes are documented here by [release-please](https://github.com/googleapis/release-please)
from [Conventional Commits](https://www.conventionalcommits.org/). Versions follow
[SemVer](https://semver.org/).

## [0.9.0](https://github.com/LDoyleDev/training-coach/compare/v0.8.0...v0.9.0) (2026-10-07)


### Features

* **bot:** add the training block calendar and the warm-up prompt ([#81](https://github.com/LDoyleDev/training-coach/issues/81)) ([1147af4](https://github.com/LDoyleDev/training-coach/commit/1147af467a1cb7b2508944b6f98c79e1ede64f74))
* **domain:** strength blocks train one step harder at 4-8 reps ([#83](https://github.com/LDoyleDev/training-coach/issues/83)) ([39eee4b](https://github.com/LDoyleDev/training-coach/commit/39eee4b55d060dfa147f98f83398cb17e003cf24)), closes [#26](https://github.com/LDoyleDev/training-coach/issues/26)

## [0.8.0](https://github.com/LDoyleDev/training-coach/compare/v0.7.0...v0.8.0) (2026-10-07)


### Features

* **bot:** add /review with the week's sessions, sets per muscle and bests ([#79](https://github.com/LDoyleDev/training-coach/issues/79)) ([f056c24](https://github.com/LDoyleDev/training-coach/commit/f056c243da96731bf5c6a7ace4393fa7967af790))
* **bot:** send the weekly review every Sunday at 19:00 ([#80](https://github.com/LDoyleDev/training-coach/issues/80)) ([e429121](https://github.com/LDoyleDev/training-coach/commit/e4291216596e5fef0a210d4a72aae0a1d4d3019f)), closes [#73](https://github.com/LDoyleDev/training-coach/issues/73)
* **db:** bind sessions to a user and give every person their own rows ([#76](https://github.com/LDoyleDev/training-coach/issues/76)) ([b8ef45b](https://github.com/LDoyleDev/training-coach/commit/b8ef45b4d5428e7b71a3cbe0e212a9bedfa425a0))
* **db:** refuse per-person rows in an unbound session ([#78](https://github.com/LDoyleDev/training-coach/issues/78)) ([91c0fe6](https://github.com/LDoyleDev/training-coach/commit/91c0fe6cb434ad9774f6fd4046ec6abc350f973b)), closes [#72](https://github.com/LDoyleDev/training-coach/issues/72)


### Documentation

* ADR-0028 for training blocks; phase 2 steps linked to issues ([#75](https://github.com/LDoyleDev/training-coach/issues/75)) ([4ce96f0](https://github.com/LDoyleDev/training-coach/commit/4ce96f002a5c85e532aff3aeba63666f6c64ffd0))

## [0.7.0](https://github.com/LDoyleDev/training-coach/compare/v0.6.0...v0.7.0) (2026-10-07)


### Features

* **domain:** aim about 10% of the range higher each session ([#71](https://github.com/LDoyleDev/training-coach/issues/71)) ([218b336](https://github.com/LDoyleDev/training-coach/commit/218b336c72eb1a41c1ac8e83a1949f6f5ac54a11)), closes [#70](https://github.com/LDoyleDev/training-coach/issues/70)


### Documentation

* options for phase 2 decisions and a web app and health data proposal ([#67](https://github.com/LDoyleDev/training-coach/issues/67)) ([6b7baef](https://github.com/LDoyleDev/training-coach/commit/6b7baef9c585315b60199649aa76f1d68aceb19b))

## [0.6.0](https://github.com/LDoyleDev/training-coach/compare/v0.5.0...v0.6.0) (2026-10-07)


### Features

* **bot:** add /progress with each exercise's step, last session and best ([#65](https://github.com/LDoyleDev/training-coach/issues/65)) ([9c8d189](https://github.com/LDoyleDev/training-coach/commit/9c8d1899f275bfc4b5dccfb82e5cc02eb92babe1)), closes [#13](https://github.com/LDoyleDev/training-coach/issues/13)
* **bot:** report personal bests and offer to move up after a save ([#64](https://github.com/LDoyleDev/training-coach/issues/64)) ([15ceb1c](https://github.com/LDoyleDev/training-coach/commit/15ceb1cbbca8dc1ad059571df8f8b5575a9c20dc))

## [0.5.0](https://github.com/LDoyleDev/training-coach/compare/v0.4.0...v0.5.0) (2026-10-07)


### Features

* **bot:** log workouts by text with a confirm step ([#57](https://github.com/LDoyleDev/training-coach/issues/57)) ([e3fa439](https://github.com/LDoyleDev/training-coach/commit/e3fa439d23c2a93b79a22f32c39e746e7495ab1c))
* **bot:** log workouts by voice ([#60](https://github.com/LDoyleDev/training-coach/issues/60)) ([7daa1a0](https://github.com/LDoyleDev/training-coach/commit/7daa1a0c044203e5aa826b8ca0aed328c2ff0cdd))
* **db:** save confirmed workout logs once ([#55](https://github.com/LDoyleDev/training-coach/issues/55)) ([ca4396b](https://github.com/LDoyleDev/training-coach/commit/ca4396b0f99b069933cfa37e9ef99aa3cc3de546))
* **infra:** back up the database nightly with rotation and a pull script ([#63](https://github.com/LDoyleDev/training-coach/issues/63)) ([bb179c7](https://github.com/LDoyleDev/training-coach/commit/bb179c76fb666c38c28d9340bf90786b93d92975)), closes [#14](https://github.com/LDoyleDev/training-coach/issues/14) [#39](https://github.com/LDoyleDev/training-coach/issues/39)
* **parser:** let a model read logs the rules can't, as a suggestion only ([#61](https://github.com/LDoyleDev/training-coach/issues/61)) ([29abf47](https://github.com/LDoyleDev/training-coach/commit/29abf473133b4bc0ad14153dd8d5360158db6cd1))

## [0.4.0](https://github.com/LDoyleDev/training-coach/compare/v0.3.0...v0.4.0) (2026-10-06)


### Features

* **domain:** parse typed workout logs ([#54](https://github.com/LDoyleDev/training-coach/issues/54)) ([4cdd627](https://github.com/LDoyleDev/training-coach/commit/4cdd627acbfec0589fb9c7ea99fa098bef658fd9))


### Bug Fixes

* **db:** refuse plan edits that would remap a ladder step's history ([#48](https://github.com/LDoyleDev/training-coach/issues/48)) ([0828390](https://github.com/LDoyleDev/training-coach/commit/0828390edf96f3290413d32b0a31c6f7b89cd296))

## [0.3.0](https://github.com/LDoyleDev/training-coach/compare/v0.2.0...v0.3.0) (2026-10-06)


### Features

* **bot:** add /settings and the evening nudge ([#47](https://github.com/LDoyleDev/training-coach/issues/47)) ([2415f9f](https://github.com/LDoyleDev/training-coach/commit/2415f9f504c23cc5ff742bd9b54be83afc572a6e))
* **bot:** add Start, Rest today and Swap buttons to the morning message ([#46](https://github.com/LDoyleDev/training-coach/issues/46)) ([ff3395d](https://github.com/LDoyleDev/training-coach/commit/ff3395da9a7107682242026dea15abe6957424f9))
* **bot:** send the morning session and answer /today and /week ([#43](https://github.com/LDoyleDev/training-coach/issues/43)) ([a390388](https://github.com/LDoyleDev/training-coach/commit/a39038835a7e4b067497a29a5744070a9e075aef))


### Documentation

* drop notes about who wrote the code ([#44](https://github.com/LDoyleDev/training-coach/issues/44)) ([f5aeccc](https://github.com/LDoyleDev/training-coach/commit/f5aeccc4ee7c15b53477aa885d6faeeca3aa5062))

## [0.2.0](https://github.com/LDoyleDev/training-coach/compare/v0.1.0...v0.2.0) (2026-10-06)


### Features

* **db:** add phase 1 data model and initial migration ([#15](https://github.com/LDoyleDev/training-coach/issues/15)) ([1659578](https://github.com/LDoyleDev/training-coach/commit/1659578d6981fb7105425a980098b8bd75a93986))
* **db:** seed the training plan from plan.toml ([#17](https://github.com/LDoyleDev/training-coach/issues/17)) ([db56602](https://github.com/LDoyleDev/training-coach/commit/db566027d12e02b0e4fc5d059531d53374f617fd))
* **domain:** add session queue, targets and progression rules ([#19](https://github.com/LDoyleDev/training-coach/issues/19)) ([f0352d0](https://github.com/LDoyleDev/training-coach/commit/f0352d08b7033b16d1281b32834885e4b7998fa7))
* **domain:** align the training plan with Huberman's foundational fitness protocol ([#27](https://github.com/LDoyleDev/training-coach/issues/27)) ([80f5740](https://github.com/LDoyleDev/training-coach/commit/80f5740410ee58a529fb9c1dcf16f608e8b144e3))
* **web:** add the public training plan page and GET /api/plan ([#32](https://github.com/LDoyleDev/training-coach/issues/32)) ([16a4500](https://github.com/LDoyleDev/training-coach/commit/16a450015d3ab04ec36c8fe8dfbf09ec1bc6ee4a))


### Bug Fixes

* **infra:** stop .env.example overriding the database path inside the container ([#33](https://github.com/LDoyleDev/training-coach/issues/33)) ([8236dd0](https://github.com/LDoyleDev/training-coach/commit/8236dd0e4a18b41cf1cfb28b6fcfae293745ead3))
* **web:** bump source-map-js to 1.2.2 for GHSA-68fv-2mgg-jv7q ([#37](https://github.com/LDoyleDev/training-coach/issues/37)) ([966e540](https://github.com/LDoyleDev/training-coach/commit/966e540f5036fc6951aba07e997f12d3cba4d8a8))


### Documentation

* move development to WSL 2 on the Windows desktop ([#31](https://github.com/LDoyleDev/training-coach/issues/31)) ([9ff84f3](https://github.com/LDoyleDev/training-coach/commit/9ff84f3e07b34895905efbf215a1d59211fea52f))
* record phase 1 status, draft the phase 2 spec and document the live Pi setup ([#35](https://github.com/LDoyleDev/training-coach/issues/35)) ([1bf9f9f](https://github.com/LDoyleDev/training-coach/commit/1bf9f9f79bc355acd838c20edccf7198137d64b4))

## 0.1.0 (2026-09-29)

### Features

* Project scaffold: FastAPI backend with owner-only Telegram bot skeleton, React dashboard
  shell, Docker Compose deployment, CI, release automation, ADRs 0001-0013 and phase 1 spec.
