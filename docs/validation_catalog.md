# Validation catalog

## Source status

The expected files `docs/reference/validation_catalog_001_100.md` and `docs/reference/validation_catalog_101_200.md` were not present in the repository or supplied attachments during this implementation. The prompt describes twenty broad category groups but does not provide the 200 individual check names, descriptions, or per-check category boundaries.

To preserve the original check intent, DataTrace currently imports zero catalog definitions. The API returns `source_status: SOURCE_MISSING`, `total: 0`, and an explanatory message. These values mean no definitions are loaded; they do not mean the requested 200 checks were assessed and found unavailable or not implemented.

## Import contract

The `validation_definitions` table is ready to retain the original ID, catalog number, name, description, category, severity, applicability/configuration requirements, implementation status/version, test status, limitations, enabled state, file types, applicability support, and source. No catalog row is seeded from the brief alone.

The catalog screen supports exact ID, partial name, full text, category, severity, implementation status, enabled state, applicability, and supported file type filters. Filter options and status counts are derived from imported database rows. Selecting a definition opens its supplied description and recorded requirements; the UI does not invent separate “what it detects” or “why it matters” text when the source does not provide those fields.

Once the two reference documents are supplied, each original title, description, category, and intent must be transcribed and reviewed before implementation status is assigned. A catalog definition is not evidence that its validator ran.
