# RxNorm Current Prescribable Content (runtime data)

This directory holds the **minimal RxNorm data the rx-ray app needs at runtime**,
committed to the repo so a fresh clone runs without the bulk local data tree.

Each subfolder is one dated RxNorm release. The app always loads the **latest**
subfolder (folders are named `YYYYMMDD`, so the lexicographically largest name is
the newest release). To update, drop a new `YYYYMMDD/` folder here with the two
parquet files below — no code change needed.

## Contents per release folder

- `rxnconso.parquet` — RxNorm concepts (RXCUIs, concept types, names).
- `rxnrel.parquet` — RxNorm relationships between concepts.

These are the only two tables the runtime resolver (`RxNormParquetStore`) reads.
`RXNSAT` and the raw OpenFDA dumps are **not** required at runtime and stay
gitignored.

## Provenance

- **Source:** RxNorm Current Prescribable Content
  (<https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html>).
- **Release:** `20260406` = the 04/06/2026 (April 6, 2026) Current Prescribable
  Content release, derived from the April 6, 2026 RxNorm Full Release.
- **Why this subset:** it is license-free (no UMLS license required, so it can
  ship in a public repo) and is built from the `RXNORM` + FDA Structured Product
  Label (`MTHSPL`) sources — the same FDA label data rx-ray reads from OpenFDA,
  so the terminology and the label evidence line up.
- **How it was produced:** the three `.RRF` tables from
  `RxNorm_full_prescribe_04062026` were loaded into a local MySQL RxNorm
  database; `rxnconso` and `rxnrel` were exported to parquet.
