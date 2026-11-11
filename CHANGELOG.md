# Changelog

All notable changes are documented here by [release-please](https://github.com/googleapis/release-please)
from [Conventional Commits](https://www.conventionalcommits.org/). Versions follow
[SemVer](https://semver.org/).

## [1.22.1](https://github.com/LDoyleDev/training-coach/compare/v1.22.0...v1.22.1) (2026-11-11)


### Documentation

* session log for 1.22.0 ([#735](https://github.com/LDoyleDev/training-coach/issues/735)) ([3a9005a](https://github.com/LDoyleDev/training-coach/commit/3a9005a162914d71cc71d295e701d861db76c258))

## [1.22.0](https://github.com/LDoyleDev/training-coach/compare/v1.21.0...v1.22.0) (2026-11-11)


### Features

* **api:** the cycle in the plan editor's routes, and the map per cycle ([#725](https://github.com/LDoyleDev/training-coach/issues/725)) ([a650bf9](https://github.com/LDoyleDev/training-coach/commit/a650bf9e5ff10d27b9d985d680d828a93a0bfc55))
* **db:** retired sessions, and every reader of the cycle through one helper ([#714](https://github.com/LDoyleDev/training-coach/issues/714)) ([84edb7e](https://github.com/LDoyleDev/training-coach/commit/84edb7e40210623987b8d333f9133bf0ece2c123))
* **domain:** a cycle draft applied, the queue after it, and the map's bands per cycle ([#712](https://github.com/LDoyleDev/training-coach/issues/712)) ([b4877ed](https://github.com/LDoyleDev/training-coach/commit/b4877edeeecdfaa95aa9bef0d17a4c469b85d413))
* **domain:** a plan saves its sessions: add, copy, rename, move, remove ([#719](https://github.com/LDoyleDev/training-coach/issues/719)) ([90b83f1](https://github.com/LDoyleDev/training-coach/commit/90b83f1b4b41111668f6951cf5e818dde07c3cc3))
* **domain:** a removed session is refused in words, and ends undo ([#720](https://github.com/LDoyleDev/training-coach/issues/720)) ([f2428a2](https://github.com/LDoyleDev/training-coach/commit/f2428a25ce4c52c26325cd960ee3b9488f916da1))
* **domain:** the import removes and puts back sessions, history kept ([#724](https://github.com/LDoyleDev/training-coach/issues/724)) ([0bf8602](https://github.com/LDoyleDev/training-coach/commit/0bf8602f200eca91fb3b14cc2e228f3bb705aaec))
* **web:** a cardio session without its cardio exercise is warned ([#733](https://github.com/LDoyleDev/training-coach/issues/733)) ([fded6e7](https://github.com/LDoyleDev/training-coach/commit/fded6e7f3a801db7e323cbfd11f1a05487449509))
* **web:** a session's kind can be changed on the cycle card ([#734](https://github.com/LDoyleDev/training-coach/issues/734)) ([b20dcfc](https://github.com/LDoyleDev/training-coach/commit/b20dcfca67439b5be41ec68c20af2e5a6129b5fb))
* **web:** move and remove sessions, and see what saving will do ([#729](https://github.com/LDoyleDev/training-coach/issues/729)) ([db53cba](https://github.com/LDoyleDev/training-coach/commit/db53cbac4c3eac9cff3fc54ade533766f27b4ed5))
* **web:** saving will says what's next and what today becomes ([#731](https://github.com/LDoyleDev/training-coach/issues/731)) ([93ad25c](https://github.com/LDoyleDev/training-coach/commit/93ad25c9312d7ad71f393fce4cd2ebcc0e7f5735))
* **web:** the cycle rules in TypeScript, held to the shared cases ([#716](https://github.com/LDoyleDev/training-coach/issues/716)) ([3c707a1](https://github.com/LDoyleDev/training-coach/commit/3c707a1997b7a93ae6c098ce3fc63e03b9f28368))
* **web:** your cycle on the plan editor: add a session, rename, rest days ([#728](https://github.com/LDoyleDev/training-coach/issues/728)) ([20baa46](https://github.com/LDoyleDev/training-coach/commit/20baa4683849f6418b5bf7e7acd6269a4a438ede))


### Bug Fixes

* **domain:** the cycle save writes the event kind undo reads, from one place ([#721](https://github.com/LDoyleDev/training-coach/issues/721)) ([3b65a1d](https://github.com/LDoyleDev/training-coach/commit/3b65a1dad6567b8c150e1153f3ee5d6c3ca68967))


### Documentation

* **docs:** ADR-0093, adding and removing sessions, with Liam's 20 decisions ([#707](https://github.com/LDoyleDev/training-coach/issues/707)) ([112dcad](https://github.com/LDoyleDev/training-coach/commit/112dcad9ff13282fb3940980ca07a9b884c9f795))
* **docs:** session log for 1.21.0 ([#711](https://github.com/LDoyleDev/training-coach/issues/711)) ([e2dadb0](https://github.com/LDoyleDev/training-coach/commit/e2dadb0b2a43e4db12e2276630b788378c4e956f))

## [1.21.0](https://github.com/LDoyleDev/training-coach/compare/v1.20.0...v1.21.0) (2026-11-10)


### Features

* **api:** the walk-through's routes: what it asks, a preview and the one save ([#685](https://github.com/LDoyleDev/training-coach/issues/685)) ([329f24b](https://github.com/LDoyleDev/training-coach/commit/329f24bda211ff7ab71425fd93b0eb0c1369c4ef))
* **db:** the 45° back extension keeps the lower back at 4 at the gym ([#671](https://github.com/LDoyleDev/training-coach/issues/671)) ([fa2912f](https://github.com/LDoyleDev/training-coach/commit/fa2912fc61a5c80441f6588a6106613627a040e9))
* **db:** walk-through answers, start date and exercises per session in the schema ([#673](https://github.com/LDoyleDev/training-coach/issues/673)) ([d554091](https://github.com/LDoyleDev/training-coach/commit/d5540911842c669cf8ba602c16c8e4033f968c6f))
* **domain:** exercises per session in the trim, and a plan that starts on a day ([#674](https://github.com/LDoyleDev/training-coach/issues/674)) ([9614a1c](https://github.com/LDoyleDev/training-coach/commit/9614a1ce86369211c65d60cb456fb0a34b444a55))
* **domain:** the walk-through's one save makes a member's plan from their choices ([#679](https://github.com/LDoyleDev/training-coach/issues/679)) ([31094a6](https://github.com/LDoyleDev/training-coach/commit/31094a66dc6e2aae33632fcdbd24dbac090aee88))
* **web:** /start, the walk-through's shell, with consent, where you live and the health questions ([#683](https://github.com/LDoyleDev/training-coach/issues/683)) ([37344e8](https://github.com/LDoyleDev/training-coach/commit/37344e801732b9fb63477582689e21ab0317848e))
* **web:** the walk-through reads GET /api/walkthrough, with the starter and start day in TS ([#688](https://github.com/LDoyleDev/training-coach/issues/688)) ([999bdde](https://github.com/LDoyleDev/training-coach/commit/999bdde3243e843ec5d968ae6340a877781871c2))
* **web:** the walk-through's ladder walker, and the days, minutes and exercises per session ([#686](https://github.com/LDoyleDev/training-coach/issues/686)) ([ac4a64f](https://github.com/LDoyleDev/training-coach/commit/ac4a64fe1457874e70c9dbfd1d7080d230ec32f3))
* **web:** the walk-through's level rule, ladder walk and lock rule in TypeScript ([#676](https://github.com/LDoyleDev/training-coach/issues/676)) ([dc0bf5b](https://github.com/LDoyleDev/training-coach/commit/dc0bf5bdf972fc48d48a5f6233ffbc021081c434))
* **web:** the walk-through's plan screen, previewed and changeable ([#696](https://github.com/LDoyleDev/training-coach/issues/696)) ([b7093a0](https://github.com/LDoyleDev/training-coach/commit/b7093a017aebe4bca4de2aed7216e01cf5fff330))
* **web:** the walk-through's questions about you, what to avoid, where you train and the home kit ([#684](https://github.com/LDoyleDev/training-coach/issues/684)) ([0b13d23](https://github.com/LDoyleDev/training-coach/commit/0b13d23a7155ec8112521c4f3e3db8b5c3c495e9))
* **web:** the walk-through's Save, with the answers only after a yes, and Done ([#697](https://github.com/LDoyleDev/training-coach/issues/697)) ([10d01d3](https://github.com/LDoyleDev/training-coach/commit/10d01d32286bc36aa78cf5b0fa9a1550449da717))
* **web:** the ways into the walk-through, and the Plan hero from the plan ([#698](https://github.com/LDoyleDev/training-coach/issues/698)) ([dade830](https://github.com/LDoyleDev/training-coach/commit/dade83093df4c4cd46fe0699a59fe755b3fa0b40))


### Bug Fixes

* **domain:** say "dip bars or two chairs" without an "a" ([#705](https://github.com/LDoyleDev/training-coach/issues/705)) ([da95012](https://github.com/LDoyleDev/training-coach/commit/da950120c94b12b3a728bede4d4aed453e591773))
* **web:** Account's two-line choices without Tailwind's block ([#693](https://github.com/LDoyleDev/training-coach/issues/693)) ([ed0d0d9](https://github.com/LDoyleDev/training-coach/commit/ed0d0d94a9847a601679044d3cc843b2881ae5b5))
* **web:** drop a Telegram card error once the card has moved on ([#702](https://github.com/LDoyleDev/training-coach/issues/702)) ([9450c54](https://github.com/LDoyleDev/training-coach/commit/9450c54ceb3290758a026d8ef05ccc77186bd924))
* **web:** offer a new Telegram link when a reload lost the one shown ([#701](https://github.com/LDoyleDev/training-coach/issues/701)) ([e867696](https://github.com/LDoyleDev/training-coach/commit/e867696b5586041a86afed574af595fe4ee0bc22))
* **web:** read the Plan page's ladders from the person's plan ([#706](https://github.com/LDoyleDev/training-coach/issues/706)) ([746745e](https://github.com/LDoyleDev/training-coach/commit/746745e907b0a5952e264e0282dbeafae912582c))


### Documentation

* **docs:** ADR-0092, the walk-through, with Liam's 23 decisions taken as recommended ([#666](https://github.com/LDoyleDev/training-coach/issues/666)) ([b2f3a82](https://github.com/LDoyleDev/training-coach/commit/b2f3a825da308844e40840f65cd386f243ccd820))
* **docs:** session log for 1.20.0 ([#670](https://github.com/LDoyleDev/training-coach/issues/670)) ([7cb612b](https://github.com/LDoyleDev/training-coach/commit/7cb612bf5f9f8849613e684ca2089fad35351e1a))

## [1.20.0](https://github.com/LDoyleDev/training-coach/compare/v1.19.0...v1.20.0) (2026-11-08)


### Features

* **api:** a member's health data opens per category on consent (ADR-0090) ([#618](https://github.com/LDoyleDev/training-coach/issues/618)) ([9c09889](https://github.com/LDoyleDev/training-coach/commit/9c0988968c9137270d153ff0f078a33f05204807))
* **api:** connect a member's Telegram with a link and a code (ADR-0089) ([#639](https://github.com/LDoyleDev/training-coach/issues/639)) ([3977b1b](https://github.com/LDoyleDev/training-coach/commit/3977b1bd62bdc157f0fccd503126ee4f32896670))
* **api:** consent records per category; withdrawing erases (ADR-0090) ([#617](https://github.com/LDoyleDev/training-coach/issues/617)) ([b4d8028](https://github.com/LDoyleDev/training-coach/commit/b4d80282abcf76f795b96c63e0f00c236f26404f))
* **bot:** a stranger's /start &lt;token&gt; gets the connect code (ADR-0089) ([#643](https://github.com/LDoyleDev/training-coach/issues/643)) ([d150809](https://github.com/LDoyleDev/training-coach/commit/d150809f8d109ae632901df7415b99e178883012))
* **bot:** band offers and alerts, proposals and plan notices per person ([#654](https://github.com/LDoyleDev/training-coach/issues/654)) ([1f18f68](https://github.com/LDoyleDev/training-coach/commit/1f18f68807adff28957e4a992876515320e93bea))
* **bot:** band, daily check and proposals use the sender's data and consent ([#634](https://github.com/LDoyleDev/training-coach/issues/634)) ([b34159c](https://github.com/LDoyleDev/training-coach/commit/b34159c56b987c1dd017abe9ff3434a0cc04b6cb))
* **bot:** morning, nudge and review per person (joining step 9) ([#652](https://github.com/LDoyleDev/training-coach/issues/652)) ([1ccd713](https://github.com/LDoyleDev/training-coach/commit/1ccd713ac6138a71a086d8537816fc5cf64ad735))
* **bot:** one sender gate before every handler (ADR-0089) ([#615](https://github.com/LDoyleDev/training-coach/issues/615)) ([71cf9b0](https://github.com/LDoyleDev/training-coach/commit/71cf9b035c36938f87f404c3f50316df482156b8))
* **bot:** progress, habits, stretching, undo and share use the sender's data ([#632](https://github.com/LDoyleDev/training-coach/issues/632)) ([3bc6efb](https://github.com/LDoyleDev/training-coach/commit/3bc6efb0c8509f555ff03e6ed71c510609d46936))
* **bot:** today, logs, settings and sign-in use the sender's own data ([#624](https://github.com/LDoyleDev/training-coach/issues/624)) ([69e2a12](https://github.com/LDoyleDev/training-coach/commit/69e2a125210815aa416253aa394830cf458f49eb))
* **bot:** unlink, leave and erase drop the person's in-memory bot state ([#648](https://github.com/LDoyleDev/training-coach/issues/648)) ([0056301](https://github.com/LDoyleDev/training-coach/commit/0056301512050d69656d3e56d44a988c0b43eeb7))
* **db:** the 2-, 3- and 4-day starters in the seed (any-level S1) ([#628](https://github.com/LDoyleDev/training-coach/issues/628)) ([294089e](https://github.com/LDoyleDev/training-coach/commit/294089eb4fc72e46014bea0c08a1bc43c5f54966))
* **db:** the starters' gym swaps in the seed, and a writer per person ([#650](https://github.com/LDoyleDev/training-coach/issues/650)) ([1f01418](https://github.com/LDoyleDev/training-coach/commit/1f01418da587579ee9b5fa5912d12006ef9fe888))
* **domain:** rest places in the queue, as rest days after a session ([#626](https://github.com/LDoyleDev/training-coach/issues/626)) ([41bb03e](https://github.com/LDoyleDev/training-coach/commit/41bb03e47ad015dc72eead80472c2c2ecd0e8a37))
* **web:** connect Telegram on Account with the bot's code (ADR-0089) ([#644](https://github.com/LDoyleDev/training-coach/issues/644)) ([ecce62d](https://github.com/LDoyleDev/training-coach/commit/ecce62dbdb9f5195328e1089d0427bd6a074ca1f))
* **web:** joining says it's a private test for family and friends ([#619](https://github.com/LDoyleDev/training-coach/issues/619)) ([f2d8b8e](https://github.com/LDoyleDev/training-coach/commit/f2d8b8ed87ebe912e2847687037c4df864389042))
* **web:** the consent card and Account's list (ADR-0090) ([#620](https://github.com/LDoyleDev/training-coach/issues/620)) ([a27f79d](https://github.com/LDoyleDev/training-coach/commit/a27f79da8d01b944f45f8a1ef609ed73c83beb14))
* **web:** the health questions are answered on the device (ADR-0085) ([#612](https://github.com/LDoyleDev/training-coach/issues/612)) ([2a99863](https://github.com/LDoyleDev/training-coach/commit/2a9986360712945d155653f9dcc0a51221a366fe))


### Bug Fixes

* **api:** a member's erase drops their Telegram link ([#609](https://github.com/LDoyleDev/training-coach/issues/609)) ([e58836f](https://github.com/LDoyleDev/training-coach/commit/e58836f19ab898bb4494de3c62f14817463a447e))
* **api:** a waiting health proposal stays hidden while its yes is out of date ([#640](https://github.com/LDoyleDev/training-coach/issues/640)) ([4d8ad3b](https://github.com/LDoyleDev/training-coach/commit/4d8ad3bf7fde2aefeae4c52371055bf46815e001))
* **api:** saving a body or heart-rate proposal needs a current yes ([#636](https://github.com/LDoyleDev/training-coach/issues/636)) ([ea7337f](https://github.com/LDoyleDev/training-coach/commit/ea7337fde40f0872cf368e489a422e20c4994278))
* **bot:** start-up never takes a member's link; owner alerts follow it ([#614](https://github.com/LDoyleDev/training-coach/issues/614)) ([de81645](https://github.com/LDoyleDev/training-coach/commit/de8164583318d7201e59cc1505f1d6d1f59f25b4))
* **db:** users ids are never reused ([#647](https://github.com/LDoyleDev/training-coach/issues/647)) ([3811c9f](https://github.com/LDoyleDev/training-coach/commit/3811c9fdece0f369c5b37d1f52aa91200bcc66a1))


### Documentation

* **docs:** a short DPIA draft for the private test ([#622](https://github.com/LDoyleDev/training-coach/issues/622)) ([dd1fe04](https://github.com/LDoyleDev/training-coach/commit/dd1fe04374b4332f711519d19b4244c0a1c1ffd3))
* **docs:** ADR-0089, Telegram for members ([#613](https://github.com/LDoyleDev/training-coach/issues/613)) ([9799232](https://github.com/LDoyleDev/training-coach/commit/9799232906718e52c0de576c78cca07fe73ea157))
* **docs:** ADR-0090, consent per category and family and friends first ([#616](https://github.com/LDoyleDev/training-coach/issues/616)) ([260fca8](https://github.com/LDoyleDev/training-coach/commit/260fca827d3c0c15f8fd6e5f01c72ad3bb240d49))
* **docs:** joining step 6 done; step 8's first two parts done ([#621](https://github.com/LDoyleDev/training-coach/issues/621)) ([d22c1dd](https://github.com/LDoyleDev/training-coach/commit/d22c1ddf81b7005fff83f1df3f4d70a0cb1a1e45))
* **docs:** session log for 1.19.0, and Liam's 7 Nov answers ([#610](https://github.com/LDoyleDev/training-coach/issues/610)) ([a879ab7](https://github.com/LDoyleDev/training-coach/commit/a879ab761f7e3d6be2df4f6c3763f7763ab2d140))
* **docs:** the starters by days a week and place, approved ([#588](https://github.com/LDoyleDev/training-coach/issues/588)) ([62b3933](https://github.com/LDoyleDev/training-coach/commit/62b39339c9bbe28fc115361fa971af899d3b2f52))

## [1.19.0](https://github.com/LDoyleDev/training-coach/compare/v1.18.1...v1.19.0) (2026-11-07)


### Features

* **api:** a member can leave, kept gone after a restore by a left list ([#600](https://github.com/LDoyleDev/training-coach/issues/600)) ([1dc40af](https://github.com/LDoyleDev/training-coach/commit/1dc40afd8d4e24f2bd29c15cb63d59780f089b53))
* **api:** a member leaves, and an admin removes one, from the web ([#602](https://github.com/LDoyleDev/training-coach/issues/602)) ([5c3a796](https://github.com/LDoyleDev/training-coach/commit/5c3a796bdc4876e4ac07b0a22e4287ee0d229e7c))
* **api:** a release changing an exercise in your plan tells you ([#582](https://github.com/LDoyleDev/training-coach/issues/582)) ([084bc50](https://github.com/LDoyleDev/training-coach/commit/084bc5024d1996af01946485ce9ba30c6c783559))
* **api:** an admin's recovery link for a member who lost their passkey ([#605](https://github.com/LDoyleDev/training-coach/issues/605)) ([0d19188](https://github.com/LDoyleDev/training-coach/commit/0d19188cb08bbbf936fb5c0be934f9a289794f8c))
* **api:** invites an admin makes and someone joins with, behind TC_MULTI_USER ([#596](https://github.com/LDoyleDev/training-coach/issues/596)) ([9982d9e](https://github.com/LDoyleDev/training-coach/commit/9982d9e9b2a973aa4c3c81a87c0565ae6668f065))
* **api:** members are training-only until the lawyer's review ([#608](https://github.com/LDoyleDev/training-coach/issues/608)) ([792a8c1](https://github.com/LDoyleDev/training-coach/commit/792a8c118673ae9160a0ad677263d0b7e74d4490))
* **api:** the members' 30-day wind-down when TC_MULTI_USER goes off ([#604](https://github.com/LDoyleDev/training-coach/issues/604)) ([c75a569](https://github.com/LDoyleDev/training-coach/commit/c75a5693043018473169e4421cbc68954483ff10))
* **api:** warn of a session over an hour and of pushing without pulling ([#593](https://github.com/LDoyleDev/training-coach/issues/593)) ([5bd4bde](https://github.com/LDoyleDev/training-coach/commit/5bd4bde77d1a802ac36a4ddff4a4f276da366fc4))
* **api:** with TC_MULTI_USER off, the app is closed to members ([#601](https://github.com/LDoyleDev/training-coach/issues/601)) ([2469772](https://github.com/LDoyleDev/training-coach/commit/246977228f4a34dc03ef7e121be06d062dbb7ec4))
* **bot:** a member's daily cap on the shared Groq key ([#598](https://github.com/LDoyleDev/training-coach/issues/598)) ([dd20e62](https://github.com/LDoyleDev/training-coach/commit/dd20e622bf6ee9edef0dfc1a11f5639597793fc8))
* **db:** people get a role, admin or member, behind TC_MULTI_USER ([#595](https://github.com/LDoyleDev/training-coach/issues/595)) ([7aca8b1](https://github.com/LDoyleDev/training-coach/commit/7aca8b14753cd85fbc2a1bf7ecd0d2f19b372a3c))
* **web:** a muscle on the map names what would add to it ([#594](https://github.com/LDoyleDev/training-coach/issues/594)) ([e14e8bd](https://github.com/LDoyleDev/training-coach/commit/e14e8bde213e5809487a3ca5aa054769837d214f))
* **web:** a recovery link on People, and the notice on Account after one ([#607](https://github.com/LDoyleDev/training-coach/issues/607)) ([2992116](https://github.com/LDoyleDev/training-coach/commit/29921168dd7d87faddf163e47d959df95cbb0e15))
* **web:** edit your own plan, saved as one version with a note ([#583](https://github.com/LDoyleDev/training-coach/issues/583)) ([8f82a65](https://github.com/LDoyleDev/training-coach/commit/8f82a65feff8c2e4d2aa399a49d2da3b8945fe9f))
* **web:** Leave on Account for a member, Remove on People for the admin ([#603](https://github.com/LDoyleDev/training-coach/issues/603)) ([60ff6e5](https://github.com/LDoyleDev/training-coach/commit/60ff6e547eab68d4032df96bb6227616bb3ba76f))
* **web:** People on Account and the /join page, behind TC_MULTI_USER ([#597](https://github.com/LDoyleDev/training-coach/issues/597)) ([a58e761](https://github.com/LDoyleDev/training-coach/commit/a58e76113b2656e9cada2a2fa47c1b424fc543e9))
* **web:** the body map follows your edits as you make them ([#584](https://github.com/LDoyleDev/training-coach/issues/584)) ([cd65142](https://github.com/LDoyleDev/training-coach/commit/cd65142b2894519fd453feff258c23b174c7022d))
* **web:** the closing page for a member while TC_MULTI_USER is off ([#606](https://github.com/LDoyleDev/training-coach/issues/606)) ([dcfe639](https://github.com/LDoyleDev/training-coach/commit/dcfe6397b5da83394ffb58d4cba98eac14f319c7))
* **web:** the picker shows who an exercise is for and what it needs ([#592](https://github.com/LDoyleDev/training-coach/issues/592)) ([665308c](https://github.com/LDoyleDev/training-coach/commit/665308c4737d503b301d486e1c2696b22bc41018))


### Bug Fixes

* **api:** erasing keeps the person's role, so the owner stays admin ([#599](https://github.com/LDoyleDev/training-coach/issues/599)) ([f2bed81](https://github.com/LDoyleDev/training-coach/commit/f2bed81b1889f561691fa5dc5a827468a5c22f40))


### Documentation

* **docs:** session log for 1.18.1, lengths shorter than the session ([#590](https://github.com/LDoyleDev/training-coach/issues/590)) ([3830a26](https://github.com/LDoyleDev/training-coach/commit/3830a269632d37f830bef5ce116eeb200273e224))

## [1.18.1](https://github.com/LDoyleDev/training-coach/compare/v1.18.0...v1.18.1) (2026-11-07)


### Bug Fixes

* **api:** offer only lengths shorter than the session due ([#586](https://github.com/LDoyleDev/training-coach/issues/586)) ([9e3ce4d](https://github.com/LDoyleDev/training-coach/commit/9e3ce4d804999a4973279b781b74dfbd35ac8a2d))


### Documentation

* **docs:** session log for 1.18.0, plans per person ([#587](https://github.com/LDoyleDev/training-coach/issues/587)) ([aac37b9](https://github.com/LDoyleDev/training-coach/commit/aac37b95253c817b6577b2e877c4b6a670bb16eb))

## [1.18.0](https://github.com/LDoyleDev/training-coach/compare/v1.17.0...v1.18.0) (2026-11-06)


### Features

* **api:** the owner saves a plan.toml change as one version ([#581](https://github.com/LDoyleDev/training-coach/issues/581)) ([5281962](https://github.com/LDoyleDev/training-coach/commit/5281962fd3f91c51b0fa4ac649e9b02627681001))
* **api:** the Plan page and body map read the plan rows, not plan.toml ([#579](https://github.com/LDoyleDev/training-coach/issues/579)) ([4fe4329](https://github.com/LDoyleDev/training-coach/commit/4fe4329a43c35d93200c3fa7da9dc5b4b6e22835))
* **db:** each person owns their sessions, items and plan versions ([#580](https://github.com/LDoyleDev/training-coach/issues/580)) ([65292c1](https://github.com/LDoyleDev/training-coach/commit/65292c1e7b2e87736360f47bb7ab3465545d4555))


### Documentation

* **docs:** session log for 1.17.0, the reverse fly on dumbbells ([#573](https://github.com/LDoyleDev/training-coach/issues/573)) ([32bc8f9](https://github.com/LDoyleDev/training-coach/commit/32bc8f9a57f6ca8c67d28cab992cac9663b19ae3))
* **docs:** step 5 refuses other people; the import is the owner's alone ([#575](https://github.com/LDoyleDev/training-coach/issues/575)) ([d439bab](https://github.com/LDoyleDev/training-coach/commit/d439babd1dd4f70b62b151ce2a9e7af57fbc4b9e))
* **docs:** step 5 review: erase, seed guards, the import and the build ([#576](https://github.com/LDoyleDev/training-coach/issues/576)) ([d49e677](https://github.com/LDoyleDev/training-coach/commit/d49e67786a84e81d812ce4b639becd71428fc7ef))

## [1.17.0](https://github.com/LDoyleDev/training-coach/compare/v1.16.0...v1.17.0) (2026-11-04)


### Features

* **db:** reverse fly on dumbbells that take load, not one 8 kg kettlebell ([#571](https://github.com/LDoyleDev/training-coach/issues/571)) ([38a765e](https://github.com/LDoyleDev/training-coach/commit/38a765eca554f32f3b18643fd30c9b487a259117))


### Documentation

* **docs:** session log for 1.16.0, the EU and EEA only ([#568](https://github.com/LDoyleDev/training-coach/issues/568)) ([5b4bd13](https://github.com/LDoyleDev/training-coach/commit/5b4bd13f1998bc47aacb2ceaea0b57e06114a520))

## [1.16.0](https://github.com/LDoyleDev/training-coach/compare/v1.15.0...v1.16.0) (2026-11-03)


### Features

* **api:** pause the bot and MCP 30 days after a visit from Europe ([#514](https://github.com/LDoyleDev/training-coach/issues/514)) ([23704ad](https://github.com/LDoyleDev/training-coach/commit/23704ad4f2cf7bac4925c15f7da8e4b00e086d4f))
* **web:** ask where the person lives, EU and EEA only ([#515](https://github.com/LDoyleDev/training-coach/issues/515)) ([0fef1eb](https://github.com/LDoyleDev/training-coach/commit/0fef1eb0349b7a0e1072f9e23a0ffec6f9acd21e))


### Documentation

* **docs:** band runbook: heart rate waits for Mi Fitness, MIUI kills ([#567](https://github.com/LDoyleDev/training-coach/issues/567)) ([0eaabdc](https://github.com/LDoyleDev/training-coach/commit/0eaabdc9658bfcfb8c5672295a040c77236631a0))
* **docs:** restore drill of 2 Nov passed on the Pi before step 5 ([#566](https://github.com/LDoyleDev/training-coach/issues/566)) ([9e54540](https://github.com/LDoyleDev/training-coach/commit/9e545402d7c9b78383183accc78796998475b341))
* **docs:** session log for 1.15.0 and reader 0.0.8 ([#559](https://github.com/LDoyleDev/training-coach/issues/559)) ([83db79b](https://github.com/LDoyleDev/training-coach/commit/83db79b66b01391ba41bd2ff292907bed5ac09bb))

## [1.15.0](https://github.com/LDoyleDev/training-coach/compare/v1.14.0...v1.15.0) (2026-11-01)


### Features

* **bot:** a test day's warm-up line says 10 minutes, sessions keep 5 ([#555](https://github.com/LDoyleDev/training-coach/issues/555)) ([05d5f00](https://github.com/LDoyleDev/training-coach/commit/05d5f008b3efeec38db5a818faa9066a60f2facb))
* **web:** stop signs with 112 and a time limit, checked for Europe ([#556](https://github.com/LDoyleDev/training-coach/issues/556)) ([33380b9](https://github.com/LDoyleDev/training-coach/commit/33380b99cae85457f38bb2e31c200fc01f16fd9a))


### Documentation

* **docs:** home and gym versions of the 3- and 4-day starters, accepted ([#484](https://github.com/LDoyleDev/training-coach/issues/484)) ([82241ee](https://github.com/LDoyleDev/training-coach/commit/82241ee0d8d79def4662da184c0ceb6081f2ca3d))
* **docs:** session log for 1.14.0 ([#551](https://github.com/LDoyleDev/training-coach/issues/551)) ([318d40e](https://github.com/LDoyleDev/training-coach/commit/318d40e0ee1cdba1184926b6bb57a6dc009684ad))
* **docs:** the plan import ships with builder step 5 (Liam, 1 Nov) ([#557](https://github.com/LDoyleDev/training-coach/issues/557)) ([81b02e6](https://github.com/LDoyleDev/training-coach/commit/81b02e6f2626e1710895fe9060e7dca820061729))

## [1.14.0](https://github.com/LDoyleDev/training-coach/compare/v1.13.0...v1.14.0) (2026-11-01)


### Features

* **db:** knees marks on the new deep steps, names that fit the ladders ([#546](https://github.com/LDoyleDev/training-coach/issues/546)) ([a9b25cd](https://github.com/LDoyleDev/training-coach/commit/a9b25cd50642e1e70e0428679ddbdc8aeba09892))
* **web:** draw the door-frame row and curl ([#549](https://github.com/LDoyleDev/training-coach/issues/549)) ([b4cfbd8](https://github.com/LDoyleDev/training-coach/commit/b4cfbd8998cd13382af19a3b6ceb22a2835ced43))
* **web:** draw the lower ladder steps, so none is left without a figure ([#548](https://github.com/LDoyleDev/training-coach/issues/548)) ([fd54206](https://github.com/LDoyleDev/training-coach/commit/fd542064791082a53e8835197bab82de5dc88207))


### Documentation

* **docs:** session log for 1.13.0 ([#547](https://github.com/LDoyleDev/training-coach/issues/547)) ([a7ba5ff](https://github.com/LDoyleDev/training-coach/commit/a7ba5ffbcf32d3e780bb3d8ac1f143d2a309a36d))

## [1.13.0](https://github.com/LDoyleDev/training-coach/compare/v1.12.0...v1.13.0) (2026-11-01)


### Features

* **db:** extend fifteen ladders downward and bring back the Squat (ADR-0083) ([#534](https://github.com/LDoyleDev/training-coach/issues/534)) ([910f2b0](https://github.com/LDoyleDev/training-coach/commit/910f2b0907c74fed1e91df9a18c3aa195289e70d))


### Documentation

* **docs:** session log for 1.12.0 ([#542](https://github.com/LDoyleDev/training-coach/issues/542)) ([3011439](https://github.com/LDoyleDev/training-coach/commit/30114395f65dbef693ed65f2e84abbda0e321efc))

## [1.12.0](https://github.com/LDoyleDev/training-coach/compare/v1.11.0...v1.12.0) (2026-11-01)


### Features

* **api:** "Easy on my knees", a fifth preference (ADR-0083) ([#541](https://github.com/LDoyleDev/training-coach/issues/541)) ([f582fe3](https://github.com/LDoyleDev/training-coach/commit/f582fe321c0153645acde82dcab8460ab6cc4c5f))
* **api:** an optional last set of as many good reps as you can (ADR-0084) ([#536](https://github.com/LDoyleDev/training-coach/issues/536)) ([78bd11c](https://github.com/LDoyleDev/training-coach/commit/78bd11c776042b90f59d544de5f1d18985fcd09f))
* **api:** away, no equipment, as a third place on Today's switch (ADR-0086) ([#538](https://github.com/LDoyleDev/training-coach/issues/538)) ([4270b2b](https://github.com/LDoyleDev/training-coach/commit/4270b2b27f336b81e686da1e7e02218c31c07e48))
* **api:** minutes per session on Account, the default length (ADR-0082) ([#529](https://github.com/LDoyleDev/training-coach/issues/529)) ([6f911fe](https://github.com/LDoyleDev/training-coach/commit/6f911fe3eb280649a732f889458226cd633aba39))
* **api:** the four preferences lock the steps they mark (ADR-0083) ([#531](https://github.com/LDoyleDev/training-coach/issues/531)) ([8104c2c](https://github.com/LDoyleDev/training-coach/commit/8104c2c9814f0d49841e95bda8228cfa5497d248))
* **db:** away versions of the seven sessions and door-frame pulls (ADR-0086) ([#539](https://github.com/LDoyleDev/training-coach/issues/539)) ([c9d7058](https://github.com/LDoyleDev/training-coach/commit/c9d7058f48a141299755229ba6423f64579b0752))
* **db:** balance and interval walk entries, and the way-in rule (ADR-0083) ([#520](https://github.com/LDoyleDev/training-coach/issues/520)) ([9cd41ab](https://github.com/LDoyleDev/training-coach/commit/9cd41abc37591b2f0c7f38909f0c9c27b912f166))
* **db:** entry exercises for the lower body and core (ADR-0083) ([#518](https://github.com/LDoyleDev/training-coach/issues/518)) ([9038ae4](https://github.com/LDoyleDev/training-coach/commit/9038ae48463d891ea40ba16488ba025773767ec4))
* **db:** entry exercises for the upper body, with bands (ADR-0083) ([#519](https://github.com/LDoyleDev/training-coach/issues/519)) ([cc55cc2](https://github.com/LDoyleDev/training-coach/commit/cc55cc264e80688bf18c390864a215eb3bb4e473))
* **domain:** suggest a step down when the range's bottom is out of reach ([#530](https://github.com/LDoyleDev/training-coach/issues/530)) ([cd5949c](https://github.com/LDoyleDev/training-coach/commit/cd5949c6bad48831d022e7403898aea52679fcd0))
* **web:** ease back in after three weeks away, one step down today ([#533](https://github.com/LDoyleDev/training-coach/issues/533)) ([79e8678](https://github.com/LDoyleDev/training-coach/commit/79e86789aa49b884f9a1770dc8325384c1338163))
* **web:** figures for the entry exercises (ADR-0063, ADR-0083) ([#523](https://github.com/LDoyleDev/training-coach/issues/523)) ([dd3b7fa](https://github.com/LDoyleDev/training-coach/commit/dd3b7fadb2c1eee71e2ce450ba17164f702c4625))
* **web:** offer Step down next to Move up on Plan, saved screen, bot ([#532](https://github.com/LDoyleDev/training-coach/issues/532)) ([199a524](https://github.com/LDoyleDev/training-coach/commit/199a524f63be8471376f9b0e75d0f6340283e58a))


### Documentation

* **docs:** session log for 1.11.0 ([#521](https://github.com/LDoyleDev/training-coach/issues/521)) ([856f923](https://github.com/LDoyleDev/training-coach/commit/856f9236efab2ab963612d5c6cd5facdafa814f1))

## [1.11.0](https://github.com/LDoyleDev/training-coach/compare/v1.10.0...v1.11.0) (2026-10-31)


### Features

* **api:** answer 451 outside the EU and EEA (ADR-0085 layer 2) ([#513](https://github.com/LDoyleDev/training-coach/issues/513)) ([45d3f57](https://github.com/LDoyleDev/training-coach/commit/45d3f57e0dc3af427cb4db13fdd548567d4e3817))
* **api:** short on time today: a day's length and the trimmed session ([#510](https://github.com/LDoyleDev/training-coach/issues/510)) ([d452c1d](https://github.com/LDoyleDev/training-coach/commit/d452c1d7ada6c3e08c647701770ececda4fc0021))
* **bot:** the work list and morning message follow the day's length ([#517](https://github.com/LDoyleDev/training-coach/issues/517)) ([84ff161](https://github.com/LDoyleDev/training-coach/commit/84ff161c518ad58e8977d46bc4e07a4285a60c92))
* **db:** a level and marks on every ladder step, and failure_ok ([#506](https://github.com/LDoyleDev/training-coach/issues/506)) ([f6392b1](https://github.com/LDoyleDev/training-coach/commit/f6392b1910599f46497d43e459a038bf89c285d8))
* **db:** record each guided day's plan and judge progress on it ([#509](https://github.com/LDoyleDev/training-coach/issues/509)) ([08e3580](https://github.com/LDoyleDev/training-coach/commit/08e3580cd3a9e09d9f52e6db78c690aeef174f99))
* **domain:** judge a shorter day on its own planned sets ([#501](https://github.com/LDoyleDev/training-coach/issues/501)) ([5614794](https://github.com/LDoyleDev/training-coach/commit/56147946189c9c28b8f2f548c05e8f2c04e33e89))
* **domain:** trim a session to fit the minutes ([#502](https://github.com/LDoyleDev/training-coach/issues/502)) ([527bc10](https://github.com/LDoyleDev/training-coach/commit/527bc1080e9cea233f6b9fe6f89382f1fc6922b7))
* **web:** short on time today: pick 40, 30 or 20 min on Today ([#516](https://github.com/LDoyleDev/training-coach/issues/516)) ([5af6722](https://github.com/LDoyleDev/training-coach/commit/5af6722b06d4e4368b95407f3959c4f0a4995a0a))
* **web:** stop signs, the talk-test option and a breathing cue ([#505](https://github.com/LDoyleDev/training-coach/issues/505)) ([301273a](https://github.com/LDoyleDev/training-coach/commit/301273a0d7b0e38143eba2aefa6f36424df1c5e9))


### Documentation

* **docs:** decide shorter sessions, lower ladders and Europe-only safety ([#495](https://github.com/LDoyleDev/training-coach/issues/495)) ([c80c25f](https://github.com/LDoyleDev/training-coach/commit/c80c25f4e2bbf12bed090dc0ddaf83bed2db19fc)), closes [#494](https://github.com/LDoyleDev/training-coach/issues/494)
* **docs:** session log for 1.10.0 ([#490](https://github.com/LDoyleDev/training-coach/issues/490)) ([a1dba1b](https://github.com/LDoyleDev/training-coach/commit/a1dba1ba588600071bdc1c7ea46d9b6cb60fe9b3))

## [1.10.0](https://github.com/LDoyleDev/training-coach/compare/v1.9.0...v1.10.0) (2026-10-30)


### Features

* **domain:** the warm-up is 5 minutes, not 10 ([#485](https://github.com/LDoyleDev/training-coach/issues/485)) ([603c539](https://github.com/LDoyleDev/training-coach/commit/603c539f60ea7f947a3d80d6950cf098e5d047d6))
* **web:** "Can you do ...?" level questions on every ladder step ([#489](https://github.com/LDoyleDev/training-coach/issues/489)) ([4789cdf](https://github.com/LDoyleDev/training-coach/commit/4789cdf68b89835336f4a85296a14c6b8f623250))


### Bug Fixes

* **web:** the chart's side labels fit beside it, never cut off ([#480](https://github.com/LDoyleDev/training-coach/issues/480)) ([ff7653f](https://github.com/LDoyleDev/training-coach/commit/ff7653fc619e92d7cba64651ff1753e201d5ad88))


### Documentation

* **docs:** session log for 1.9.0 ([#472](https://github.com/LDoyleDev/training-coach/issues/472)) ([8707da7](https://github.com/LDoyleDev/training-coach/commit/8707da79b0173c3b444edfcdbe6c6e107cdbe32f))
* **docs:** what reads the plan, and a draft migration for step 5 ([#487](https://github.com/LDoyleDev/training-coach/issues/487)) ([e54b0b3](https://github.com/LDoyleDev/training-coach/commit/e54b0b398d3e012d3ed65f0c04eb9457809d93ba))

## [1.9.0](https://github.com/LDoyleDev/training-coach/compare/v1.8.0...v1.9.0) (2026-10-30)


### Features

* **db:** pull-ups and chin-ups end in one vest step that takes load ([#465](https://github.com/LDoyleDev/training-coach/issues/465)) ([bca43ec](https://github.com/LDoyleDev/training-coach/commit/bca43ec79a0216c6ab8349374dace277d90cd62f))
* **domain:** a vest or backpack takes load; dips gain a loaded step ([#459](https://github.com/LDoyleDev/training-coach/issues/459)) ([c818a33](https://github.com/LDoyleDev/training-coach/commit/c818a33d43608ee16b3b8467bdf137e7742958b2))
* **web:** Plan's exercise lists follow the home or gym view ([#455](https://github.com/LDoyleDev/training-coach/issues/455)) ([7c6b532](https://github.com/LDoyleDev/training-coach/commit/7c6b5323294251cc9720f12ef9c92a4d2cf1bde5))
* **web:** Plan's ladder cards name the weights of the last session and the best ([#463](https://github.com/LDoyleDev/training-coach/issues/463)) ([a7ee764](https://github.com/LDoyleDev/training-coach/commit/a7ee7649e3e63633d8334fe077e2310b9b591b18))
* **web:** Progress and /progress name the weights of the last session and the best ([#458](https://github.com/LDoyleDev/training-coach/issues/458)) ([0a551de](https://github.com/LDoyleDev/training-coach/commit/0a551dee135d3db0e0664466dfe049dd67f86f19))


### Bug Fixes

* **db:** close the migration engine and the tests' SQLite connections ([#461](https://github.com/LDoyleDev/training-coach/issues/461)) ([1d6e991](https://github.com/LDoyleDev/training-coach/commit/1d6e991fb72ed21df46d73bf22967577a8bf498f))
* **web:** the weight strip's labels fit beside it, never cut off ([#467](https://github.com/LDoyleDev/training-coach/issues/467)) ([9d54f9c](https://github.com/LDoyleDev/training-coach/commit/9d54f9c58862ea6f9adf5442dcabfcf01d9a6106))


### Documentation

* **adr:** accept ADR-0081, confirm ADR-0072's built choices ([#449](https://github.com/LDoyleDev/training-coach/issues/449)) ([06fff29](https://github.com/LDoyleDev/training-coach/commit/06fff293cdcb405e654053672b835f15859fa202))
* **docs:** threat model row for the home kit (equipment) ([#451](https://github.com/LDoyleDev/training-coach/issues/451)) ([85a75f2](https://github.com/LDoyleDev/training-coach/commit/85a75f2e9a78ce955d1374ab2a87e24c9bd8b507))

## [1.8.0](https://github.com/LDoyleDev/training-coach/compare/v1.7.1...v1.8.0) (2026-10-29)


### Features

* **api:** each person's own weight steps for - and + and the next weight ([#436](https://github.com/LDoyleDev/training-coach/issues/436)) ([121190c](https://github.com/LDoyleDev/training-coach/commit/121190c664a94ef5b12ec9e90d117ca5a212248b))
* **api:** propose_log takes a weight per set on loaded steps ([#434](https://github.com/LDoyleDev/training-coach/issues/434)) ([a6ffcde](https://github.com/LDoyleDev/training-coach/commit/a6ffcded3250d8e92dcb2194a2bf8d110601b79f))
* **bot:** new bests name the weight they were set at ([#446](https://github.com/LDoyleDev/training-coach/issues/446)) ([cacf540](https://github.com/LDoyleDev/training-coach/commit/cacf54048ffff5ea063ef3be428fa5ea189d4d84))
* **domain:** at home the next weight is the next one owned ([#445](https://github.com/LDoyleDev/training-coach/issues/445)) ([0f1ce22](https://github.com/LDoyleDev/training-coach/commit/0f1ce22f9a5f4e3ca4648684013a0fd718efc648))
* **web:** body map counts the home or gym versions ([#433](https://github.com/LDoyleDev/training-coach/issues/433)) ([48dd866](https://github.com/LDoyleDev/training-coach/commit/48dd86676047ac642d061ecf9cd6252af818da67))
* **web:** the day's log and the AI's read tools show each set's weight ([#439](https://github.com/LDoyleDev/training-coach/issues/439)) ([92e166d](https://github.com/LDoyleDev/training-coach/commit/92e166d1a7957fcca648da30f8fcfa716d487324))


### Bug Fixes

* **api:** /healthz through the tunnel says only that the app is up ([#447](https://github.com/LDoyleDev/training-coach/issues/447)) ([b2fdc47](https://github.com/LDoyleDev/training-coach/commit/b2fdc47a74164537df7e0da97cbc07db3ab8d121))
* **db:** a SQLite savepoint opened first no longer commits on release ([#443](https://github.com/LDoyleDev/training-coach/issues/443)) ([451b13e](https://github.com/LDoyleDev/training-coach/commit/451b13ebe524453c153ced0856ca012685e6faba))
* **web:** pec deck levers pass beside the head; Nordic curl drawn bigger ([#437](https://github.com/LDoyleDev/training-coach/issues/437)) ([3076125](https://github.com/LDoyleDev/training-coach/commit/3076125966987ef0ca8e12cff385425352bd8193))


### Documentation

* adb plan for the reader closing when the screen turns off ([#431](https://github.com/LDoyleDev/training-coach/issues/431)) ([d074b78](https://github.com/LDoyleDev/training-coach/commit/d074b78a6d4f2d26aff3dbba1a8152876b59b172))
* session log for 1.8.0 ([#448](https://github.com/LDoyleDev/training-coach/issues/448)) ([2500d49](https://github.com/LDoyleDev/training-coach/commit/2500d49a1b151b51da09609be0be20779f0bb6ff))

## [1.7.1](https://github.com/LDoyleDev/training-coach/compare/v1.7.0...v1.7.1) (2026-10-28)


### Bug Fixes

* **web:** archer push-up seen from in front of the head ([#422](https://github.com/LDoyleDev/training-coach/issues/422)) ([0feab91](https://github.com/LDoyleDev/training-coach/commit/0feab9183f1f7971ccd411f7747ebf817e42c4a8))
* **web:** figure props stand out from the dark paper ([#419](https://github.com/LDoyleDev/training-coach/issues/419)) ([5a06cb5](https://github.com/LDoyleDev/training-coach/commit/5a06cb59c4c9088cac66aa77f1dfbe497c73b896))
* **web:** front views fill their picture; machine pec deck; Pallof cable ([#417](https://github.com/LDoyleDev/training-coach/issues/417)) ([697f3ce](https://github.com/LDoyleDev/training-coach/commit/697f3ce9bc62e782aacf30501577922af5f4002f))
* **web:** Nordic curls hook under a sofa; reverse Nordics drawn bigger ([#420](https://github.com/LDoyleDev/training-coach/issues/420)) ([9b3afa8](https://github.com/LDoyleDev/training-coach/commit/9b3afa84199640eca67c3b8dabe0035c2267cce3))


### Documentation

* session log for the 1.7.1 wrap ([#424](https://github.com/LDoyleDev/training-coach/issues/424)) ([8f6f398](https://github.com/LDoyleDev/training-coach/commit/8f6f3986ba42aad73314be8d8d9574bac17c3c94))

## [1.7.0](https://github.com/LDoyleDev/training-coach/compare/v1.6.0...v1.7.0) (2026-10-28)


### Features

* **api:** today's session at home or at the gym, the person's switch ([#406](https://github.com/LDoyleDev/training-coach/issues/406)) ([63e4181](https://github.com/LDoyleDev/training-coach/commit/63e418125aa39ffa6f917fc8acca35a752dd7532))
* **db:** places: where you train and where each workout was done ([#398](https://github.com/LDoyleDev/training-coach/issues/398)) ([969e544](https://github.com/LDoyleDev/training-coach/commit/969e544bcae92f8413bec67e7c92541e6181f612))
* **domain:** gym versions of four sessions, from the gym catalogue ([#402](https://github.com/LDoyleDev/training-coach/issues/402)) ([f62e0fe](https://github.com/LDoyleDev/training-coach/commit/f62e0fe0a73c3b2c897ccc652d8da571118b5688))
* **web:** a Home | Gym switch on Today, asking before it drops sets ([#407](https://github.com/LDoyleDev/training-coach/issues/407)) ([9920b9d](https://github.com/LDoyleDev/training-coach/commit/9920b9d5c88963681f1d77b3ae6a07407b3f1834))
* **web:** barbell figures: back squat, RDL, hip thrust, back extension ([#397](https://github.com/LDoyleDev/training-coach/issues/397)) ([93f3120](https://github.com/LDoyleDev/training-coach/commit/93f312064ae15eb541e510d715c87feb5ffdc1a3))
* **web:** cable figures: lat pulldown, overhead extension, crunch, Pallof ([#405](https://github.com/LDoyleDev/training-coach/issues/405)) ([2bfcc38](https://github.com/LDoyleDev/training-coach/commit/2bfcc389c9cc58c61531fd9dac6d8f880b73e1b9))
* **web:** change an exercise's level during a session ([#413](https://github.com/LDoyleDev/training-coach/issues/413)) ([7e1b454](https://github.com/LDoyleDev/training-coach/commit/7e1b454e56ca2e2ae2a68f64f823a1ac1accd5f7))
* **web:** Copenhagen ankle-on-chair and deeper reverse Nordic figures ([#414](https://github.com/LDoyleDev/training-coach/issues/414)) ([7bb87da](https://github.com/LDoyleDev/training-coach/commit/7bb87daccab52c6092d9944d6d7aa97370e12e3e))
* **web:** dumbbell figures: presses, curls, wrist curl, row ([#400](https://github.com/LDoyleDev/training-coach/issues/400)) ([d413736](https://github.com/LDoyleDev/training-coach/commit/d41373679e47b99740fbf571bee91eec29bf9dd8))
* **web:** goblet split squat, single-leg and Nordic curl figures ([#409](https://github.com/LDoyleDev/training-coach/issues/409)) ([aa9c6ec](https://github.com/LDoyleDev/training-coach/commit/aa9c6ec5d7de47ef896954732440a831203e0a3a))
* **web:** lateral raise, fly and reverse fly, seen from the front ([#408](https://github.com/LDoyleDev/training-coach/issues/408)) ([d98ac12](https://github.com/LDoyleDev/training-coach/commit/d98ac12fbcebbf0ba8d1b86c2ea5aa0c767afad7))
* **web:** machine figures: leg press, leg extension, curl, calf raises ([#403](https://github.com/LDoyleDev/training-coach/issues/403)) ([c85a4fa](https://github.com/LDoyleDev/training-coach/commit/c85a4facbb0b88bb79398be7f3578739d7f98561))
* **web:** pistol, jump squat, calf, tibialis and swing step figures ([#410](https://github.com/LDoyleDev/training-coach/issues/410)) ([7d20237](https://github.com/LDoyleDev/training-coach/commit/7d20237667a62742be4e98ee24737c41f1519066))
* **web:** push-up, diamond and pike push-up step figures ([#415](https://github.com/LDoyleDev/training-coach/issues/415)) ([c5a550a](https://github.com/LDoyleDev/training-coach/commit/c5a550ab2e9545466bfd4b18b04f12e8af838216))


### Documentation

* session log for the 1.7.0 wrap; gym versions accepted ([#421](https://github.com/LDoyleDev/training-coach/issues/421)) ([8f18acf](https://github.com/LDoyleDev/training-coach/commit/8f18acff7ed1ebe1c5eff9307c00c3906292a961))

## [1.6.0](https://github.com/LDoyleDev/training-coach/compare/v1.5.0...v1.6.0) (2026-10-27)


### Features

* **web:** ring a loud, celebratory bell at the end of every session ([#411](https://github.com/LDoyleDev/training-coach/issues/411)) ([2c3f081](https://github.com/LDoyleDev/training-coach/commit/2c3f081bb62f9b9624a4e209b921032098e3f3f4))
* **web:** show the top for your kit on Home and the weekly review ([#399](https://github.com/LDoyleDev/training-coach/issues/399)) ([442fb04](https://github.com/LDoyleDev/training-coach/commit/442fb0449027170a2dc1f7b0b585eced24b7475b))


### Bug Fixes

* **bot:** say the top of a ladder in plain words, not plan.toml ([#396](https://github.com/LDoyleDev/training-coach/issues/396)) ([f802cfb](https://github.com/LDoyleDev/training-coach/commit/f802cfb6fbb276961219155e2bb4a8ff58b7eb5f))
* **infra:** reader names Health Connect's own data, not "_platform" ([#401](https://github.com/LDoyleDev/training-coach/issues/401)) ([50b2c62](https://github.com/LDoyleDev/training-coach/commit/50b2c623116e2b1124b35ff8cdda1934f5043c5c))


### Documentation

* session log for the 1.6.0 wrap ([#412](https://github.com/LDoyleDev/training-coach/issues/412)) ([57c5d2c](https://github.com/LDoyleDev/training-coach/commit/57c5d2c19a179235d453738d8f70d76adf09022a))

## [1.5.0](https://github.com/LDoyleDev/training-coach/compare/v1.4.0...v1.5.0) (2026-10-27)


### Features

* **api:** count all cardio, split by zone, targets from the plan ([#390](https://github.com/LDoyleDev/training-coach/issues/390)) ([1fa9b28](https://github.com/LDoyleDev/training-coach/commit/1fa9b2884e7b54958cd1ac04fbf51feeeb1bc01e))
* **web:** cardio by zone, what's left, and extra cardio on Plan ([#391](https://github.com/LDoyleDev/training-coach/issues/391)) ([c0cd7a0](https://github.com/LDoyleDev/training-coach/commit/c0cd7a033c48d5282dcd2d33b159e8dc3c04f0ff))


### Documentation

* session log for the 1.5.0 wrap ([#394](https://github.com/LDoyleDev/training-coach/issues/394)) ([c3e0e7f](https://github.com/LDoyleDev/training-coach/commit/c3e0e7f49f8f88ca41fdb29ac30781e7be00afaf))

## [1.4.0](https://github.com/LDoyleDev/training-coach/compare/v1.3.0...v1.4.0) (2026-10-27)


### Features

* **db:** sets record their weight on a loaded step (ADR-0072) ([#379](https://github.com/LDoyleDev/training-coach/issues/379)) ([5e424af](https://github.com/LDoyleDev/training-coach/commit/5e424affd90c973d5af14b6ed52c37a81834aa7c))
* **domain:** 23 gym exercises join the catalogue, each taking load ([#385](https://github.com/LDoyleDev/training-coach/issues/385)) ([cde4d6d](https://github.com/LDoyleDev/training-coach/commit/cde4d6d6942ab8e27b86141ed7d5a4c729aba4dc))
* **domain:** double progression suggests the next weight up ([#381](https://github.com/LDoyleDev/training-coach/issues/381)) ([61d5813](https://github.com/LDoyleDev/training-coach/commit/61d5813f8ebf527edb5ae3e7d730d35bb38e947d))
* **infra:** reader sends sleep, exercise and their deletions ([#374](https://github.com/LDoyleDev/training-coach/issues/374)) ([553e502](https://github.com/LDoyleDev/training-coach/commit/553e502266cf14656149f94bd035b502340ecf88))
* **infra:** reader syncs in the background and shows the last 7 days ([#375](https://github.com/LDoyleDev/training-coach/issues/375)) ([6ace269](https://github.com/LDoyleDev/training-coach/commit/6ace2695ecfd732f4d8d826a7962955aef1732cc))
* **parser:** typed and spoken logs take a weight, "rows 10 10 9 at 16" ([#380](https://github.com/LDoyleDev/training-coach/issues/380)) ([451a2bb](https://github.com/LDoyleDev/training-coach/commit/451a2bb57269d9f315929de84e79a64aa807d44a))
* **web:** Account and the bot name the reader; runbook for it ([#376](https://github.com/LDoyleDev/training-coach/issues/376)) ([b89f4b3](https://github.com/LDoyleDev/training-coach/commit/b89f4b367eaf140cfbc397f2c59cc4e2b270db61))
* **web:** Copenhagen plank from the front and side; calf raise close-up ([#377](https://github.com/LDoyleDev/training-coach/issues/377)) ([f21d67f](https://github.com/LDoyleDev/training-coach/commit/f21d67f9d749ec0083771c4329fc639e99ac760e))
* **web:** each weight is a period on the chart, with a kg strip under it ([#383](https://github.com/LDoyleDev/training-coach/issues/383)) ([ad77e37](https://github.com/LDoyleDev/training-coach/commit/ad77e37f9f4ebbc36a7fb2a97c8df5ca0bd9a59b))
* **web:** figures by ladder step: vest, dip bars, suitcase, hammer curl ([#378](https://github.com/LDoyleDev/training-coach/issues/378)) ([726437c](https://github.com/LDoyleDev/training-coach/commit/726437c6d13fef42dfc25c63e6639e8138a52c74))
* **web:** plank front view in perspective, dips with feet off the floor ([#389](https://github.com/LDoyleDev/training-coach/issues/389)) ([7d8dee9](https://github.com/LDoyleDev/training-coach/commit/7d8dee9d39d9c3d883e17413c6bd56eedd970e10))
* **web:** the set screen records the weight, with − and + from last time ([#382](https://github.com/LDoyleDev/training-coach/issues/382)) ([67f97ac](https://github.com/LDoyleDev/training-coach/commit/67f97ac735cc4255b7957d2e5b8a046d6b2cc4a4))


### Bug Fixes

* **infra:** pin the backend to Python 3.12, the Pi's version ([#384](https://github.com/LDoyleDev/training-coach/issues/384)) ([01310ef](https://github.com/LDoyleDev/training-coach/commit/01310efbeda30bd81eb4fcf034732b3ffdb27d78))


### Documentation

* session log for the 1.4.0 wrap ([#392](https://github.com/LDoyleDev/training-coach/issues/392)) ([872fbaa](https://github.com/LDoyleDev/training-coach/commit/872fbaa29a598484a1e16632a98f269546fabec8))

## [1.3.0](https://github.com/LDoyleDev/training-coach/compare/v1.2.0...v1.3.0) (2026-10-26)


### Features

* **domain:** rep ranges top out at 18; say what opens the next level ([#372](https://github.com/LDoyleDev/training-coach/issues/372)) ([959cff6](https://github.com/LDoyleDev/training-coach/commit/959cff684dfa3cb82917a89eb58a01bfc2a7624e))


### Bug Fixes

* **infra:** reader ends a read on an empty page token, at most 20 reads ([#370](https://github.com/LDoyleDev/training-coach/issues/370)) ([0754f74](https://github.com/LDoyleDev/training-coach/commit/0754f744363e5e6c1d23c456bb9c2d526d37556d))
* **infra:** skip rclone's HEAD by version id that R2 answers with 501 ([#369](https://github.com/LDoyleDev/training-coach/issues/369)) ([a140c96](https://github.com/LDoyleDev/training-coach/commit/a140c9680bb99938e95e9b772a84208ee0f42d2f))


### Documentation

* session log for the 1.3.0 wrap ([#373](https://github.com/LDoyleDev/training-coach/issues/373)) ([ccd24e9](https://github.com/LDoyleDev/training-coach/commit/ccd24e96ebe36027b106696b91b106e7a6636b3c))

## [1.2.0](https://github.com/LDoyleDev/training-coach/compare/v1.1.0...v1.2.0) (2026-10-26)


### Features

* **api:** home kit per person, and steps lock by kit (ADR-0071) ([#358](https://github.com/LDoyleDev/training-coach/issues/358)) ([7cc2baa](https://github.com/LDoyleDev/training-coach/commit/7cc2baaa32f735fb08e1dda0b1b8ec31733ef330))
* **api:** one way to take each measurement, and a tape estimate ([#349](https://github.com/LDoyleDev/training-coach/issues/349)) ([7959bc7](https://github.com/LDoyleDev/training-coach/commit/7959bc7a3434c1177444c1af92deef3e78a4b1d1))
* **domain:** concrete kit ladders, with step cues and band strengths ([#360](https://github.com/LDoyleDev/training-coach/issues/360)) ([360b74b](https://github.com/LDoyleDev/training-coach/commit/360b74b1addc1d3e4f6e2d35461cc7fb09853aac))
* **web:** cardio and Home totals count the last 7 days ([#364](https://github.com/LDoyleDev/training-coach/issues/364)) ([5c61179](https://github.com/LDoyleDev/training-coach/commit/5c61179f869ef82bad80fca0c7be87934be9df05))
* **web:** draw seven leg figures, calf raise to reverse Nordic ([#356](https://github.com/LDoyleDev/training-coach/issues/356)) ([bb682ba](https://github.com/LDoyleDev/training-coach/commit/bb682baaeefa9a11233b7b9d1c06f506d3dc4517))
* **web:** how to measure, 7-day weight and a body-fat trend ([#351](https://github.com/LDoyleDev/training-coach/issues/351)) ([654ec1c](https://github.com/LDoyleDev/training-coach/commit/654ec1c92175e1d213a684ef50e816c202c0d345))
* **web:** My equipment on Account, and locked steps on levels ([#359](https://github.com/LDoyleDev/training-coach/issues/359)) ([ca546e3](https://github.com/LDoyleDev/training-coach/commit/ca546e3dc7565be258b3d6ae00485269fda88037))


### Documentation

* session log for the 1.2.0 wrap ([#368](https://github.com/LDoyleDev/training-coach/issues/368)) ([8ef0077](https://github.com/LDoyleDev/training-coach/commit/8ef0077a81de67e2d96fb1f810368aef9116687f))

## [1.1.0](https://github.com/LDoyleDev/training-coach/compare/v1.0.0...v1.1.0) (2026-10-25)


### Features

* **domain:** Torso curls get a second set, biceps at 11 a week ([#353](https://github.com/LDoyleDev/training-coach/issues/353)) ([08965c6](https://github.com/LDoyleDev/training-coach/commit/08965c626bd08f318d587fb4fa32bed05188875f))
* **web:** a boxing-ring bell, everyone's default timer sound ([#347](https://github.com/LDoyleDev/training-coach/issues/347)) ([dee9b02](https://github.com/LDoyleDev/training-coach/commit/dee9b020c9bccc83564a6bd83f7e30d46f00d6fd))
* **web:** counter first on the set screen, rest sound, times at check ([#345](https://github.com/LDoyleDev/training-coach/issues/345)) ([eed9f9d](https://github.com/LDoyleDev/training-coach/commit/eed9f9d3355a96d02e435403b786461387356495))
* **web:** draw pull-up, chin-up, dip, row, pike and diamond figures ([#346](https://github.com/LDoyleDev/training-coach/issues/346)) ([f522c67](https://github.com/LDoyleDev/training-coach/commit/f522c6761304ac77e767f5330893a588bbaabccf))
* **web:** guided stretching with an overview and a bell at each change ([#348](https://github.com/LDoyleDev/training-coach/issues/348)) ([f9ab32a](https://github.com/LDoyleDev/training-coach/commit/f9ab32a76fbde6962fafaf405d3e4c365392730e))
* **web:** move up, not yet and any level by hand on the Plan page ([#350](https://github.com/LDoyleDev/training-coach/issues/350)) ([8b0ee73](https://github.com/LDoyleDev/training-coach/commit/8b0ee73429a8b9bb8af16746730e7dfb4fac6219))


### Bug Fixes

* **web:** stretching falls back to the bell when Settings can't load ([#354](https://github.com/LDoyleDev/training-coach/issues/354)) ([8909bcf](https://github.com/LDoyleDev/training-coach/commit/8909bcf2d756d4662a6a2df3166183a7dac32942))


### Documentation

* wrap 1.1.0: set screen, bell, stretching and levels ([#355](https://github.com/LDoyleDev/training-coach/issues/355)) ([713b8a3](https://github.com/LDoyleDev/training-coach/commit/713b8a30598dad05a7afecb094d3bfae36479855))

## [1.0.0](https://github.com/LDoyleDev/training-coach/compare/v0.38.1...v1.0.0) (2026-10-25)


### Features

* **domain:** band face pulls for rear delts, suitcase carries for traps ([#340](https://github.com/LDoyleDev/training-coach/issues/340)) ([346feec](https://github.com/LDoyleDev/training-coach/commit/346feec3ebfed19eb9e3b32fb7dcdd6a377521a9))
* **web:** show each ladder step as its own period on the trend chart ([#341](https://github.com/LDoyleDev/training-coach/issues/341)) ([d06cac2](https://github.com/LDoyleDev/training-coach/commit/d06cac2ae968c7159951076cc6aa2a17e544b68b))
* **web:** show the muscles an exercise works on the set screen ([#343](https://github.com/LDoyleDev/training-coach/issues/343)) ([5bf9f43](https://github.com/LDoyleDev/training-coach/commit/5bf9f432961b259ee4943c5ddcbe5ac6e22dd661))


### Bug Fixes

* **domain:** a pair starts so no exercise or main muscle comes twice running ([#344](https://github.com/LDoyleDev/training-coach/issues/344)) ([9d03a99](https://github.com/LDoyleDev/training-coach/commit/9d03a99742e8baebb93a4da4aa48a4e8d06402b7))
* **infra:** the off-site job pings its own monitor, so a stopped job is noticed ([#338](https://github.com/LDoyleDev/training-coach/issues/338)) ([a76776b](https://github.com/LDoyleDev/training-coach/commit/a76776bf6f4965511bc037622df43970534bd735))


### Documentation

* ADRs for kit and places, load, and plans per person (accepted) ([#339](https://github.com/LDoyleDev/training-coach/issues/339)) ([109c6f1](https://github.com/LDoyleDev/training-coach/commit/109c6f178af1051ac438fea5f9a34d7a017dc978))
* wrap 1.0.0: the restore drill, phase 2 done, builder next steps ([#342](https://github.com/LDoyleDev/training-coach/issues/342)) ([8d3436c](https://github.com/LDoyleDev/training-coach/commit/8d3436cce9374a9b133818b33e7cb22f4133c6fb))
* wrap v0.38.1: reader diagnostics and dependency updates ([#335](https://github.com/LDoyleDev/training-coach/issues/335)) ([7aa3a4d](https://github.com/LDoyleDev/training-coach/commit/7aa3a4d6298ffd1bfcc51dd99831877a6ad12a1b))

## [0.38.1](https://github.com/LDoyleDev/training-coach/compare/v0.38.0...v0.38.1) (2026-10-24)


### Bug Fixes

* **infra:** reader keeps the screen awake, names the read that hits the quota, reads less ([#333](https://github.com/LDoyleDev/training-coach/issues/333)) ([4146302](https://github.com/LDoyleDev/training-coach/commit/4146302b1b46124e8319d2529d215e15dc345181))

## [0.38.0](https://github.com/LDoyleDev/training-coach/compare/v0.37.2...v0.38.0) (2026-10-24)


### Features

* **api:** the person picks zone 2 or moderate on AI cardio proposals ([#321](https://github.com/LDoyleDev/training-coach/issues/321)) ([d90487b](https://github.com/LDoyleDev/training-coach/commit/d90487ba541d2cff357fa4481908faedbfebbb21))
* **infra:** band reader spike: steps and heart rate from Health Connect ([#316](https://github.com/LDoyleDev/training-coach/issues/316)) ([be10175](https://github.com/LDoyleDev/training-coach/commit/be1017529a9ae96c46d95dc0c753398c22d161f1))


### Bug Fixes

* **api:** harden propose_log against lax types, odd ids and starts ([#320](https://github.com/LDoyleDev/training-coach/issues/320)) ([ef084e6](https://github.com/LDoyleDev/training-coach/commit/ef084e6a6d521d60432e7e444f183b5c00272caf))
* **api:** limit what one stolen band-import secret can do ([#324](https://github.com/LDoyleDev/training-coach/issues/324)) ([2e95a21](https://github.com/LDoyleDev/training-coach/commit/2e95a21ca6bd3e4f52a8e4d02d2e637d19948532))
* **infra:** close the 2026-10-24 security test's auto-deploy and tc-read gaps ([#323](https://github.com/LDoyleDev/training-coach/issues/323)) ([f7cf286](https://github.com/LDoyleDev/training-coach/commit/f7cf2869c37699b0644479557d6b6fb340d8baf8))
* **infra:** give tc-read's sql query its own memory and output budget ([#317](https://github.com/LDoyleDev/training-coach/issues/317)) ([98fc5d7](https://github.com/LDoyleDev/training-coach/commit/98fc5d74fc94fc2f5c7f2b8c896610ab4cdb9153))
* **infra:** harden auto-deploy against cut-offs, full disks, old images ([#318](https://github.com/LDoyleDev/training-coach/issues/318)) ([d70297c](https://github.com/LDoyleDev/training-coach/commit/d70297cd39abb535895835a06a4710795722ca0a))
* **infra:** reader and CI hardening from the security review ([#322](https://github.com/LDoyleDev/training-coach/issues/322)) ([ebf7a53](https://github.com/LDoyleDev/training-coach/commit/ebf7a537d21aabb34f2f84ae5c360864d0afcded))


### Documentation

* ADR-0070, our own Android reader, and its plan after review ([#315](https://github.com/LDoyleDev/training-coach/issues/315)) ([6065312](https://github.com/LDoyleDev/training-coach/commit/60653129649b45f68733952af2ae6764ca159abd))
* wrap v0.38.0: the band reader and the security review ([#332](https://github.com/LDoyleDev/training-coach/issues/332)) ([9609857](https://github.com/LDoyleDev/training-coach/commit/9609857b35fd1028cd8e5d24854df70e7cdec0c0))

## [0.37.2](https://github.com/LDoyleDev/training-coach/compare/v0.37.1...v0.37.2) (2026-10-24)


### Bug Fixes

* **api:** keep a daily steps record on the day the clocks go back ([#313](https://github.com/LDoyleDev/training-coach/issues/313)) ([2b7e855](https://github.com/LDoyleDev/training-coach/commit/2b7e85522b28f3455f0aaa89bc7143a34185305f))


### Documentation

* plan our own Android reader for band data ([#312](https://github.com/LDoyleDev/training-coach/issues/312)) ([1313af7](https://github.com/LDoyleDev/training-coach/commit/1313af7e2841bf33bab997e89534456fbf031b13))
* wrap v0.37.1: the Pi build fix and the v0.37.0 rollback ([#310](https://github.com/LDoyleDev/training-coach/issues/310)) ([45ae827](https://github.com/LDoyleDev/training-coach/commit/45ae827c26656477863e24d5670738e29220b2da))
* wrap v0.37.2: eval findings, and HC Webhook 1.9.26+ before our reader ([#314](https://github.com/LDoyleDev/training-coach/issues/314)) ([7e3dbf1](https://github.com/LDoyleDev/training-coach/commit/7e3dbf1ac9754c6031c7b72d6892ce339181456a))

## [0.37.1](https://github.com/LDoyleDev/training-coach/compare/v0.37.0...v0.37.1) (2026-10-24)


### Bug Fixes

* **infra:** let the Pi's image build survive a slow download ([#308](https://github.com/LDoyleDev/training-coach/issues/308)) ([fe24f32](https://github.com/LDoyleDev/training-coach/commit/fe24f324cbb708c6267a034c4605dfd9939fe3c6))

## [0.37.0](https://github.com/LDoyleDev/training-coach/compare/v0.36.0...v0.37.0) (2026-10-24)


### Features

* **api:** a connected AI proposes a run's distance, heart rate and start ([#305](https://github.com/LDoyleDev/training-coach/issues/305)) ([9cacda9](https://github.com/LDoyleDev/training-coach/commit/9cacda9f0304621f8c2c27fba7047eb79e216c99))


### Documentation

* wrap 21-24 Oct (v0.34.0 to v0.37.0): session log and lessons ([#302](https://github.com/LDoyleDev/training-coach/issues/302)) ([3907af8](https://github.com/LDoyleDev/training-coach/commit/3907af8cc79f2be6e931745485f470cdf9e81c0d))

## [0.36.0](https://github.com/LDoyleDev/training-coach/compare/v0.35.0...v0.36.0) (2026-10-23)


### Features

* **web:** log how a run felt, plus distance, heart rate and start ([#295](https://github.com/LDoyleDev/training-coach/issues/295)) ([c8fce2e](https://github.com/LDoyleDev/training-coach/commit/c8fce2e022dbfae24650daed959c9c227786d273))
* **web:** put Plan in the nav and move Tests into a Body tab ([#299](https://github.com/LDoyleDev/training-coach/issues/299)) ([626870d](https://github.com/LDoyleDev/training-coach/commit/626870d2d86aa0f3c2a11587ba516fe54f0391eb))
* **web:** show each session's own body map on the Plan page ([#300](https://github.com/LDoyleDev/training-coach/issues/300)) ([4faaac4](https://github.com/LDoyleDev/training-coach/commit/4faaac4f0be2fe29513db69c69bf369aab4aa085))
* **web:** show what a day logged on Today, with ‹ › to earlier days ([#298](https://github.com/LDoyleDev/training-coach/issues/298)) ([06cb787](https://github.com/LDoyleDev/training-coach/commit/06cb78787aab2c784884328e72f8cdbe061a349d))
* **web:** tick an earlier day's habits from Today's day card ([#301](https://github.com/LDoyleDev/training-coach/issues/301)) ([3dceaa8](https://github.com/LDoyleDev/training-coach/commit/3dceaa8cccb154f1f5d83b116ddeee8205d51189))


### Documentation

* plan cardio prefill from a photo or screenshot ([#296](https://github.com/LDoyleDev/training-coach/issues/296)) ([592c9b7](https://github.com/LDoyleDev/training-coach/commit/592c9b7112b733b69d2fcb954335ba8257975fb2))

## [0.35.0](https://github.com/LDoyleDev/training-coach/compare/v0.34.0...v0.35.0) (2026-10-23)


### Features

* **api:** keep a cardio day's block open after its run (ADR-0066) ([#294](https://github.com/LDoyleDev/training-coach/issues/294)) ([e622c6c](https://github.com/LDoyleDev/training-coach/commit/e622c6ca7f23471d8ca024390f6d2c6cbd29aa97))
* **domain:** add a core and hips block on Recovery and Cardio + core ([#293](https://github.com/LDoyleDev/training-coach/issues/293)) ([a289877](https://github.com/LDoyleDev/training-coach/commit/a289877d91480120bca268d8ff067dd9d7b1d315))


### Documentation

* research a core and hips block for the muscles the plan misses ([#290](https://github.com/LDoyleDev/training-coach/issues/290)) ([239a2c2](https://github.com/LDoyleDev/training-coach/commit/239a2c2c82a8b0685f1e2231bde3e0eefbeb3aca))

## [0.34.0](https://github.com/LDoyleDev/training-coach/compare/v0.33.0...v0.34.0) (2026-10-23)


### Features

* **api:** rest by transition: a 15 s switch inside a pair, a rest after it ([#288](https://github.com/LDoyleDev/training-coach/issues/288)) ([05abf38](https://github.com/LDoyleDev/training-coach/commit/05abf38d8df5681674067f23e1df6004e614ef61))
* **band:** note refused syncs and read HC Webhook record ids ([#283](https://github.com/LDoyleDev/training-coach/issues/283)) ([96a531e](https://github.com/LDoyleDev/training-coach/commit/96a531e863a89c04237ab115d337499a839b069e))
* **domain:** exercise catalogue with weighted muscles, fractional sets ([#284](https://github.com/LDoyleDev/training-coach/issues/284)) ([fc52c9f](https://github.com/LDoyleDev/training-coach/commit/fc52c9f2c4c0356605bef7342537a25eb38dcce2))
* **domain:** put every main muscle on target with the coverage update ([#289](https://github.com/LDoyleDev/training-coach/issues/289)) ([78de1af](https://github.com/LDoyleDev/training-coach/commit/78de1af77dc032b769ebe68a12005df862f05f9f))
* **web:** read-only body map on the Plan tab, coloured by weekly sets ([#285](https://github.com/LDoyleDev/training-coach/issues/285)) ([c018439](https://github.com/LDoyleDev/training-coach/commit/c018439ba2fcaef5124b1a00fb894346efe52132))


### Documentation

* plan the program builder, equipment and home/gym versions ([#276](https://github.com/LDoyleDev/training-coach/issues/276)) ([260aa67](https://github.com/LDoyleDev/training-coach/commit/260aa6719ecbbd1c0e0bd9fd4dbbbcfce092a29c))
* time efficiency for the builder: rest inside pairs, fillers and kit ([#286](https://github.com/LDoyleDev/training-coach/issues/286)) ([69b4e02](https://github.com/LDoyleDev/training-coach/commit/69b4e0212192ba89144f20894dbe49c18f4cba2d))

## [0.33.0](https://github.com/LDoyleDev/training-coach/compare/v0.32.0...v0.33.0) (2026-10-21)


### Features

* **api:** define the mobility flow's eight movements and serve them ([#278](https://github.com/LDoyleDev/training-coach/issues/278)) ([6f08c6a](https://github.com/LDoyleDev/training-coach/commit/6f08c6a1cfa75bc99cf487336dc889b35a805428))
* **web:** choose the mobility flow's timer sound in Settings ([#281](https://github.com/LDoyleDev/training-coach/issues/281)) ([a21e220](https://github.com/LDoyleDev/training-coach/commit/a21e220b32db17873e755d876bf2890a9071ca7d))
* **web:** draw exercises as mannequins moving from start to end ([#279](https://github.com/LDoyleDev/training-coach/issues/279)) ([c2ea250](https://github.com/LDoyleDev/training-coach/commit/c2ea250c926ce6d8feb9e7a15a8c54782e2d1876))
* **web:** graph six weeks of each exercise on dates, with a scale ([#275](https://github.com/LDoyleDev/training-coach/issues/275)) ([30946ee](https://github.com/LDoyleDev/training-coach/commit/30946ee29a34260e250e295a28005e490354ad39))
* **web:** guide the mobility flow one movement at a time ([#280](https://github.com/LDoyleDev/training-coach/issues/280)) ([3a2fe64](https://github.com/LDoyleDev/training-coach/commit/3a2fe642f72b6d12a7292a00d12fa8b28fea09a8))

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
