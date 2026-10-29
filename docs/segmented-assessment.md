# Classify before assessment

Extraction policy v0.3 and extraction adapter v0.5 classify every new item as CONTEXT, ROLE_CAPABILITY, ESSENTIAL, DESIRABLE, UNCLASSIFIED or PRACTICAL_CONDITION. Each item has a source-based classification_reason. Its domain category (language, technology, education, etc.) is a separate dimension.

Related duties are grouped by coherent capability families, retaining all supporting literal fragments in source_excerpts. evidence_text remains one contiguous literal source excerpt. Every additional excerpt is independently source-validated. Essential qualifications, numerical thresholds and independent qualifications must not be collapsed into a generic capability. No hard item-count cap silently removes content. The current editor can amend the proposed groups and classification; interactive merging/splitting into new groups is not yet supported.

New extraction requires explicit classification. Historical imported requirements with null classification remain readable through a conservative category/priority fallback, marked inferred in the report. Historical review hashes remain verifiable: newly optional default fields do not change old digests. Existing data is not automatically reclassified.

## Evaluation

Context is stored with the reviewed source but excluded from the assessment and scoring-service input. Grouped capabilities, selection qualifications and conditions are assessed with their separate literal excerpts supplied to the semantic provider (policy v0.3).

The report is segmented_v1 and contains selection_requirements (essential, desirable, unclassified), role_capabilities, role_context and practical_conditions. It presents no aggregate score. Each selection block has its own item counts and evidence coverage; empty blocks have null coverage rather than a fictitious zero or perfect result.

- A confirmed GAP in an explicit professional essential leads to NO_APPLY.
- Unknown or partial essentials, unresolved classification, missing established essentials or pending practical conditions lead to REVIEW.
- Otherwise the report can indicate APPLY as a suggestion for human consideration. Desirable unknowns and role capability unknowns do not lower essential coverage or compensate an essential gap.
- Practical mandatory eligibility remains visible in its own block; an unresolved condition prevents automatic APPLY.

Legacy mixed calculations remain in database audits and legacy_fit_audit for provenance, not as a product-level fit rating. Top-level score is null. Source-inventory warnings can still make the result provisional; literal coverage is not a semantic-completeness claim.

## Interface and persistence

Review cards are compact and grouped by content type. Expand only to inspect classification reasons, description, source fragments or amendments. Changing classification updates the allowed priority; duties and context cannot be given essential weight. Human amendment notes are optional. Changing classification automatically aligns the technical priority and records the manual override without inventing a justification; the original AI explanation remains in the original snapshot. Saving preserves classification and the group excerpts along with the exact evaluated report.

Run alembic upgrade head before starting this version. Migration a107d9c84121 adds nullable classification fields without changing existing opportunities, sources or profile facts. Restart the single-worker server and reload the browser after upgrading. Export or copy the current unsaved offer before reloading: transient sessions are not migrated.

## Verification

Regression tests cover essential-gap precedence over arbitrarily many bonuses/capabilities, invariance of essential coverage when the offer has 0, 1 or 40 unknown duties, unknown versus gap, unclear classification, no declared essentials, multi-excerpt grounding and literal inventory, classification/priority conflicts, historical review hashes, and context excluded from actual provider calls while preserved on save.

The earlier reference offer was re-extracted into 20 items: one context, three capability families, ten desirable qualifications, two unclassified qualifications and four practical conditions. This is a diagnostic on a stored reference input, not necessarily the text most recently pasted in the browser. Classification and grouping remain AI proposals requiring source review; a single example does not measure accuracy.
