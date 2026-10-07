# ADR-0023: The model fallback only suggests; the rule parser decides

- Status: Accepted
- Date: 2026-10-07
- Deciders: Liam

## Context

ADR-0008 allows a Groq-hosted model to parse logs the rule parser can't read ("did eight pull
ups and then twelve dips"). ADR-0007 says model output is untrusted data. Voice transcripts
make this the first place where text from outside meets a language model.

## Decision

- The model is asked only when the rule parser reports problems and a Groq key is set.
- It gets no tools. It must answer in a strict JSON schema (`openai/gpt-oss-20b`, temperature
  0) whose exercise names are an enum of the plan's names and whose units are "", "s" or
  "min"; the client re-checks names and rejects negative values in case a provider ignores the
  schema. The log sits between `<log>` tags as data; any spelling of the tag in the text (case,
  spacing, Unicode look-alikes) is stripped first.
- Its answer is never used as data. It is turned back into plain `exercise n n n` lines and
  read by the same bounded rule parser; the reading is used only if that parse has no
  problems at all, and the reply says the model helped ("check every number"). If it read
  fewer parts than the message had, the reply says so.
- Otherwise, including any Groq failure, the user sees the rule parser's own problems.
- Nothing is saved without Save (ADR-0007). Model output is never logged.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Model rewrites, rules re-parse (chosen) | One validator for all input; bounds, units and names enforced the same way; worst case is a wrong suggestion the user sees | Needs a model with strict schema support |
| Use the model's JSON directly | Simpler | A second validation path to keep in step; easier to slip unbounded or invented values through |
| Rules only | No external model | "eight pull ups" and loose speech can't be logged by voice |
| Model first, rules as a check | Model handles everything | Costs a call per log; injection surface on every message |

## Consequences

- Changing the bounds or name matching in `domain/parser.py` changes the fallback too.
- The parse model is a setting (`TC_GROQ_PARSE_MODEL`); a replacement must support strict
  JSON-schema output.
- The prompt is versioned in `backend/src/training_coach/prompts/log_rewrite.md`.
