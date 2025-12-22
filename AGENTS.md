# Assistant Rules for TDoc-Crawler (Agent Index)

---

description: Agent-facing documentation index
alwaysApply: true
---

This repository maintains separate documentation for humans and for coding agents:

- Human-facing CLI behavior and usage examples: [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
- Agent-facing implementation and workflow guidance: [docs/agents-md/](docs/agents-md/)

## Quick Start for Coding Agents

Read in this order:

1. Tools and workflow basics (100–130)
2. Project domain and architecture (200–400)
3. Engineering and testing rules (600–700)
4. Documentation maintenance (800–900)

Key code entry points:

- [src/tdoc_crawler/cli/app.py](src/tdoc_crawler/cli/app.py)
- [src/tdoc_crawler/crawlers/](src/tdoc_crawler/crawlers/)
- [src/tdoc_crawler/database/](src/tdoc_crawler/database/)
- [src/tdoc_crawler/models/](src/tdoc_crawler/models/)

## Agent Documentation Index

- [docs/agents-md/100_Tool_Usage.md](docs/agents-md/100_Tool_Usage.md)
- [docs/agents-md/110_Tool_beads.md](docs/agents-md/110_Tool_beads.md)
- [docs/agents-md/120_Tool_memorygraph.md](docs/agents-md/120_Tool_memorygraph.md)
- [docs/agents-md/130_Tool_sequential_thinking.md](docs/agents-md/130_Tool_sequential_thinking.md)

- [docs/agents-md/200_Project_Domain_3GPP_TDocs_Meetings.md](docs/agents-md/200_Project_Domain_3GPP_TDocs_Meetings.md)
- [docs/agents-md/300_Repo_Architecture_and_Key_Files.md](docs/agents-md/300_Repo_Architecture_and_Key_Files.md)
- [docs/agents-md/320_Database_Schema_and_Invariants.md](docs/agents-md/320_Database_Schema_and_Invariants.md)
- [docs/agents-md/400_Crawling_and_Portal_Patterns.md](docs/agents-md/400_Crawling_and_Portal_Patterns.md)

- [docs/agents-md/600_Engineering_Standards.md](docs/agents-md/600_Engineering_Standards.md)
- [docs/agents-md/700_Testing_and_Mocking_Patterns.md](docs/agents-md/700_Testing_and_Mocking_Patterns.md)

- [docs/agents-md/800_Documentation.md](docs/agents-md/800_Documentation.md)
- [docs/agents-md/900_Updating_AGENTS.md](docs/agents-md/900_Updating_AGENTS.md)

## Non-negotiables

- Do not commit or push unless explicitly requested.
- Do not commit `.env` files.
- Keep human CLI usage/examples in [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md); keep agent rules/patterns in [docs/agents-md/](docs/agents-md/).
- Do not denormalize working-group fields back into `tdocs`; derive via joins (see [docs/agents-md/320_Database_Schema_and_Invariants.md](docs/agents-md/320_Database_Schema_and_Invariants.md)).

## Reviews of AGENTS.md

After several implementation steps, the present file (`AGENTS.md`) might need an update. When explicitly asked, use/update the file  `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md` for that purpose. The review/update will be triggered with a prompt similar to this one:

```markdown
Please review the current code basis and think thorougly about possible changes/updates/modifications/refactoring/restructuring of the coding instruction file AGENTS.md, which would help coding assistants to (re-)generate the code basis as close as possible.
Document your review findings in the file `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`, including specific proposed changes with explanations. Avoid copying too many specific source code samples/examples into `docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`. Sort and prioritize your findings them based on impact and effort. If your review does not find any necessary changes, simply state that the current AGENTS.md is adequate and requires no modifications.


Do not update AGENTS.md directly, only document your review findings in the specified file as stated above.
```

The actual update of AGENTS.md will be done only after explicit user confirmation and after a prompt similar to this one:

```markdown
Based on the review findings in the file #file:REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md (`docs/REVIEW_AND_IMPROVEMENTS_AGENTS_MD.md`), please update the coding instruction file AGENTS.md. Make sure to incorporate all relevant suggestions in the prioritized order specified by the review document, ensuring that the updated `AGENTS.md` reflects the best practices and guidelines for coding assistants to (re-)generate the code basis as close as possible.

Avoid copying citing/copying too many specific source code samples/examples into `AGENTS.MD`. You might move the current section regarding "Reviews of AGENTS.md" to a different place (should preferably remain at the very end of the document), but keep its content unchanged. After integration of the review findings, apply a final markdown lint cleanup.
```
