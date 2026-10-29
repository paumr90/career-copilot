# Semantic validation and regression diagnostics

The software suite and live semantic diagnostics answer different questions. On 29 October 2026, 224 software tests passed locally. The opt-in live run matched 9 of 10 synthetic reference labels using gpt-5.6-terra, semantic policy v0.2 and provider adapter v0.4. These are single-run diagnostics, not independent expert accuracy estimates.

## Reference review

Codex reviewed the changed diagnostic labels against the evidence actually supplied to the model. This is a technical review, not user approval or independent expert adjudication. Private profile facts and job assessment reports are excluded from this repository.

- Coordinating teams and an external partner supports a concrete portion of a teams-and-vendors requirement. Without an established vendor relationship, PARTIAL_MATCH is a defensible conservative reference.
- Managing projects can support a concrete leadership subset; a claim of strong leadership needs relevant activities or outcomes. Do not require literal reuse of the word leadership when activities clearly demonstrate it.
- Generic consulting or planning does not by itself demonstrate resolving problems. Concrete diagnosis and resolution activities can fully satisfy a problem-resolution requirement.
- Exploring agents or using language models does not demonstrate agent architecture development, model training or research publication. UNKNOWN reflects missing evidence, not confirmed inability.

No further policy relaxation was made to force agreement with these judgments.

## Synthetic cases

`tests/fixtures/semantic_cases.json` contains ten authored reference cases. They cover clear coordination evidence, partial vendor evidence, ambiguous partners, model use versus model development, project planning versus research, budgets/schedules as a concrete subset, explicit language alternatives, concrete incident resolution, concrete leadership and missing negotiation evidence.

The expected labels are never sent to the provider. Evidence is supplied directly so this diagnostic isolates assessment; it does not test retrieval or extraction. Provider proposals still pass the ordinary evidence-reference/status validator. Disagreements and provider failures are retained and cause a nonzero exit. Offline harness tests verify detection of both overstatement and excessive caution, as well as rejection of invalid keys and unprovided citations. They do not establish model accuracy.

```bash
python -m app.modules.fit.regression --live --output work/semantic-results.local.json
```

API credentials and model configuration come from local settings. This command incurs API usage and never creates a job opportunity or reads the personal profile. It saves each completed case before continuing.

## Open discrepancy

The `partner_ambiguous` reference is PARTIAL_MATCH. The recorded live run returned MATCH, treating an external technical partner as sufficient evidence for a vendor requirement even though the commercial relationship was unspecified. The reference was not changed to make the run pass. This remains an open boundary for review and repeated independent examples; the PR is a draft.

The other nine cases matched their reference labels, including concrete positive examples of leadership and incident resolution. One run cannot distinguish stable behavior from model variability. Do not generalize a 9/10 result to production accuracy.

## Extraction recovery and report interpretation

The extraction CLI checkpoints each parsed proposal and its available token telemetry before retrying validation failures once. It keeps both attempts, stops after a second invalid proposal and logs provider errors without inventing unavailable usage. SDK transport retries remain separately configured.

Reports lead with `assessment_summary`, including critical unknowns and evidence coverage. A high score calculated only over known requirements must not be presented as overall fit when coverage is low. The scoring formula has not been changed to turn missing evidence into a confirmed gap. No product interface or automatic application submission is included.
