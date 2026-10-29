# Local review and evaluation workflow

The CLI is the first usable interface to the backend. It reads private JSON files;
use filenames ending in `.local.json` so they are excluded from Git.

1. Prepare a `JobDescriptionInput` JSON containing the original job text and the
   extracted requirements. Existing deterministic/OpenAI extraction services produce
   this model.
2. Export a review request:

   ```powershell
   python -m app.cli review-template --input work/job.local.json --output work/review.local.json
   ```

3. Check every requirement against its source excerpt. Fill `reviewer` and
   `reviewed_keys` (each key exactly once). Add any corrections to `amendments`.
   Each amendment needs a reason and can change priority, category or blocking.
   The original source text stays unchanged; descriptions and evidence excerpts can be corrected with a reason and source grounding.

   ```json
   {
     "requirement_key": "technical_education",
     "priority": "MUST_HAVE",
     "category": "EDUCATION",
     "blocking": false,
     "reason": "The original description explicitly requires technical education."
   }
   ```

4. Validate and freeze the review:

   ```powershell
   python -m app.cli review --input work/review.local.json --output work/approved.local.json
   ```

5. Evaluate it with the configured model and local profile:

   ```powershell
   python -m app.cli evaluate --review work/approved.local.json --output work/result.local.json
   ```

The default evaluation rolls back the test opportunity and database audit.
The JSON report includes review hash, final assessments, scoring and assessment
audit. Add `--save` to commit the opportunity and audit. Configure PostgreSQL,
`LLM_MODEL` and `LLM_API_KEY` locally in `.env`.

## Reading the report

Always read score together with coverage. UNKNOWN is excluded from the score
denominator; coverage is the proportion of total requirement weight with a known
assessment. Reports mark results as provisional below 80% coverage or whenever
requirements remain unknown. A provisional report cannot recommend APPLY;
the original scoring recommendation is retained separately for audit.

Each unresolved requirement includes its rationale and a next action. An UNKNOWN
may indicate missing profile information, inadequate retrieval or ambiguity;
it is not evidence of a professional gap.

## Evidence selection and response validation

Ranking expands curated multilingual concepts (e.g. preventa/prevenda/proposals).
It reserves primary evidence when positive supporting matches would otherwise
exclude it. This only selects evidence; it never establishes a match.
Employment and projects can directly substantiate skills as primary evidence.

Each provider proposal is checked immediately against both its exact request and
the deterministic assessment policy. OpenAI can correct one rejected proposal;
both attempts and telemetry are retained. A second invalid response raises an
error with the attempt history, and the CLI exports it without calculating fit.
HTTP retries remain governed by the configured SDK retry limit.

UNKNOWN citations are removed only after checking that their IDs were supplied;
discarded IDs remain in telemetry. The semantic status is never upgraded.

## Tests

```powershell
pytest
pytest tests/unit
```

Database tests automatically create a random PostgreSQL schema, apply every
migration, load the synthetic fixture in `tests/fixtures/`, and drop that schema
on completion. They do not import the local Career Master or inspect the public
schema. The account needs CREATE SCHEMA permission. Set `TEST_DATABASE_URL` to use
a dedicated test database. Unit-only runs do not connect to PostgreSQL.

The synthetic profile includes no personal career data. Its counts are explicit
fixture contracts. Changing a personal profile cannot change these tests.


## Calibrated extraction and compatibility

The CLI can now perform a fresh governed extraction:

```powershell
python -m app.cli extract --input work/raw-job.local.json --output work/job.local.json
```

The input is a `RawJobDescriptionInput` object (`company`, `role_title`,
`raw_text`, optional `location` and `source_url`). A companion audit JSON
contains the original proposal, model telemetry, extraction rule version and a
literal source-bullet inventory. Unrepresented bullets are review prompts;
their absence does not prove semantic completeness.

Review amendments may correct `description` or `evidence_text` with an explicit
reason. The original snapshot remains unchanged and the revised evidence must
still be a contiguous verbatim source excerpt.

Reports now score professional requirements separately from location, work mode,
vehicle ownership and compensation. `fit` and the headline score describe the
professional subset; `combined_fit` preserves the earlier combined calculation.
`conditions` lists practical eligibility and negotiation points independently.
A pending condition prevents an automatic APPLY recommendation.

Factual work-profile fields include `current_city`, optional `current_province`,
`owns_vehicle`, and `onsite_days_acceptance` (days, status, condition). Import
only confirmed values with provenance. A preferred location cannot prove actual
residence; no city/province membership or currency conversion is inferred.
The semantic evidence projector exports only category-relevant fields.

The compatibility guards participate in immediate validation and its one bounded
repair. All new rules remain conservative where scope, period or actual offer
conditions are not established.


## Bounded extraction recovery and summary

Each extraction audit now includes an `attempts` array with parsed proposals, available provider telemetry and validation errors. The CLI checkpoints a failed validation before requesting one correction grounded in the original source. A second invalid proposal stops extraction; provider failures are also logged. No invalid job is emitted as successful output.

The report and terminal output lead with `assessment_summary`: coverage, critical unknowns and an insufficient-evidence status where applicable. Read this before the conditional score. See [semantic validation](semantic-validation.md) for the optional live synthetic regression command and its known disagreement.
