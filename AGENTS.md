# Repository Working Guidelines

These rules apply to all work in this repository.

## Think before coding

- State assumptions and unresolved uncertainty before implementation.
- Do not present an unverified claim as fact; use `NOT VERIFIED` when needed.
- Prefer the simplest solution that satisfies the stated requirement.
- Define a concrete verification result before changing code.

## Keep changes surgical

- Touch only files required by the current task.
- Do not combine refactoring, formatting, dependency upgrades, and behavior changes.
- Preserve existing naming, backend priority, command flags, UI behavior, and output paths unless the task explicitly changes them.
- Do not add antivirus bypasses, execute installer payloads, or modify source content being packaged.

## Verify the result

- Add or update a focused test for behavior changes when practical.
- Run focused tests first, then the full suite for cross-cutting changes.
- Do not report runtime behavior as passing unless it was actually exercised.
- Review `git diff --check` and the changed-file scope before commit.

## Tooling commands

- Sync the locked environment with `uv sync`.
- Lint with `uv run ruff check .`.
- Test with `uv run pytest -q`.
- Run repository hooks with `uv run pre-commit run --all-files`.
- Never bypass a failed hook without documenting and resolving its cause.
