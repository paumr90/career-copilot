# Local review interface

Run PostgreSQL and apply migrations as described in the README. Use the existing local `.env` and canonical profile; the interface neither imports nor modifies profile facts.

```powershell
.\start-local.ps1
# Or, from the project directory:
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. Keep the terminal open. Use one server worker: previews are held in this process, not in a distributed store. Do not expose the unauthenticated service on a public address. Host validation and same-origin write checks are enabled.

1. Enter company, title and the full source text. Location and URL are optional. URLs are recorded as metadata, never fetched automatically.
2. Extract requirements. This makes a real model call and incurs tokens. Errors leave any available attempt audit downloadable.
3. Review each criterion and its literal source excerpt. Correct description, priority, category, blocker or excerpt as needed, with an optional note. Confirm every criterion and identify the reviewer. The current review model supports amendments to existing criteria; adding/removing criteria is not part of this prototype.
4. Evaluate the approved review. This makes model calls using the configured canonical profile. Coverage, critical unknowns and unresolved conditions appear before the conditional score. Expand a criterion to inspect its rationale, original excerpt and the projected evidence actually cited.
5. Save only if you want to keep the opportunity. This creates the opportunity, reviewed source, assessment/scoring audits and displayed report in one transaction. It does not call the model again. Repeated save requests for the same preview are idempotent for the lifetime of the server.

Evaluation itself rolls back its temporary opportunity and audits. The save operation copies the evaluated audit snapshots, preserving the preview opportunity identifier as provenance and recording the persisted identifier separately. The saved report represents the profile and rules at evaluation time; it is not silently recalculated later.

## Temporary sessions and errors

Sessions survive only while the server process runs. The browser does not store personal reports in localStorage. Page refresh loses the current session link; server restart clears transient sessions. Download JSON or save the opportunity before leaving. The full session download can contain private facts and should stay local (`*.local.json`). No list or reopening screen for saved opportunities is implemented yet.

At most 30 transient sessions are accepted per process, with two background workers. A busy session cannot be reviewed or saved; an edited review invalidates its earlier report. Failed model/validation operations do not persist an opportunity. Saving failures roll back and can be retried. If a provider fails before returning usage, no token count is invented.

The interface is in Catalan; source text, stored facts and existing model rationales retain their original languages. JavaScript inserts source and evidence text through textContent, not HTML. There are no third-party fonts, scripts or frontend dependencies.

## Verification

HTTP integration tests use synthetic data in an isolated PostgreSQL schema and injected providers. They cover rollback, exact-result saving without another model call, duplicate saves, rejected incomplete/ungrounded reviews, invalidation after amendments, error/audit downloads and origin/host checks. They do not establish live model accuracy.

The full software suite passed locally with 252 tests, together with Ruff checks and JavaScript syntax validation. Browser visual/interaction QA remains pending: the execution environment could not connect its browser to the locally bound server, and its browser policy rejects file-based previews. HTTP integration coverage is not a substitute for that visual check.


Extraction adapter v0.4 explicitly treats company, title and location fields as context rather than quotable source. If the model changes only whitespace in a quote, a unique token-identical source span can restore the original spacing; the untouched provider proposal and the exact correction remain in the audit. Ambiguous matches, word changes and punctuation changes are not repaired this way. A corrective model attempt may omit a criterion supported only by metadata; the literal source validator remains unchanged.

A live synthetic check with a location supplied only in metadata produced two source-grounded criteria and no location/work-mode criterion. This does not replay or guarantee success on any particular pasted offer. Literal-source failures are explained in Catalan, with technical details retained in session downloads.


This version uses [segmented assessment](segmented-assessment.md): compact review groups, separate essential/desirable qualifications, informational role capabilities and practical compatibility. There is no aggregate score. Run the new migration before restarting; copy or download unsaved input before reloading the browser.
