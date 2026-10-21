# Changelog

All notable changes are documented here by [release-please](https://github.com/googleapis/release-please)
from [Conventional Commits](https://www.conventionalcommits.org/). Versions follow
[SemVer](https://semver.org/).

## [0.32.0](https://github.com/LDoyleDev/training-coach/compare/v0.31.0...v0.32.0) (2026-10-21)


### Features

* **web:** record when each set of a guided session starts and ends ([#267](https://github.com/LDoyleDev/training-coach/issues/267)) ([d350b45](https://github.com/LDoyleDev/training-coach/commit/d350b45639b8504eb7825447cdf71c74fd669cee))
* **web:** say how long today's session takes on the home screen ([#274](https://github.com/LDoyleDev/training-coach/issues/274)) ([680336c](https://github.com/LDoyleDev/training-coach/commit/680336c9eae3ce949b8f128299f14931c7a96326))
* **web:** show how long guided sessions take ([#270](https://github.com/LDoyleDev/training-coach/issues/270)) ([a0ddfec](https://github.com/LDoyleDev/training-coach/commit/a0ddfecea25dde9d0f2faf66c47c8c5e3bc49100))


### Bug Fixes

* **deps:** update certifi and Pillow past newly published vulnerabilities ([#268](https://github.com/LDoyleDev/training-coach/issues/268)) ([18d81af](https://github.com/LDoyleDev/training-coach/commit/18d81afcd0e64af4f659db9fc4b785442644fd76))

## [0.31.0](https://github.com/LDoyleDev/training-coach/compare/v0.30.0...v0.31.0) (2026-10-19)


### Features

* tell me when steps, sleep or heart rate stop on their own ([#257](https://github.com/LDoyleDev/training-coach/issues/257)) ([aec4cd3](https://github.com/LDoyleDev/training-coach/commit/aec4cd3ef553ae1d18958db58407bb344f24338a))

## [0.30.0](https://github.com/LDoyleDev/training-coach/compare/v0.29.0...v0.30.0) (2026-10-13)


### Features

* tell me when band data stops arriving ([#243](https://github.com/LDoyleDev/training-coach/issues/243)) ([5b7c476](https://github.com/LDoyleDev/training-coach/commit/5b7c476f92a769ab6e77b9289880202cc8b54e54))


### Bug Fixes

* **api:** ignore HC Webhook test payloads ([#245](https://github.com/LDoyleDev/training-coach/issues/245)) ([ebcc972](https://github.com/LDoyleDev/training-coach/commit/ebcc97288c907fa2cbcc5fe3e7587440af4d7f68))

## [0.29.0](https://github.com/LDoyleDev/training-coach/compare/v0.28.0...v0.29.0) (2026-10-12)


### Features

* **api:** ask before a log lands on a day that has its session ([#240](https://github.com/LDoyleDev/training-coach/issues/240)) ([e8fce94](https://github.com/LDoyleDev/training-coach/commit/e8fce94e60c30c48a135f57aabbc684133cc077c))
* **bot:** ask in Telegram before a day gets two sessions ([#242](https://github.com/LDoyleDev/training-coach/issues/242)) ([4906487](https://github.com/LDoyleDev/training-coach/commit/4906487b7e0606b825df62bad6b5f1d0e2748f4f))
* Claude can propose logs you confirm (MCP C2) ([#234](https://github.com/LDoyleDev/training-coach/issues/234)) ([97bae35](https://github.com/LDoyleDev/training-coach/commit/97bae355d462cace7022a35742a859dfd73fe4d3))
* **web:** log another day, and ask before a day gets two sessions ([#241](https://github.com/LDoyleDev/training-coach/issues/241)) ([91f6fc1](https://github.com/LDoyleDev/training-coach/commit/91f6fc17f194dd483d92556a93fcec0b4fd97460))


### Bug Fixes

* **api:** alerts, message times and drafts go to their own person ([#236](https://github.com/LDoyleDev/training-coach/issues/236)) ([6aefdd8](https://github.com/LDoyleDev/training-coach/commit/6aefdd875372f1eae7a6bbc182c85d7bf31aa6f8))
* **parser:** accept the activity word on a cardio log line ([#239](https://github.com/LDoyleDev/training-coach/issues/239)) ([75e6b86](https://github.com/LDoyleDev/training-coach/commit/75e6b86ebb4339f1ba4c708e68b1624607db09f1))


### Documentation

* multi-user steps 1-3 done; drop the fixed owner leaks ([#238](https://github.com/LDoyleDev/training-coach/issues/238)) ([11f5bc9](https://github.com/LDoyleDev/training-coach/commit/11f5bc9bd4ec838e0dc94bb3328ccd4e7a6756a9))
* record multi-user decisions, ADR-0058 for invites and members ([#233](https://github.com/LDoyleDev/training-coach/issues/233)) ([131fde6](https://github.com/LDoyleDev/training-coach/commit/131fde6703337db725045ba6bd6d99df7072ee20))

## [0.28.0](https://github.com/LDoyleDev/training-coach/compare/v0.27.0...v0.28.0) (2026-10-12)


### Features

* pace setting for progression steps ([#231](https://github.com/LDoyleDev/training-coach/issues/231)) ([fe1102b](https://github.com/LDoyleDev/training-coach/commit/fe1102be4db49f207695b7e1c25f5aecba45b13a))


### Documentation

* plan for invite-only multi-user (L2) ([#230](https://github.com/LDoyleDev/training-coach/issues/230)) ([aeb734b](https://github.com/LDoyleDev/training-coach/commit/aeb734b4d33a41a995a5921175b754966992f045))

## [0.27.0](https://github.com/LDoyleDev/training-coach/compare/v0.26.0...v0.27.0) (2026-10-11)


### Features

* **api:** ingest band data from Health Connect Webhook (ADR-0055) ([#224](https://github.com/LDoyleDev/training-coach/issues/224)) ([5d11332](https://github.com/LDoyleDev/training-coach/commit/5d11332d211b5f56f70024d2f26a4f6b0a565ab9))
* **api:** OAuth server and passkey consent page for Connect my AI ([#227](https://github.com/LDoyleDev/training-coach/issues/227)) ([cec9956](https://github.com/LDoyleDev/training-coach/commit/cec9956b2ea1286f6eb640dc94cf2c9600f7106e))
* **api:** read-only /mcp endpoint with scoped tools for Connect my AI ([#222](https://github.com/LDoyleDev/training-coach/issues/222)) ([f51623f](https://github.com/LDoyleDev/training-coach/commit/f51623f76f121e581e021524af409f22aaf61712))
* **db:** MCP connections, codes and tokens with rotation and revoke ([#218](https://github.com/LDoyleDev/training-coach/issues/218)) ([6207a95](https://github.com/LDoyleDev/training-coach/commit/6207a95a72ff5cfc86459236a07c083ffbd968e5))
* **domain:** Karvonen heart-rate zones for imported workouts ([#225](https://github.com/LDoyleDev/training-coach/issues/225)) ([4236d57](https://github.com/LDoyleDev/training-coach/commit/4236d5788e8fcad2b065290c9d3b2e56568351ce))
* **web:** band sleep, steps and resting HR on Home and Progress ([#228](https://github.com/LDoyleDev/training-coach/issues/228)) ([9c09540](https://github.com/LDoyleDev/training-coach/commit/9c095409a1ec041093983a42cf70d8d8fd9f8ab9))
* **web:** count a band workout as cardio with one tap ([#226](https://github.com/LDoyleDev/training-coach/issues/226)) ([d496f79](https://github.com/LDoyleDev/training-coach/commit/d496f7970c2aa1f11512a7388037a44e6302ee1e))
* **web:** list and revoke connected AI apps on the Account page ([#223](https://github.com/LDoyleDev/training-coach/issues/223)) ([66f6a30](https://github.com/LDoyleDev/training-coach/commit/66f6a3087741639341efe7a92c0ad7243b4b2f43))
* **web:** message times, nudges and pause on Account ([#217](https://github.com/LDoyleDev/training-coach/issues/217)) ([7113afd](https://github.com/LDoyleDev/training-coach/commit/7113afd9fe9f6cea45ad0dfbb162f5d6b05f8426))
* **web:** show the week's AI comment on /review, kept 7 days ([#229](https://github.com/LDoyleDev/training-coach/issues/229)) ([e7dbed4](https://github.com/LDoyleDev/training-coach/commit/e7dbed4c4ea8a0fc87731a92f32b8e882c0955fd))
* **web:** the plan becomes a tab of Progress ([#220](https://github.com/LDoyleDev/training-coach/issues/220)) ([8d66da2](https://github.com/LDoyleDev/training-coach/commit/8d66da23f24a49ecbc6dcdd343c33f70192c780a))
* **web:** the weekly review page, linked from Home and Progress ([#219](https://github.com/LDoyleDev/training-coach/issues/219)) ([52a56b5](https://github.com/LDoyleDev/training-coach/commit/52a56b5663c79b53e73e00e19c2da1a34a76932b))
* **web:** tick today's habits on the session page ([#216](https://github.com/LDoyleDev/training-coach/issues/216)) ([e1ebed4](https://github.com/LDoyleDev/training-coach/commit/e1ebed4447a0ba7bcc87c58cf3f242518d4168bf))


### Documentation

* threat model for connecting my own AI over MCP ([#196](https://github.com/LDoyleDev/training-coach/issues/196)) ([212857f](https://github.com/LDoyleDev/training-coach/commit/212857f603a8a5e18fc10aefbe6dbf1b6309464e))

## [0.26.0](https://github.com/LDoyleDev/training-coach/compare/v0.25.0...v0.26.0) (2026-10-11)


### Features

* **api:** log cardio in one step, with minutes and what it was ([#202](https://github.com/LDoyleDev/training-coach/issues/202)) ([1330fae](https://github.com/LDoyleDev/training-coach/commit/1330faeb2c98b43beef4c9fbf768d17a43e19bd9))
* **api:** the home page's last 7 days say what each cardio log was ([#208](https://github.com/LDoyleDev/training-coach/issues/208)) ([9dec6b3](https://github.com/LDoyleDev/training-coach/commit/9dec6b3c39ffea327188918c5b9481ac0082c1d6))
* **bot:** an Open in app button on the morning message and /today ([#204](https://github.com/LDoyleDev/training-coach/issues/204)) ([7c1ca91](https://github.com/LDoyleDev/training-coach/commit/7c1ca91cb653c6ba74e257faa20d427a420cb016))
* **bot:** ask the daily check on the morning message ([#214](https://github.com/LDoyleDev/training-coach/issues/214)) ([ddd5724](https://github.com/LDoyleDev/training-coach/commit/ddd5724ca0078c2d8cb4862252b64840452c20b4))
* **parser:** a typed or spoken cardio log keeps what it was ([#207](https://github.com/LDoyleDev/training-coach/issues/207)) ([3931575](https://github.com/LDoyleDev/training-coach/commit/393157573bf52acc78a87bfb0e5ffe333058a873))
* **web:** a HIIT interval timer with countdown beeps and a bell ([#201](https://github.com/LDoyleDev/training-coach/issues/201)) ([eaa0ba3](https://github.com/LDoyleDev/training-coach/commit/eaa0ba31009ed7067d4d61821b5a0a429bfcfb31))
* **web:** a home page that shows what you've done, then Today ([#203](https://github.com/LDoyleDev/training-coach/issues/203)) ([68f0c49](https://github.com/LDoyleDev/training-coach/commit/68f0c4979c46f60668f4cf64d73db98ffc316359))
* **web:** ask the readiness questions when the app opens, if due ([#209](https://github.com/LDoyleDev/training-coach/issues/209)) ([6122cf5](https://github.com/LDoyleDev/training-coach/commit/6122cf50f97beed9790da535aa824eefa7cd4197))
* **web:** daily check of sleep, soreness and energy before training ([#213](https://github.com/LDoyleDev/training-coach/issues/213)) ([b0af6a6](https://github.com/LDoyleDev/training-coach/commit/b0af6a6d6f9a0aa9c6dd1ed8c916198faa3de544))
* **web:** install the app on the phone's home screen (D3) ([#211](https://github.com/LDoyleDev/training-coach/issues/211)) ([c8155a1](https://github.com/LDoyleDev/training-coach/commit/c8155a110cccebafcd6f5d81f34d91610e623157))
* **web:** log cardio in one step, and run HIIT from the session page ([#206](https://github.com/LDoyleDev/training-coach/issues/206)) ([6c15b24](https://github.com/LDoyleDev/training-coach/commit/6c15b24b43ad28f3bf038bd13491c5423a0c45cd))
* **web:** rest, push, swap and undo today from the web app ([#212](https://github.com/LDoyleDev/training-coach/issues/212)) ([bd7a1c2](https://github.com/LDoyleDev/training-coach/commit/bd7a1c2867502017aeea4a19f66b67d91198ee6f))
* **web:** the HIIT timer works like the Tabata Timer app ([#210](https://github.com/LDoyleDev/training-coach/issues/210)) ([ba7dff2](https://github.com/LDoyleDev/training-coach/commit/ba7dff2c48eeeea9a894859e3161a6e507b58320))

## [0.25.0](https://github.com/LDoyleDev/training-coach/compare/v0.24.0...v0.25.0) (2026-10-10)


### Features

* **bot:** /share sends my last 4 weeks as a picture to forward ([#199](https://github.com/LDoyleDev/training-coach/issues/199)) ([745a7df](https://github.com/LDoyleDev/training-coach/commit/745a7df91c0ca40135e22854e214fa54ea26077f))
* **web:** buttons that look like buttons, and pages that fit a phone ([#197](https://github.com/LDoyleDev/training-coach/issues/197)) ([6736a9b](https://github.com/LDoyleDev/training-coach/commit/6736a9bd5b990a969d863a9ae9562842721f5c12))
* **web:** confirm it's you with your fingerprint instead of signing out ([#194](https://github.com/LDoyleDev/training-coach/issues/194)) ([d8364ac](https://github.com/LDoyleDev/training-coach/commit/d8364ac0cccc2ccc4a5303fd8b0bf6be631ce4d9))


### Documentation

* a UX plan with options to make the app flow ([#195](https://github.com/LDoyleDev/training-coach/issues/195)) ([3713c10](https://github.com/LDoyleDev/training-coach/commit/3713c1072b4c6bbb5952570c63aba28d875ba8b7))
* architecture paths for undo, AI comments, share and confirm ([#200](https://github.com/LDoyleDev/training-coach/issues/200)) ([544a24a](https://github.com/LDoyleDev/training-coach/commit/544a24a608704a62b2125d4f393d3d92c62b7b48))

## [0.24.0](https://github.com/LDoyleDev/training-coach/compare/v0.23.0...v0.24.0) (2026-10-10)


### Features

* **web:** a Sign out button in the top bar of every page ([#192](https://github.com/LDoyleDev/training-coach/issues/192)) ([d9e1881](https://github.com/LDoyleDev/training-coach/commit/d9e18815cd4fe73b185ec6a55d5db0a9a53f56e7))

## [0.23.0](https://github.com/LDoyleDev/training-coach/compare/v0.22.0...v0.23.0) (2026-10-10)


### Features

* **api:** store my own Groq key, encrypted, for AI comments ([#189](https://github.com/LDoyleDev/training-coach/issues/189)) ([3f58b62](https://github.com/LDoyleDev/training-coach/commit/3f58b62f4c04f3c8b6b19b2e797c9bfef51b0e06))
* **bot:** /undo takes back the last rest, swap, push or saved log ([#188](https://github.com/LDoyleDev/training-coach/issues/188)) ([bef989b](https://github.com/LDoyleDev/training-coach/commit/bef989bbdfd49c8a3c4cc1a01e1301dc4b52e88c))
* **bot:** a weekly AI comment from my own Groq key after the review ([#191](https://github.com/LDoyleDev/training-coach/issues/191)) ([780af4d](https://github.com/LDoyleDev/training-coach/commit/780af4d5cc9ca957764b039bf4e83c6c319bc5ef))
* **web:** add my own Groq key for AI comments on the Account page ([#190](https://github.com/LDoyleDev/training-coach/issues/190)) ([711c7fe](https://github.com/LDoyleDev/training-coach/commit/711c7fe26d6d479916d44ee7d50e60f7bdc25f3c))
* **web:** copy my training for my own AI, with a guide to read ([#187](https://github.com/LDoyleDev/training-coach/issues/187)) ([a98b75a](https://github.com/LDoyleDev/training-coach/commit/a98b75a1b601e0632751074a990a369981a799fd))
* **web:** trend lines for measurements and test results ([#184](https://github.com/LDoyleDev/training-coach/issues/184)) ([e9d4eec](https://github.com/LDoyleDev/training-coach/commit/e9d4eec56b435f91a18e5439c185efbfaf36bf65))


### Documentation

* proposal for bring-your-own-AI connections ([#186](https://github.com/LDoyleDev/training-coach/issues/186)) ([eece39b](https://github.com/LDoyleDev/training-coach/commit/eece39b3ec21e498540c20687215a09bddeeecda))

## [0.22.0](https://github.com/LDoyleDev/training-coach/compare/v0.21.0...v0.22.0) (2026-10-10)


### Features

* **api:** readiness questions, and a note on hard days ([#182](https://github.com/LDoyleDev/training-coach/issues/182)) ([fe913ab](https://github.com/LDoyleDev/training-coach/commit/fe913ab8f30879d1b86bf22433e5e95efe90cbba))
* **infra:** a heartbeat to Healthchecks.io every 5 minutes ([#179](https://github.com/LDoyleDev/training-coach/issues/179)) ([9e3319b](https://github.com/LDoyleDev/training-coach/commit/9e3319b61ca69554d54df6aa0df037c32731cc6e))
* **web:** the readiness page, and its advice on hard days ([#183](https://github.com/LDoyleDev/training-coach/issues/183)) ([53bc91e](https://github.com/LDoyleDev/training-coach/commit/53bc91e7971dc9627fccd2cbed0c73ea2370f845))


### Documentation

* draft privacy notice and Impressum, unpublished ([#180](https://github.com/LDoyleDev/training-coach/issues/180)) ([b2f11e5](https://github.com/LDoyleDev/training-coach/commit/b2f11e5a55953b459d8887b91d80ddc8d85033f2))

## [0.21.0](https://github.com/LDoyleDev/training-coach/compare/v0.20.0...v0.21.0) (2026-10-10)


### Features

* **api:** erase all my data ([#176](https://github.com/LDoyleDev/training-coach/issues/176)) ([e8908f5](https://github.com/LDoyleDev/training-coach/commit/e8908f5482977f7ddc5aa73e8e31b456534ea24c))
* **infra:** manual and pre-deploy backups go after 35 days ([#177](https://github.com/LDoyleDev/training-coach/issues/177)) ([b988bac](https://github.com/LDoyleDev/training-coach/commit/b988bac561ca63225af4031149bdc97c5237a266))
* **infra:** the Pi deploys only releases GitHub signed ([#172](https://github.com/LDoyleDev/training-coach/issues/172)) ([418659f](https://github.com/LDoyleDev/training-coach/commit/418659f69aeff89758b72e37e46e85b1f8130de7))


### Documentation

* ADR-0044 records the 35-day limit on manual backups ([#178](https://github.com/LDoyleDev/training-coach/issues/178)) ([e1ee591](https://github.com/LDoyleDev/training-coach/commit/e1ee591674884ec9236d2591cba833439908dd5a))
* security policy for the public repo ([#173](https://github.com/LDoyleDev/training-coach/issues/173)) ([94f0030](https://github.com/LDoyleDev/training-coach/commit/94f0030dfff182325e1073463ae8863d21351eeb))
* threat model and specs record export and failure alerts ([#170](https://github.com/LDoyleDev/training-coach/issues/170)) ([8d5bc7e](https://github.com/LDoyleDev/training-coach/commit/8d5bc7e3a05fb225915bae3eda7fa028338d1981))

## [0.20.0](https://github.com/LDoyleDev/training-coach/compare/v0.19.0...v0.20.0) (2026-10-10)


### Features

* **api:** download all my data as one zip ([#169](https://github.com/LDoyleDev/training-coach/issues/169)) ([361d5a6](https://github.com/LDoyleDev/training-coach/commit/361d5a671455a968e02e99a92fb6426764bdabd4))
* **infra:** a Telegram alert when a deploy or off-site backup fails ([#168](https://github.com/LDoyleDev/training-coach/issues/168)) ([7bc0348](https://github.com/LDoyleDev/training-coach/commit/7bc03487fbfac2e28ee502de12b06bc02c941302))
* **web:** safety cues on the riskiest exercises and a stop reminder ([#165](https://github.com/LDoyleDev/training-coach/issues/165)) ([ec8fca5](https://github.com/LDoyleDev/training-coach/commit/ec8fca532599dd297607dfe84f3d03a73ec263e7))


### Bug Fixes

* **api:** 90-day session limit, passkey removal ends its sessions, JPEG allowlist ([#167](https://github.com/LDoyleDev/training-coach/issues/167)) ([8fa0c0a](https://github.com/LDoyleDev/training-coach/commit/8fa0c0afb09795c1625beb601b953f2c3ff3d9e9))

## [0.19.0](https://github.com/LDoyleDev/training-coach/compare/v0.18.0...v0.19.0) (2026-10-10)


### Features

* **infra:** a dedicated backup key, and more than one if wanted ([#164](https://github.com/LDoyleDev/training-coach/issues/164)) ([1b73f18](https://github.com/LDoyleDev/training-coach/commit/1b73f1841ccf26074b467092cf9b8d974240fa31))
* **infra:** encrypted off-site backups to R2, 35 days everywhere ([#162](https://github.com/LDoyleDev/training-coach/issues/162)) ([0cf50c2](https://github.com/LDoyleDev/training-coach/commit/0cf50c2be57c462ac0f024117bda02c7317e0651))
* **web:** the site is private; the plan moves to /plan behind sign-in ([#161](https://github.com/LDoyleDev/training-coach/issues/161)) ([3d86417](https://github.com/LDoyleDev/training-coach/commit/3d864179f6846592406f66dc3af3e4e0b8723a4c))

## [0.18.0](https://github.com/LDoyleDev/training-coach/compare/v0.17.0...v0.18.0) (2026-10-10)


### Features

* **api:** passkey-first sign-in, /recover, fresh sign-in for passkey changes, alerts ([#158](https://github.com/LDoyleDev/training-coach/issues/158)) ([692e7e5](https://github.com/LDoyleDev/training-coach/commit/692e7e564949c95eb866ed2b2b21f5e7367bbedd))


### Bug Fixes

* **api:** refuse cross-site changes, cap bodies, distrust forwarded addresses ([#160](https://github.com/LDoyleDev/training-coach/issues/160)) ([6092fc9](https://github.com/LDoyleDev/training-coach/commit/6092fc94fd76f5dc15b48a76cab547c1665d1033))

## [0.17.0](https://github.com/LDoyleDev/training-coach/compare/v0.16.0...v0.17.0) (2026-10-10)


### Features

* **api:** progress photos, cleaned of metadata, kept in the database ([#150](https://github.com/LDoyleDev/training-coach/issues/150)) ([7732ebe](https://github.com/LDoyleDev/training-coach/commit/7732ebe28e9a59eb41300b99b387f7ff4bec4bea))
* **web:** a Progress page with each exercise's step, best and trend ([#155](https://github.com/LDoyleDev/training-coach/issues/155)) ([0159b49](https://github.com/LDoyleDev/training-coach/commit/0159b491a78ba97808e6146df73eb3a1cadf5856))
* **web:** progress photos on /body, shrunk in the browser ([#152](https://github.com/LDoyleDev/training-coach/issues/152)) ([2a4b0b9](https://github.com/LDoyleDev/training-coach/commit/2a4b0b9dbb10edd5d30ade19436b267d44b3e370))
* **web:** the public plan page links to the app ([#153](https://github.com/LDoyleDev/training-coach/issues/153)) ([0d95bc4](https://github.com/LDoyleDev/training-coach/commit/0d95bc41a76be44de2ca8dc988f749128f7ed7ee))


### Documentation

* backups cover photos and measurements; rehearse with them ([#154](https://github.com/LDoyleDev/training-coach/issues/154)) ([bee8b6e](https://github.com/LDoyleDev/training-coach/commit/bee8b6e905b69eba4f41d007cc8c436cc9e5f5c3))
* phase 2 overview records photos and the progress page ([#157](https://github.com/LDoyleDev/training-coach/issues/157)) ([d8cdc1c](https://github.com/LDoyleDev/training-coach/commit/d8cdc1cef2f1fca996af656866d9fab073c35c3c))
* run a release PR's checks by closing and reopening it ([#156](https://github.com/LDoyleDev/training-coach/issues/156)) ([2145a58](https://github.com/LDoyleDev/training-coach/commit/2145a5809b69b09284f7265061492baa6d967810))

## [0.16.0](https://github.com/LDoyleDev/training-coach/compare/v0.15.0...v0.16.0) (2026-10-10)


### Features

* **api:** baseline test definitions and test days ([#137](https://github.com/LDoyleDev/training-coach/issues/137)) ([aed6b07](https://github.com/LDoyleDev/training-coach/commit/aed6b07c39df082fcf19f50772ad6cf455c9003f))
* **api:** body measurements, one per kind per day ([#144](https://github.com/LDoyleDev/training-coach/issues/144)) ([bcb0e58](https://github.com/LDoyleDev/training-coach/commit/bcb0e5831df621a016b6c2c67ce5b0d94537cff2))
* **api:** keep a guided session's progress and save it as a workout ([#129](https://github.com/LDoyleDev/training-coach/issues/129)) ([b596963](https://github.com/LDoyleDev/training-coach/commit/b596963ffeb4081329d4a7e1d87e86830373de6b))
* **api:** sign in to the web app with a one-time link from the bot ([#122](https://github.com/LDoyleDev/training-coach/issues/122)) ([d041b48](https://github.com/LDoyleDev/training-coach/commit/d041b4856013cdcd670d6fe6d5e96dbe324c83ec))
* **api:** sign in with a passkey (fingerprint or face) ([#123](https://github.com/LDoyleDev/training-coach/issues/123)) ([d441477](https://github.com/LDoyleDev/training-coach/commit/d441477b8be56769e4b5004f5e90f6d8764da80a))
* **api:** today's guided session in work order ([#128](https://github.com/LDoyleDev/training-coach/issues/128)) ([e0d73e6](https://github.com/LDoyleDev/training-coach/commit/e0d73e6d257a77d0ded484ed11473bab6627d911))
* **bot:** a short how-to for every exercise in a session ([#125](https://github.com/LDoyleDev/training-coach/issues/125)) ([1d47489](https://github.com/LDoyleDev/training-coach/commit/1d4748901689d9118e7c312922b36328b9de1445))
* **bot:** weekly review shows zone 2 minutes against 180-200 ([#141](https://github.com/LDoyleDev/training-coach/issues/141)) ([4665dde](https://github.com/LDoyleDev/training-coach/commit/4665dde9622f661da32c51af1eb1d4525907fe76))
* **db:** every workout records the plan version in force on its date ([#134](https://github.com/LDoyleDev/training-coach/issues/134)) ([9a53f15](https://github.com/LDoyleDev/training-coach/commit/9a53f153adad90ca597a10e368f7ab5d145ff74d))
* **scheduler:** due test days stand in front of the queue ([#140](https://github.com/LDoyleDev/training-coach/issues/140)) ([7cfc8d7](https://github.com/LDoyleDev/training-coach/commit/7cfc8d701c66a0e0264b0c3b9027b736e1512b38))
* **web:** an account page to remove passkeys and sign out devices ([#127](https://github.com/LDoyleDev/training-coach/issues/127)) ([85b5977](https://github.com/LDoyleDev/training-coach/commit/85b597724d9e5fdb986a0d8585a75b2991c6c9a8))
* **web:** compare test results with the baseline and last time ([#139](https://github.com/LDoyleDev/training-coach/issues/139)) ([7a06e59](https://github.com/LDoyleDev/training-coach/commit/7a06e591f0828638ff59e831b7fa70a0a5d14bc2))
* **web:** label a first session at a step as the baseline ([#133](https://github.com/LDoyleDev/training-coach/issues/133)) ([0f9298d](https://github.com/LDoyleDev/training-coach/commit/0f9298d37f0bccfa97045c2bac877f1be9c6dbff))
* **web:** measurements at /body with the change since first and last ([#147](https://github.com/LDoyleDev/training-coach/issues/147)) ([85bd110](https://github.com/LDoyleDev/training-coach/commit/85bd110c8857e2b0ad067a136b576cb068828493))
* **web:** offer stretching after a saved guided session ([#136](https://github.com/LDoyleDev/training-coach/issues/136)) ([c813b4c](https://github.com/LDoyleDev/training-coach/commit/c813b4c65736ac7d895c716f419a977cbcf9a203))
* **web:** one header with a nav between the signed-in pages ([#148](https://github.com/LDoyleDev/training-coach/issues/148)) ([0ac630b](https://github.com/LDoyleDev/training-coach/commit/0ac630b7a7728559545e57a6bd12920cf14823b0))
* **web:** rest timer, stopwatch, pair switch and saving an unsaved day ([#132](https://github.com/LDoyleDev/training-coach/issues/132)) ([97af54c](https://github.com/LDoyleDev/training-coach/commit/97af54c598b1dc0b544e3af42811901542a4c4d1))
* **web:** show a due test day before today's session ([#145](https://github.com/LDoyleDev/training-coach/issues/145)) ([a63d1df](https://github.com/LDoyleDev/training-coach/commit/a63d1df6543c859dfa9b40c4f47ab42f395d598c))
* **web:** the guided session, one set at a time ([#131](https://github.com/LDoyleDev/training-coach/issues/131)) ([59cdbb5](https://github.com/LDoyleDev/training-coach/commit/59cdbb5fd30bff9d337e9eb44cc0f423a24739cf))
* **web:** walk through a day of baseline tests at /tests ([#138](https://github.com/LDoyleDev/training-coach/issues/138)) ([1fb87e6](https://github.com/LDoyleDev/training-coach/commit/1fb87e6540b289b77aab2f5fe52afcb6faf18209))


### Bug Fixes

* **web:** an ended sign-in says so on every page, keeping what was typed ([#149](https://github.com/LDoyleDev/training-coach/issues/149)) ([5d02637](https://github.com/LDoyleDev/training-coach/commit/5d02637e578132570687a96c0c302d0f690bd15c))


### Documentation

* decide the guided session (D1) and list its issues ([#119](https://github.com/LDoyleDev/training-coach/issues/119)) ([5eddada](https://github.com/LDoyleDev/training-coach/commit/5eddadab6a44b556f5c65bcc57c59e0997dd1ca5))
* phase 2 overview matches what is built ([#146](https://github.com/LDoyleDev/training-coach/issues/146)) ([6cf6232](https://github.com/LDoyleDev/training-coach/commit/6cf6232ce3a043a9ab864d8f6398fce6db4a7811))
* web app first (ADR-0035) and passkey sign-in (ADR-0036) ([#121](https://github.com/LDoyleDev/training-coach/issues/121)) ([2f8e1d5](https://github.com/LDoyleDev/training-coach/commit/2f8e1d5b63198c00a84bad24277f9813c10ab38e))

## [0.15.0](https://github.com/LDoyleDev/training-coach/compare/v0.14.0...v0.15.0) (2026-10-09)


### Features

* **bot:** a daily protein target for the protein habit ([#113](https://github.com/LDoyleDev/training-coach/issues/113)) ([9a8f52d](https://github.com/LDoyleDev/training-coach/commit/9a8f52d70b21e180051eb88b35834bab163967c7))

## [0.14.0](https://github.com/LDoyleDev/training-coach/compare/v0.13.0...v0.14.0) (2026-10-09)


### Features

* **bot:** say what counts for each habit in the evening message ([#111](https://github.com/LDoyleDev/training-coach/issues/111)) ([c05bdfe](https://github.com/LDoyleDev/training-coach/commit/c05bdfe85bc92f7397c8e5fd473df3f708fc69b2))

## [0.13.0](https://github.com/LDoyleDev/training-coach/compare/v0.12.0...v0.13.0) (2026-10-09)


### Features

* **db:** retire exercises instead of losing them ([#108](https://github.com/LDoyleDev/training-coach/issues/108)) ([f6f6343](https://github.com/LDoyleDev/training-coach/commit/f6f634328a872025192ef445746ffb9055748567))


### Bug Fixes

* **parser:** cycle, cycling and cycled log as zone 2 ([#110](https://github.com/LDoyleDev/training-coach/issues/110)) ([465477b](https://github.com/LDoyleDev/training-coach/commit/465477be5b492598f169a5be693451191a0213aa))

## [0.12.0](https://github.com/LDoyleDev/training-coach/compare/v0.11.0...v0.12.0) (2026-10-08)


### Features

* **bot:** log a past day with a date on the first line ([#105](https://github.com/LDoyleDev/training-coach/issues/105)) ([b4acc33](https://github.com/LDoyleDev/training-coach/commit/b4acc33b1a482b9820708335bdd1f66b06190656))

## [0.11.0](https://github.com/LDoyleDev/training-coach/compare/v0.10.0...v0.11.0) (2026-10-08)


### Features

* **bot:** list sessions set by set in work order, in exercise pairs ([#99](https://github.com/LDoyleDev/training-coach/issues/99)) ([f5199ec](https://github.com/LDoyleDev/training-coach/commit/f5199eca3e672bac7ebd650e161c685fb4a543a3))
* **bot:** offer stretching after a saved resistance log ([#102](https://github.com/LDoyleDev/training-coach/issues/102)) ([24840a9](https://github.com/LDoyleDev/training-coach/commit/24840a965948c03df7ac04e5e9177ae3581def00))
* **domain:** choose a stretching routine for a session and a time ([#101](https://github.com/LDoyleDev/training-coach/issues/101)) ([fdbf93f](https://github.com/LDoyleDev/training-coach/commit/fdbf93f841b50007b7ea2e5f7a637e899644674a))


### Documentation

* Pi commands use docker compose; make isn't installed there ([#103](https://github.com/LDoyleDev/training-coach/issues/103)) ([5f9f7a9](https://github.com/LDoyleDev/training-coach/commit/5f9f7a947d47d7a0e92c6498433cda078b72c610))

## [0.10.0](https://github.com/LDoyleDev/training-coach/compare/v0.9.1...v0.10.0) (2026-10-07)


### Features

* **bot:** habit buttons in the evening message and /habits ([#93](https://github.com/LDoyleDev/training-coach/issues/93)) ([3135ea3](https://github.com/LDoyleDev/training-coach/commit/3135ea350c0740723093b593e09669fa6d6b42d8))
* **db:** store habit check-offs and tally them in the weekly review ([#92](https://github.com/LDoyleDev/training-coach/issues/92)) ([caf3801](https://github.com/LDoyleDev/training-coach/commit/caf3801e963161eb7dd084ea21e871ea1212367e))
* **infra:** deploy new releases on the Pi from a timer ([#88](https://github.com/LDoyleDev/training-coach/issues/88)) ([c515a4c](https://github.com/LDoyleDev/training-coach/commit/c515a4ca66dea738394bb492b3369c7bb479717b))

## [0.9.1](https://github.com/LDoyleDev/training-coach/compare/v0.9.0...v0.9.1) (2026-10-07)


### Bug Fixes

* **parser:** read lines copied from the bot's own message ([#86](https://github.com/LDoyleDev/training-coach/issues/86)) ([8454b1c](https://github.com/LDoyleDev/training-coach/commit/8454b1c72547569a97c972cc6ef8b11d5839b3a9))


### Documentation

* decide photo storage (D3) and habits (D5) ([#84](https://github.com/LDoyleDev/training-coach/issues/84)) ([d290fa3](https://github.com/LDoyleDev/training-coach/commit/d290fa3959681baa6c52c82948ffcb90fd8f776b))

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
