---
description: Record an architecture decision
argument-hint: <short title>
---
Create a new ADR titled "$ARGUMENTS".

1. Find the next number in `docs/adr/` (4 digits).
2. Copy `docs/adr/template.md` to `docs/adr/NNNN-kebab-title.md` and fill it in: context,
   decision, options considered with trade-offs, consequences. Status: Proposed (I accept it
   when I merge the PR).
3. If it replaces an earlier ADR, set that one's status to "Superseded by ADR-NNNN" and link both.
4. Add it to the index table in `docs/adr/README.md`.
