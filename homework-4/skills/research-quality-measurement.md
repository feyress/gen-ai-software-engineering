---
name: research-quality-measurement
description: Use when verifying a bug researcher's findings to assign an objective, repeatable quality rating to a codebase-research document.
---

# Research Quality Measurement

This skill defines how the **Bug Research Verifier** rates the quality of a
`codebase-research.md` document. It exists so that "research quality" is an
objective, repeatable label — not a gut feeling.

## What you measure

For every claim in the research document, check three things against the actual
source files:

1. **Reference accuracy** — does the cited `file:line` point at the code described?
   A line number off by a small amount (the snippet is found nearby) is a *minor*
   discrepancy; a wrong file or a snippet that does not exist anywhere is *major*.
2. **Snippet fidelity** — does the quoted code match the source character-for-character
   (ignoring leading/trailing whitespace)?
3. **Claim correctness** — is the described defect actually present and correctly
   diagnosed?

Count the claims and compute:

- `verified_refs` = claims whose snippet is found in the cited file.
- `exact_line_refs` = claims whose `file:line` is exactly correct.
- `minor_discrepancies` = snippet found in the right file but wrong line number.
- `major_discrepancies` = wrong file, fabricated snippet, or incorrect diagnosis.

## Quality levels

Assign exactly one level using the worst rule that applies (a single major
discrepancy caps you at **Adequate**; two or more cap you at **Poor**):

| Level | Criteria |
|-------|----------|
| **Excellent** | All snippets verified, all line numbers exact, all diagnoses correct, 0 discrepancies. |
| **Good** | All snippets verified and all diagnoses correct, but ≤2 *minor* (line-number) discrepancies and 0 major. |
| **Adequate** | All snippets locate in the right file; at most 1 major discrepancy; diagnoses broadly correct. |
| **Poor** | ≥2 major discrepancies, or a snippet that cannot be found, or a wrong diagnosis. |
| **Unreliable** | Most references do not resolve, or the document is internally inconsistent / unusable for planning. |

## Required output sections

When writing `verified-research.md`, the verifier MUST include these sections, in order:

1. **Verification Summary** — overall PASS/FAIL and the **Research Quality** level from
   the table above, plus the counts (`verified_refs`, `exact_line_refs`,
   `minor_discrepancies`, `major_discrepancies`).
2. **Verified Claims** — per claim: the claim id, the cited reference, the actual
   location found, and ✅/⚠️/❌.
3. **Discrepancies Found** — each discrepancy with claimed vs. actual and its severity
   (minor/major). Write "None" if there are none.
4. **Research Quality Assessment** — the chosen level and a one-paragraph justification
   that names the rule from the table that applied.
5. **References** — the files inspected.

## Decision rule for the downstream planner

- **Excellent / Good** → the plan may proceed as-is.
- **Adequate** → proceed, but the planner should re-confirm the flagged references.
- **Poor / Unreliable** → do not plan from this research; send it back for redo.
