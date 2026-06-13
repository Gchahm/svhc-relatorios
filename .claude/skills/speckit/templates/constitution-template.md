# [PROJECT_NAME] Constitution
<!-- Example: Spec Constitution, TaskFlow Constitution, etc. -->

## Core Principles

### [PRINCIPLE_1_NAME]
<!-- Example: I. Library-First -->
[PRINCIPLE_1_DESCRIPTION]
<!-- Example: Every feature starts as a standalone library; Libraries must be self-contained, independently testable, documented; Clear purpose required - no organizational-only libraries -->

### [PRINCIPLE_2_NAME]
<!-- Example: II. CLI Interface -->
[PRINCIPLE_2_DESCRIPTION]
<!-- Example: Every library exposes functionality via CLI; Text in/out protocol: stdin/args → stdout, errors → stderr; Support JSON + human-readable formats -->

### [PRINCIPLE_3_NAME]
<!-- Example: III. Test-First (NON-NEGOTIABLE) -->
[PRINCIPLE_3_DESCRIPTION]
<!-- Example: TDD mandatory: Tests written → User approved → Tests fail → Then implement; Red-Green-Refactor cycle strictly enforced -->

### [PRINCIPLE_4_NAME]
<!-- Example: IV. Integration Testing -->
[PRINCIPLE_4_DESCRIPTION]
<!-- Example: Focus areas requiring integration tests: New library contract tests, Contract changes, Inter-service communication, Shared schemas -->

### [PRINCIPLE_5_NAME]
<!-- Example: V. Observability, VI. Versioning & Breaking Changes, VII. Simplicity -->
[PRINCIPLE_5_DESCRIPTION]
<!-- Example: Text I/O ensures debuggability; Structured logging required; Or: MAJOR.MINOR.BUILD format; Or: Start simple, YAGNI principles -->

## [SECTION_2_NAME]
<!-- Example: Additional Constraints, Security Requirements, Performance Standards, Technology Stack, etc. -->

[SECTION_2_CONTENT]
<!-- Example: Technology stack requirements, compliance standards, deployment policies, etc. -->

## Running & Verifying the App
<!--
REQUIRED, project-specific section. The repo-agnostic `speckit pr` phase (Step 4) defers here for
how to verify a change before opening a PR — it hardcodes no commands. Fill the four parts below with
concrete, copy-pasteable values derived from this repo (package.json scripts / Makefile /
pyproject.toml / README / CI config). If there are genuinely none (e.g. a pure library/docs repo),
say so explicitly so the pr phase can record `Verification: none — no runtime surface`.
-->

- **Start the app**: [RUN_COMMAND]
  <!-- Example: `npm run dev`; or `make run`; or `docker compose up`; or `./gradlew bootRun` -->
- **Exercise a change**: [EXERCISE_GUIDANCE]
  <!-- Example: drive the affected surface against local/seeded data (real-shaped, not synthetic),
       and watch the server/console output for errors -->
- **Quality gates (run before every PR)**: [QUALITY_GATES]
  <!-- Example: lint, format, typecheck, and the test suite — all must pass (e.g. `npm run lint`,
       `npm test`; or `make check`; or `ruff check . && pytest`) -->
- **Dedicated verification agent/skill** (optional): [VERIFICATION_AGENT]
  <!-- Example: name a project agent/skill that exercises the running app (e.g. a browser-driving
       UI checker), or "none" if the project verifies by hand -->

## [SECTION_3_NAME]
<!-- Example: Development Workflow, Review Process, Quality Gates, Branching & PR policy, etc. -->

[SECTION_3_CONTENT]
<!-- Example: Code review requirements, branch naming, deployment approval process, etc. -->

## Governance
<!-- Example: Constitution supersedes all other practices; Amendments require documentation, approval, migration plan -->

[GOVERNANCE_RULES]
<!-- Example: All PRs/reviews must verify compliance; Complexity must be justified; Use [GUIDANCE_FILE] (e.g. CLAUDE.md / AGENTS.md) for runtime development guidance -->

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
<!-- Example: Version: 2.1.1 | Ratified: 2025-06-13 | Last Amended: 2025-07-16 -->
