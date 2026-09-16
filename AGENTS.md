# AGENTS — Instructions for Codex / Claude Code

## Mission
Implement FlyBrain Agent incrementally according to PRD.md, SDD.md, DATA.md, NEUROSCIENCE.md and TASKS.md.

## Mandatory Workflow
For every phase:
1. Read relevant project docs.
2. Inspect existing code before editing.
3. State a short implementation plan.
4. Implement only the current phase.
5. Add/update tests.
6. Run unit tests.
7. Run smoke test.
8. Fix failures.
9. Update PROGRESS.md.
10. Stop and report results.

Do NOT automatically start the next phase.

## Hard Rules
- Never fabricate biological neuron IDs, types, edges, synapse counts, regions, or dataset facts.
- Never present synthetic fixture data as biological data.
- Never silently substitute a different connectome.
- Never hard-code unknown production dataset schema before inspecting current official documentation/data.
- Never commit raw large datasets.
- Never implement P8/P9 before MVP P0-P6 is stable.
- Never claim simulated activity is measured biological activity.
- Prefer small, testable modules over monolithic files.
- Avoid unnecessary dependencies.
- No secrets/API keys in repository.
- Keep deterministic seeds for tests.
- Preserve provenance end-to-end.

## Definition of Done for a Phase
A phase is done only when:
- acceptance criteria pass
- tests pass
- smoke test passes
- docs/config updated
- PROGRESS.md updated
- no known blocking error is hidden

## Coding Style
Python:
- type hints
- pathlib
- dataclasses/Pydantic where appropriate
- clear pure functions for core transformations

TypeScript:
- strict mode
- typed API models
- no `any` without documented reason

## Git
Recommend one commit per completed phase:
`feat(p1): add normalized connectome ingestion`

Do not commit automatically unless the human explicitly requests it.

## Stop Conditions
Stop and ask/report when:
- official dataset access cannot be determined
- license/redistribution terms are unclear
- required annotation does not exist
- a requested biological mapping would require guessing
- tests reveal architectural mismatch
