---
description: Suggest the next issue to work on
---
List open issues in the current milestone with `gh issue list --milestone "<current phase>"
--state open`, check which ones are unblocked (dependencies in their "Notes" are closed), and
recommend the next one in spec build order. Do not start it; tell me the number and why.
