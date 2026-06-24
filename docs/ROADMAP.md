# rx-ray Roadmap

A grouped, scoped roadmap organized by theme. Each package has a goal, concrete scope, and a "done when" check.

## Guiding principle

rx-ray's most compelling and honest story is **not** "an app that answers drug questions." It is: **a system where a symbolic layer (RxNorm terminology + retrieved FDA label evidence + deterministic coverage checks) constrains and audits an LLM so it cannot overclaim.** Every theme below is ordered to strengthen that story. When in doubt, prioritize work that makes the neuro-symbolic boundary and the guardrails more visible, more measurable, and more trustworthy.

## How to read this

- **Effort**: `S` ≤ 1 day · `M` 2–4 days · `L` 1–2 weeks · `XL` multi-week / research.
- **Impact**: `High` / `Med` / `Low`.
- **Status**: `todo` · `in progress` · `done`.

---

## Recommended sequencing

**Phase 0 — Foundation must-haves (days):**
[A1](#a1--clone-and-run-bootstrap) clone-and-run · [A2](#a2--neuro-symbolic--safety-narrative-about-page) About narrative · [A3](#a3--readme-refresh) README · [A5](#a5--architecture-doc) architecture doc.
Optionally [A4](#a4--live-demo-deployment) live demo if hosting is straightforward. These determine first impressions.

**Phase 1 — Quality + speed foundation (1–2 weeks):**
[B1](#b1--rxnorm-resolver-indexing--performance)/[E1](#e1--resolver--neighborhood-performance) resolver perf · [B5](#b5--query-to-concept-matching--display-fidelity) query to concept matching & display fidelity · [B2](#b2--specific-concept-resolution-priority--ingredient-fallback) specific-concept priority + ingredient fallback · [D1](#d1--guardrails-v2) Guardrails V2 ·
[E2](#e2--test-fixtures-fast-suite--ci) fixtures + CI · [E3](#e3--lint-scope--legacy-module-triage) lint cleanup. Makes the system faster, more correct, and protected.

**Phase 2 — Research showcase (1–2 weeks):**
[D3](#d3--evaluation-harness--curated-question-set) evaluation harness · [D4](#d4--neural-vs-symbolic-vs-combined) neural-vs-symbolic-vs-combined. The most distinctive material; depends on Phase 1 being stable.

**Phase 3 — Deeper evidence + guardrails (multi-week):**
[C1](#c1--pair-level-interaction-evidence-view) pair-level interactions · [D2](#d2--guardrails-v3) Guardrails V3 · [D5](#d5--reasoning--execution-traces) traces · [C3](#c3--question-level-provenance-graph-maturation) provenance graph.

**Backlog / opportunistic:**
[B3](#b3--autocomplete--typeahead-for-drug-dossier) typeahead · [B4](#b4--openfda-text-fallback-when-rxnorm-resolution-fails) OpenFDA fallback · [C2](#c2--external-interaction-data-source) external interaction data (gated on licensing) · [C4](#c4--context-targeted-retrieval-tuning) context tuning · [E4](#e4--generate-ts-types-from-openapi-schema) OpenAPI types · [E5](#e5--frontend-performance-for-the-evidence-map) map perf · all of [Theme F](#theme-f--ux-polish--smaller-improvements).

---

## Quick reference

| ID | Package | Theme | Effort | Impact | Status | Depends on |
|----|---------|-------|--------|--------|--------|------------|
| [A1](#a1--clone-and-run-bootstrap) | Clone-and-run bootstrap | Foundation | M | High | ✅ done | — |
| [A2](#a2--neuro-symbolic--safety-narrative-about-page) | About narrative | Foundation | S–M | High | ✅ done | — |
| [A3](#a3--readme-refresh) | README refresh | Foundation | S | Med | ✅ done | A2 |
| [A4](#a4--live-demo-deployment) | Live demo | Foundation | M | High | todo | A1 |
| [A5](#a5--architecture-doc) | Architecture doc | Foundation | S | Med | todo | — |
| [B1](#b1--rxnorm-resolver-indexing--performance) | Resolver indexing/perf | Retrieval | M | Med | todo | — |
| [B2](#b2--specific-concept-resolution-priority--ingredient-fallback) | Specific-concept priority + ingredient fallback | Retrieval | L | High | ✅ done | B5 |
| [B3](#b3--autocomplete--typeahead-for-drug-dossier) | Autocomplete/typeahead | Retrieval | M | Med | todo | B1 |
| [B4](#b4--openfda-text-fallback-when-rxnorm-resolution-fails) | OpenFDA text fallback | Retrieval | M | Med | todo | — |
| [B5](#b5--query-to-concept-matching--display-fidelity) | Query→concept matching & display fidelity | Retrieval | M | High | ✅ done | — |
| [C1](#c1--pair-level-interaction-evidence-view) | Pair-level interactions | Evidence | M | Med | ✅ done | — |
| [C2](#c2--external-interaction-data-source) | External interaction data | Evidence | XL | High | todo | — |
| [C3](#c3--question-level-provenance-graph-maturation) | Provenance graph maturation | Evidence | L | High | todo | — |
| [C4](#c4--context-targeted-retrieval-tuning) | Context-targeted tuning | Evidence | M | Low–Med | todo | — |
| [D1](#d1--guardrails-v2) | Guardrails V2 | Safety | M | High | ✅ done | — |
| [D2](#d2--guardrails-v3) | Guardrails V3 | Safety | L | High | todo | D1 |
| [D2c](#d2c--fix-evidence-packet-truncation-starving-later-label-sections) | Fix evidence-packet truncation | Safety | S–M | High | in progress | D1, D2 |
| [D3](#d3--evaluation-harness--curated-question-set) | Evaluation harness | Safety | L | High | todo | — |
| [D4](#d4--neural-vs-symbolic-vs-combined) | Neural vs symbolic vs combined | Safety | L | High | todo | D3 |
| [D5](#d5--reasoning--execution-traces) | Reasoning/execution traces | Safety | M | Med | todo | — |
| [E1](#e1--resolver--neighborhood-performance) | Resolver/neighborhood perf | Engineering | M | Med | todo | (=B1) |
| [E2](#e2--test-fixtures-fast-suite--ci) | Fixtures + fast suite + CI | Engineering | M | Med | todo | — |
| [E3](#e3--lint-scope--legacy-module-triage) | Lint scope / legacy triage | Engineering | S | Med | todo | — |
| [E4](#e4--generate-ts-types-from-openapi-schema) | OpenAPI→TS types | Engineering | M | Med | todo | — |
| [E5](#e5--frontend-performance-for-the-evidence-map) | Evidence map perf | Engineering | M | Low–Med | todo | — |
| [F1–F5](#theme-f--ux-polish--smaller-improvements) | UX polish & small items | Polish | S–M | Low | todo | — |
| [F6](#theme-f--ux-polish--smaller-improvements) | Richer drug-label cards & medication overview | Polish | M | Low | ✅ done | — |

---

## Theme A — Foundation & Launch Readiness

The highest-leverage work per hour. Most items here are small but decisive: they determine whether someone who clones the repo or opens the app has a good first impression of what the system is and what it can do.

### ✅ A1 — Clone-and-run bootstrap

**Effort:** M · **Impact:** High · **Status:** done

**Goal:** A fresh clone can run the app end-to-end without the local 8 GB data tree.

**Why it matters:** The runtime needs `data/01_raw/rxnconso_raw.parquet` (~9 MB) and `rxnrel_raw.parquet` (~26 MB), both gitignored, with no bootstrap script. A fresh clone currently results in a non-working app. This is the single biggest usability gap.

**Scope:**
- Decide between (a) committing the two runtime parquets (~35 MB total) or (b) a committed *sampled* subset (top-N RXCUIs) plus a `make data` / script to rebuild.
- Provide a one-command bootstrap (`make setup` or `scripts/bootstrap.py`) that prepares `.env`, installs deps, and verifies the data is present.
- Document the minimal runtime data (2 parquets) vs the bulk raw sources in the README.
- Ensure the OpenFDA cache has a small seeded set so demo mode and a couple of common drugs work fully offline.

**Done when:** `git clone` → documented bootstrap → working Ask + Dossier pages with no manual data wrangling.

---

### ✅ A2 — Neuro-symbolic + safety narrative (About page)

**Effort:** S–M · **Impact:** High · **Status:** done

**Goal:** The neuro-symbolic design and safety stance are clearly explained in the UI, without needing to read source.

**Why it matters:** The safety thinking is entirely in the code but invisible in the product. The current About page is ~37 lines.

**Scope:**
- A compact "How rx-ray works" panel: neural vs symbolic responsibilities (who does what), with the pipeline diagram from the README.
- A "How rx-ray avoids overclaiming" section: citation whitelist, deterministic coverage audit, careful label-text framing, no yes/no medical advice.
- Explicit scope + limitations (terminology-only RxNorm, incomplete label coverage for interactions) stated as deliberate design honesty, not as a disclaimer footnote.

**Done when:** About page clearly tells the neuro-symbolic and safety story.

> **Done.** The About page was rebuilt as collapsible sections (Welcome · What you can do here · How it works · Goal & impact · Tech stack)

---

### ✅ A3 — README refresh

**Effort:** S · **Impact:** Med · **Status:** done · **Depends on:** A2

**Goal:** README reflects the current architecture and reframes the headline around provenance + guardrails rather than "drug Q&A."

**Scope:**
- Update the feature list and repo layout for the current `components/dossier/*` structure.
- Lead with the neuro-symbolic + guardrail framing (mirror A2).
- Replace the "`next build` fails locally" caveat with a working build/run path (or a link to the live demo once A4 lands).

**Done when:** README headline and setup instructions match the real, runnable state of the project.

> **Done.** README now leads with the neuro-symbolic + guardrail framing, documents the pipeline, guardrail layer, data sources, and tech stack, and has a real `make setup` run path.

---

### A4 — Live demo deployment

**Effort:** M · **Impact:** High · **Status:** todo · **Depends on:** A1

**Goal:** A public URL (or a polished recorded walkthrough) so no local setup is required to see the project working.

**Scope:**
- Frontend on Vercel; backend on a small host (Fly/Render/Railway) or a serverless wrapper; wire `BACKEND_URL`.
- Decide how to ship the parquet data to the backend host (depends on A1).
- Demo mode already runs without a live LLM API — make that the safe default for the public demo, with optional live mode behind a key.
- Fallback: if hosting the data backend is heavy, ship a recorded 60–90s walkthrough.

**Done when:** A link in the README opens a working demo.

---

### A5 — Architecture doc

**Effort:** S · **Impact:** Med · **Status:** todo

**Goal:** A one-page design doc covering the neuro-symbolic boundary, data flow, and the guardrail/coverage layer, with the request pipeline diagram.

**Why it matters:** Makes the system legible without reading code; signals design clarity.

**Done when:** Any technical reader can read it and accurately describe the system.

---

## Theme B — Symbolic Retrieval Quality

The symbolic half of the system. Improving resolution quality and speed directly improves answer quality and responsiveness.

### B1 — RxNorm resolver indexing & performance

**Effort:** M · **Impact:** Med · **Status:** todo

**Goal:** Cut per-query resolution latency by replacing repeated full-DataFrame scans with prebuilt indexes.

**Why it matters:** `RxNormParquetStore.resolve()` runs up to ~8 full-column pandas scans per call; the n-gram scanner calls `resolve` for every 1–4-gram in the query, producing dozens of full scans per question. `get_neighborhood` re-masks the whole `rxnrel` table per hop at `depth=2, max_edges=400`. This is the main latency source.

**Scope:**
- Build exact / normalized / compact lookup dicts once at load; reserve scan-based matching for fallback only.
- Pre-index `rxnrel` edges by RXCUI (group once at load) so neighborhood expansion is a dict lookup, not a full-table boolean mask.
- Add a small benchmark (a handful of representative queries) to track latency.

**Done when:** Median query-understanding latency drops materially; benchmark recorded.

**Note:** Overlaps with E1 — treat as one effort.

---

### ✅ B2 — Specific-concept resolution priority + ingredient fallback

**Effort:** L · **Impact:** High · **Status:** done · **Depends on:** B5

**Goal:** Prefer the exact/specific RxNorm concept; when it has no label evidence of its own, fall back to its active ingredient(s) *explicitly*, with a deterministic caveat, rather than silently broadening.

**Why it matters:** Searching "tretinoin 0.5 MG/ML" or "hydrochlorothiazide oral tablet" can currently broaden to the ingredient, after which the answer cites broader evidence than the user asked about — a guardrail gap. The answer synthesizer sees the original query and extracted medication state, but if resolution broadens a specific query to an ingredient, the answer may know the user asked for a specific product/concentration while still citing broader evidence. The honest fix is not to broaden silently but to keep the specific concept as the anchor and label any ingredient fallback as a deliberate, visible broadening.

**Scope:**
- When a specific concept is resolvable, prefer it and keep it as the matched/primary node.
- Ingredient fallback for labels: when the specific concept returns no OpenFDA labels, walk `has_ingredient` to its ingredient(s), retrieve *their* labels tagged `ingredient_fallback`, name that evidence after the ingredient, and attach a deterministic caveat ("No product-specific labels for <concept>; showing labels for its active ingredient <ingredient>, which may describe other formulations").
- Multi-ingredient / combination products: retrieve a labelled bundle per ingredient, tag each, and caveat the combination — never merge ingredient evidence silently.
- Carry the specificity/broadening signal through to the evidence packet so the synthesizer and coverage audit can flag when retrieval broadened the query.
- Surface the primary's active ingredient(s) as their own Drug Network centers, so a specific product (e.g. a cream) shows an ingredient-focused neighborhood and a highlighted ingredient bubble, mirroring the Evidence Map — not just an incidental connected node.
- Search drug interactions at the ingredient level (the resolved ingredient name) rather than the full product string, which is both the wrong granularity and a malformed OpenFDA query term.
- Test set: tretinoin 0.5 MG/ML, hydrochlorothiazide oral tablet, fluoxetine oral solution, benzoyl peroxide topical gel, plus a no-product-label concept and a combination product.

**Done when:** Specific searches keep the primary node + OpenFDA lookup tied to the intended specificity; any ingredient fallback is explicit, ingredient-named, caveated, and surfaced as a limitation (single- and multi-ingredient); the active ingredient is a first-class network center; and interaction lookups are ingredient-level.

> **Done.** Specific concepts are preferred and kept as the primary node; when one has no labels of its own, retrieval broadens to its active ingredient(s) via an RxNorm ingredient walk, tagged `ingredient_fallback`, with a deterministic caveat surfaced in coverage, synthesis, and the Drug Labels panel (per-ingredient sections for combination products). The primary's active ingredient(s) are added as Drug Network centers, and drug-interaction lookups now search by ingredient name rather than the full product string.

---

### B3 — Autocomplete / typeahead for Drug Dossier

**Effort:** M · **Impact:** Med · **Status:** todo · **Depends on:** B1

**Goal:** RxNorm typeahead on the direct drug search, optionally showing matched concept type.

**Why it matters:** Makes the symbolic resolver visible and interactive; a meaningful trust and usability improvement.

**Scope:**
- Lightweight suggest endpoint backed by the resolver (depends on B1 for speed).
- Frontend typeahead with debounce; show concept type (e.g. IN / SCD) in suggestions.

**Done when:** Typing in the Dossier search surfaces ranked RxNorm suggestions.

---

### B4 — OpenFDA text fallback when RxNorm resolution fails

**Effort:** M · **Impact:** Med · **Status:** todo

**Goal:** When RxNorm can't resolve a mention, still show public label evidence via an OpenFDA lookup by extracted medication text.

**Why it matters:** A query can currently dead-end with no Drug Network *and* no labels.

**Scope:**
- Fallback OpenFDA search keyed on the extracted text when no RXCUI resolves.
- Clearly tag this evidence as text-matched (no terminology grounding) so it isn't mistaken for resolved-concept evidence.

**Done when:** Unresolved-but-real drug names can still surface labels, clearly labeled.

---

### ✅ B5 — Query-to-concept matching & display fidelity

**Effort:** M · **Impact:** High · **Status:** done

**Goal:** Resolved concepts display their preferred RxNorm term with human-readable types, dosage-form / SPL-synonym false positives stop becoming graph nodes, and the deterministic extractor stops mis-assigning allergens.

**Why it matters:** A real query — "Can I use a tretinoin cream if I have a CLINDAMYCIN allergy?" — exposed several resolution/display defects at once: a stray "CREAM" node (the bare word resolved to an SPL synonym of "milk fat, cow"), raw term-type codes ("Su"/"Dp") in tooltips and badges, concept names shown as arbitrary SPL synonyms instead of the clean RxNorm preferred term, and the allergen ("clindamycin") demoted to a generic mention while "tretinoin cream" was wrongly captured as the allergy. These undercut trust in the symbolic layer even when retrieval is otherwise correct. Note: in that query the retrieved labels were in fact the cream's (matched by RXCUI 198300) — the "TRETINOIN" on the source cards is the label's own generic name — so part of the fix is making that provenance legible rather than changing retrieval.

**Scope:**
- `resolve()` returns the winning RXCUI's *preferred* name + TTY for display (keeping match_type/score from the matched row), so e.g. RXCUI 198300 shows as "tretinoin 1 MG/ML Topical Cream" (SCD), not its SPL `DP` synonym.
- Scanner guards: a dosage-form stop set (cream, gel, ointment, lotion, solution, tablet, capsule, spray, patch, …) and rejection of scanned mentions whose preferred TTY isn't a real medication type (drop SU/DF/DFG/PT). Keeps the legitimate ingredient node, removes the junk one.
- Complete the frontend `rxNormTypeLabels` map (DP, SU, MTH_RXN_DP, PT, …) so no raw codes ever surface.
- Tighten deterministic allergy extraction so "a <other drug> … allergy" no longer swallows a preceding drug, and the real allergen resolves into allergy state.
- Label-provenance legibility: when labels are matched to a concept by RXCUI, say so on the matched-drug header / source cards so a correct RXCUI match does not read as a name mismatch.

**Done when:** The tretinoin-cream / clindamycin query (and similar) resolve to clean preferred names with human-readable types, with no dosage-form / SPL-synonym stray nodes, the allergen correctly classified, and label provenance legible — verified with a regression test.

> **Done.** `resolve()` now returns each concept's preferred RxNorm term + TTY; the query scanner drops dosage-form words and non-medication TTYs (no more stray "CREAM" node); the frontend TTY map covers SPL types; deterministic allergy extraction no longer swallows a preceding drug; and an RXCUI-match provenance note explains why label cards may read ingredient-generic. Also folded in a small UI-honesty fix: technical warnings/errors are no longer surfaced in the UI (kept in the API/logs).

---

## Theme C — Neuro-Symbolic Evidence & Interactions

Maturing how evidence is modeled, especially for multi-drug / interaction questions — currently the weakest part of the value prop and the most honestly-caveated.

### ✅ C1 — Pair-level interaction evidence view

**Effort:** M · **Impact:** Med · **Status:** done

**Goal:** Show "drug A + drug B" interaction evidence as a first-class pair, not buried inside one medication's tab.

**Why it matters:** Interaction-specific sources currently live inside a single medication tab, which is conceptually awkward for the exact questions users ask most.

**Scope:**
- A pair-level panel in Supporting Evidence and a corresponding Evidence Map treatment.
- Keep the careful framing: label text *mentions* the other drug ≠ a confirmed clinical interaction.

**Done when:** An interaction question renders a clear pair-level evidence view.

> **Done.** Replaced per-drug RxNorm graphs and per-drug "RxNorm terminology context" panels with a single unified Drug Network as the first Supporting Evidence tab. The network merges every resolved drug's neighborhood (all drugs at depth 2) with a fair per-center edge budget; shared RxNorm nodes (reachable from more than one drug) get a purple ring. The slider defaults to the fewest relationships that visually connect the drugs. Node-click offers "Open [drug] tab" for center drugs and "Search in Drug Dossier" for other nodes. The UI copy is explicit: shared nodes are RxNorm vocabulary overlap only, never clinical interaction evidence.

---

### C2 — External interaction data source

**Effort:** XL · **Impact:** High · **Status:** todo

**Goal:** Add a real interaction-focused data source; stop implying RxNorm graph distance is interaction evidence.

**Why it matters:** RxNorm is terminology-only and OpenFDA label text is incomplete for interaction discovery. This is the package that would make the "interaction" framing genuinely true.

**Scope:**
- Survey public interaction datasets; document licensing and coverage before integrating (this evaluation is itself a deliverable).
- Normalize into weak, clearly-labeled evidence edges in the question-level graph.
- Update coverage + synthesizer framing accordingly.

**Done when:** Interaction answers can cite a dedicated interaction source, with provenance and confidence clearly distinguished from label-text mentions.

**Risk:** Licensing. Keep an offline/abstention path if no suitable source is usable.

---

### C3 — Question-level provenance graph maturation

**Effort:** L · **Impact:** High · **Status:** todo

**Goal:** Evolve the Evidence Map into a single navigable provenance layer combining mentions, resolved concepts, retrieved labels, interaction-targeted text, terminology context, and (later) external interaction evidence.

**Why it matters:** Provenance/traceability is a core safety value and a natural home for every other evidence type. Pairs well with D5.

**Scope:**
- Unify node/edge kinds and their provenance tags.
- Make every answer claim traceable to a node/edge in the map.

**Done when:** The map is the canonical "where did this come from" view for an answer.

---

### C4 — Context-targeted retrieval tuning

**Effort:** M · **Impact:** Low–Med · **Status:** todo

**Goal:** Improve targeted OpenFDA lookups for conditions, allergies, and patient context.

**Scope:**
- Expand/tune target-field mappings against more real queries.
- Symptom synonyms (e.g. "swollen eyes" → eye irritation / swelling) before search.
- Configurable invalid-extraction/normalization dictionary; richer non-medication allergen list (kept conservative so medication allergies like aspirin or ibuprofen can still resolve as secondary evidence).
- Careful UI wording: label text mentions a context ≠ the app validating suitability.

**Done when:** Context-targeted hits are more accurate and clearly framed.

---

## Theme D — Safety, Guardrails & Evaluation

The differentiator. This turns "careful prompting" into a measurable, layered safety architecture.

### ✅ D1 — Guardrails V2

**Effort:** M · **Impact:** High · **Status:** done

**Goal:** Deterministic, intent-aware checks that the retrieved evidence actually addresses the question, plus a must-mention/must-caveat checklist fed into synthesis.

**Scope:**
- Intent-specific coverage checks:
  - Pregnancy/lactation Q → pregnancy, lactation, or specific-populations evidence retrieved?
  - Interaction Q → evidence retrieved for all mentioned drugs, and interaction sections present?
  - Allergy Q → contraindications, hypersensitivity, ingredient, or warning evidence present?
  - Side-effect Q → adverse reactions or warnings present?
  - Indication Q → indications_and_usage present?
- Build a deterministic must-mention / must-caveat checklist *before* synthesis and pass it into the prompt.
- Add normalized label product context to the synthesis evidence packet as a
  separate, bounded `label_product_context` block: product/display-panel text,
  description, active/inactive ingredients, purpose, and dosage per label source.
  Prompt it as formulation/product context that may answer product-specific or
  how-to/dosage questions, but must not be treated as standalone safety,
  contraindication, or interaction evidence unless supported by the relevant
  label sections.
- Expand post-generation validation beyond citation presence: cited supplied evidence only; important extracted entities mentioned or caveated; deterministic limitations preserved; no yes/no medical-advice framing.

**Done when:** Each intent has a deterministic coverage check and a pre-synthesis caveat contract that post-generation validation enforces.

> **Done.** Each intent (`patient_context_check`, `allergy_context_check`, `interaction_check`, `side_effect_check`, `indication_check`, `label_context_check`) has a deterministic coverage check (`intent_evidence_status`) against the actual retrieved label sections, with matched evidence linked back into Supporting evidence in the UI. `build_answer_contract` turns coverage into a must-mention/must-caveat checklist built before synthesis and fed into the prompt, alongside a bounded, non-citable `label_product_context` block. `validate_and_enforce` runs post-generation: it deterministically appends any must-caveat the model dropped, flags yes/no medical-advice framing, and records unaddressed must-mention topics as validation findings — surfacing those findings in the UI is carried forward into D2, since it's specifically about critiquing how well the LLM used the evidence.

---

### D2 — Guardrails V3

**Effort:** L · **Impact:** High · **Status:** todo · **Depends on:** D1

**Goal:** Extract each generated claim, map it to supporting citations, and run an optional LLM critic that flags unsupported claims, missing caveats, or overconfident wording — regenerating once on important issues.

**Scope:**
- Claim extraction + claim-to-citation alignment.
- Optional LLM critic after deterministic checks.
- One feedback-driven regeneration when important issues are found.
- Confidence language: strong / partial / limited / no retrieved coverage.

**Done when:** Answers carry per-claim support status and a critic pass with bounded regeneration.

---

### D2c — Fix evidence-packet truncation starving later label sections

**Effort:** S–M · **Impact:** High · **Status:** in progress · **Depends on:** D1, D2

**Goal:** Fix a retrieval/packet-construction bug found while investigating D2b: `EvidenceAnswerSynthesizer.label_section_payloads()` truncates per drug to `MAX_LABEL_SECTIONS = 16` entries, walking sections in a fixed priority order (`boxed_warning`, `contraindications`, `warnings`, `drug_interactions`, ...) with no per-section sub-limit and no deduplication. For drugs with many OTC label-record variants, near-duplicate boilerplate in the earlier sections alone can exceed the cap before later sections — including `drug_interactions` — are ever reached, even though the deterministic coverage layer (which runs on the untruncated dossier data) already confirmed that evidence exists and told the LLM to address it via the contract. Confirmed live with *"Can I take ibuprofen for my migraine if I'm allergic to aspirin?"*: ibuprofen has 2 boxed_warning + 2 contraindications + 13 warnings (10 of which are near-identical "allergy alert" boilerplate from different manufacturer records) = 17 non-empty entries before `drug_interactions` (2 real entries) is reached, so zero `drug_interactions` text ever reaches the LLM, despite `interaction_check` being marked "addressed." Aspirin shows the same pattern (24 entries before `drug_interactions`, 6 real entries dropped).

**Scope:**
- Cap entries **per section**, not just per drug overall, so one bloated section (typically `warnings`) can't crowd out every later section in the priority order.
- Make the cap **contract-aware**: guarantee at least one representative entry from any section the contract already marked `addressed`/required, since that's exactly the evidence the LLM is being instructed to address.
- Deduplicate near-identical boilerplate text across label records (same drug, same section) before applying any cap, so redundant manufacturer copies don't consume slots that could carry distinct information.

**Done when:** The reported query's evidence packet includes `drug_interactions` text for both ibuprofen and aspirin, and the synthesized answer no longer reports missing `drug_interactions` evidence that was actually retrieved but previously dropped before reaching the prompt.

---

### D3 — Evaluation harness & curated question set

**Effort:** L · **Impact:** High · **Status:** todo

**Goal:** A reproducible eval over a curated question set, tracking citation coverage and state coverage as quality metrics.

**Why it matters:** Makes the guardrails *measurable* and the system auditable. Coverage already exists deterministically; this formalizes it into a trackable metric.

**Scope:**
- Curate ~20–40 questions spanning pregnancy, breastfeeding, allergy context, current medication, interaction, side-effect, indication, and edge cases.
- Harness that runs the pipeline and reports state-coverage and citation-coverage per question and in aggregate.
- Store expected behaviors / regression snapshots so changes are visible.

**Done when:** `make eval` (or similar) produces a metrics report over the question set.

---

### D4 — Neural vs symbolic vs combined

**Effort:** L · **Impact:** High · **Status:** todo · **Depends on:** D3

**Goal:** For a given question, compare neural-only, symbolic-only, and combined outputs side by side.

**Why it matters:** Directly demonstrates the neuro-symbolic thesis in concrete, observable terms. Neural-only shows what the LLM does without grounding; symbolic-only shows what deterministic extraction + retrieval + coverage alone produces; combined shows how the two layers work together. Pairs naturally with D3.

**Scope:**
- Neural-only: LLM answer with no retrieved evidence/guardrails.
- Symbolic-only: deterministic extraction + retrieval + coverage, no LLM synthesis.
- Combined: the current grounded, guarded pipeline.
- An evaluation view (and/or eval-harness mode from D3) that contrasts them on the same questions, with coverage/citation metrics.

**Done when:** The three modes can be contrasted on real questions with coverage metrics.

---

### D5 — Reasoning / execution traces

**Effort:** M · **Impact:** Med · **Status:** todo

**Goal:** A clear, inspectable trace of how a query was processed: extraction → revision → resolution → retrieval → synthesis → validation.

**Why it matters:** Transparency is a core safety value and a debugging aid.

**Scope:**
- Structured per-stage trace surfaced in the UI (and/or returned in the API response).
- Tie trace steps to the provenance graph (C3) where possible.

**Done when:** Each answer can be expanded into a step-by-step processing trace.

---

## Theme E — Engineering & Codebase Health

Lower visible impact but important signal for engineering-literate readers, and they make every other package faster and safer.

### E1 — Resolver & neighborhood performance

**Effort:** M · **Impact:** Med · **Status:** todo

Same scope as [B1](#b1--rxnorm-resolver-indexing--performance) — treat as one effort. Tracked here so the engineering angle is explicit.

---

### E2 — Test fixtures, fast suite & CI

**Effort:** M · **Impact:** Med · **Status:** todo

**Goal:** A small committed RxNorm sample fixture so the core suite is fast and runs on a fresh clone, plus CI.

**Why it matters:** Tests currently take ~55 s (load real parquet) and the dossier integration tests skip without the gitignored data. A committed sample + CI protects refactors and keeps the suite useful on a fresh clone.

**Scope:**
- Tiny committed RxNorm sample (top-N RXCUIs) for fast, portable tests.
- GitHub Actions: ruff + pytest (backend), tsc + eslint (frontend).
- Keep heavier integration tests behind the existing skip-if-missing-data guard.

**Done when:** CI runs green on a fresh clone without the 8 GB data tree.

---

### E3 — Lint scope / legacy module triage

**Effort:** S · **Impact:** Med · **Status:** todo

**Goal:** Resolve the "active vs inactive module" lint split.

**Why it matters:** ruff passes only on a curated path; on full `src tests` it reports ~307 issues (mostly `W293` whitespace, some `E501`, star-imports `F403/F405`, an unused var). The split is a smell.

**Scope:**
- `ruff check --fix` for the auto-fixable majority.
- Fix the real ones (star imports, unused var) in `utils.py` / `pipelines` / `knowledge_graph`.
- Decide: are those modules part of the project (then lint them in CI) or legacy (then move to an `archive/` or notebooks area)?
- Small follow-up from A1: the legacy `knowledge_graph` extraction pipeline still reads/writes the old `data/01_raw/rxnconso_raw.parquet` / `rxnrel_raw.parquet` paths (the runtime now uses `data/01_raw/rxnorm_prescribable/<YYYYMMDD>/`). Reconcile or archive it as part of this triage.

**Done when:** A single lint command covers the whole intended surface and passes.

---

### E4 — Generate TS types from OpenAPI schema

**Effort:** M · **Impact:** Med · **Status:** todo

**Goal:** Stop hand-mirroring backend Pydantic models in `lib/types.ts` (~250 lines).

**Why it matters:** Frontend types drift from backend models silently; generating them from FastAPI's OpenAPI schema removes a whole class of bugs.

**Scope:**
- Emit the OpenAPI schema from FastAPI; generate TS types (e.g. openapi-typescript) into a generated file; replace the hand-written mirror.
- Add a check/script so regeneration is part of the workflow.

**Done when:** Frontend types are generated from the backend schema, not maintained by hand.

---

### E5 — Frontend performance for the evidence map

**Effort:** M · **Impact:** Low–Med · **Status:** todo

**Goal:** Keep the D3 force Evidence Map (~2.3k lines) smooth on larger graphs.

**Scope:**
- Profile render/simulation cost; memoize/throttle where needed; cap nodes/edges sensibly.
- Consider further splitting the component now that the dossier refactor set the pattern.

**Done when:** The map stays responsive on the densest realistic queries.

---

## Theme F — UX Polish & Smaller Improvements

Do these opportunistically, when a concrete query exposes a problem — not preemptively.

- **F1 — Evidence Map / Supporting Evidence polish** (`S`): clearer explanation for interaction-specific evidence; small visual tuning only when a real query exposes clutter.
- **F2 — Keep label limit as a deep-dive control** (`S`): not a question-flow control.
- **F3 — LLM usage / cost panel** (`S–M`): the backend already separates extraction vs synthesis API keys/models for usage tracking; surface token/cost/latency per request.
- **F4 — Prompt versioning** (`S`): keep all prompt text in `conf/base/prompts.yml`; add version labels so prompt changes are traceable.
- **F5 — Parameter extraction** (`S`): move remaining magic numbers (`MAX_LABEL_TEXT_CHARS`, `MAX_LABEL_SECTIONS`, `MAX_RXNORM_RELATIONSHIPS`, section priority/order, graph caps) into `parameters.yml`.
- **✅ F6 — Richer drug-label cards & "what is this medication" section** (`M`): normalize and surface more OpenFDA fields — `description`, `package_label_principal_display_panel`, active/inactive ingredient, purpose, dosage. Add a dedicated About section as the first Drug Labels section, showing product context per label source and visually separated from warnings/how-to-use sections. Once the cards carry this product-level detail, **retire the "labels matched by RXCUI / generic name" info-note** added in B5 (it exists only because the cards currently look ingredient-generic).

---

## Shipped

A record of completed work.

**F6 — Richer drug-label cards & medication overview**
- Normalizes additional OpenFDA product-context fields into label records:
  description, package label principal display panel, active/inactive
  ingredients, purpose, and dosage.
- Adds an About section as the first Drug Labels section, with amber section-tab
  styling and one compact product-context card per label source.
- Keeps the existing source list and standard label-section cards unchanged:
  source cards still show label number, brand/generic name, manufacturer, and
  existing details only.
- Product-context cards show the package/display-panel title on one line with a
  full cleaned tooltip, plus collapsible Purpose, Dosage, Active ingredient, and
  Inactive ingredient rows.
- Removes the temporary B5 "labels matched by RXCUI / generic name" info-note;
  ingredient-fallback caveats remain explicit.
- Defers feeding product-context fields into the LLM synthesis packet to D1, so
  the prompt can frame them as bounded product/formulation evidence rather than
  broad safety or interaction evidence.

**B2 — Specific-concept priority + ingredient fallback**
- Builds on B5's preferred-term resolution: the specific concept is kept as the
  primary/matched node.
- `RxNormParquetStore.get_ingredient_concepts()` walks composition/ingredient
  relations to a concept's active ingredient(s) (ingredients are terminal so it
  can't explode into co-ingredients).
- When the specific concept has no OpenFDA labels, retrieval broadens to its
  ingredient(s): per-ingredient bundles in `dossier.ingredient_fallback`, a
  merged tagged `label_evidence` view, a `label_evidence_scope` flag, and a
  deterministic caveat — surfaced in coverage, the synthesis evidence packet,
  and an amber note in the Drug Labels panel (with per-ingredient source
  sections for combination products).
- Primary active ingredient(s) added as Drug Network centers (own highlighted
  bubble + neighborhood), mirroring the Evidence Map.
- Drug-interaction lookups search by ingredient name, not the full product
  string (more correct and avoids malformed OpenFDA query terms).

**B5 — Query-to-concept matching & display fidelity**
- `resolve()` returns the winning RXCUI's preferred RxNorm term + TTY for display
  (keeping match_type/score from the matched row), so SPL drug-product synonyms
  no longer surface (e.g. RXCUI 198300 shows as "tretinoin 1 MG/ML Topical Cream"
  (SCD), not its `DP` synonym).
- Query n-gram scanner drops generic dosage-form words (cream, gel, tablet, …) and
  rejects mentions whose preferred TTY isn't a real medication type (SU/DF/DFG/PT),
  removing stray nodes like "CREAM" while keeping legitimate ingredient nodes.
- Frontend `rxNormTypeLabels` extended to SPL term types (DP, SU, MTH_RXN_DP, PT).
- Deterministic allergy extraction bounded so "a <other drug> … allergy" no longer
  swallows a preceding drug; the real allergen resolves into allergy state.
- RXCUI-match provenance note on the Drug Labels panel, explaining that source
  cards show the label's own generic/brand name (often the ingredient).
- Technical warnings/errors no longer surfaced in the UI (kept in API/logs).

**Foundation & launch readiness**
- A2 — About narrative: rebuilt the About page as collapsible sections (Welcome ·
  What you can do here · How it works · Goal & impact · Tech stack) in Marie's
  voice, covering the neural-vs-symbolic pipeline, the guardrails, the
  explore-the-evidence trust angle, and limitations as design honesty.
- A3 — README refresh: reframed the headline around provenance + guardrails;
  documented the pipeline, guardrail layer, data sources, and tech stack; added a
  real `make setup` run path and removed the `next build` caveat.
- A1 — Clone-and-run bootstrap: committed the minimal RxNorm runtime data
  (`rxnconso`/`rxnrel`) under `data/01_raw/rxnorm_prescribable/<YYYYMMDD>/`, with
  the resolver auto-loading the latest dated release; whitelisted the folder in
  `.gitignore` while keeping the bulk raw sources ignored; added a `Makefile`
  (`make setup` / `api` / `web` / `test` / `check`) and a `SOURCE.md` provenance
  note. OpenFDA labels fetch live (no API key needed) so a fresh clone runs
  end-to-end. Fixed `test_dossier.py` to detect data via the resolver.

**Answer reliability**
- Retry once when label evidence exists but generated bullets have no valid citations.
- Question-answer default label limit moved to `parameters.yml` (set to 10).
- Retry prompt moved to `prompts.yml`.

**Page / flow**
- Split main experience into Ask a Question, Drug Dossier, and About routes.
- Compact rx-ray header/nav and browser tab icon.
- Redesigned Ask flow: generated response, extracted state, staged loading, collapsed supporting evidence.
- File-style embedded supporting evidence; Drug Dossier as card-based deep dive.

**Guardrails / coverage V1**
- Deterministic coverage report: addressed, not_found_in_evidence, not_retrieved, out_of_scope.
- Tracks coverage for primary drug, mentioned drugs, current medications, allergies, conditions, patient context, and intent.
- Deterministic limitations appended when retrieved evidence doesn't cover important extracted state.
- Collapsible Evidence coverage UI under Generated response; polished labels; human-readable limitation wording.

**Multi-drug evidence V1**
- Compact secondary label evidence for non-primary resolved mentioned/current medications.
- Interaction-targeted OpenFDA label lookups for interaction-style questions.
- Merged/deduplicated secondary and targeted label sources by stable provenance identifiers.
- Secondary evidence, interaction-targeted hits, and RxNorm terminology context included in the answer evidence packet.
- Deterministic coverage updated so secondary evidence can address non-primary medications.
- Supporting-evidence tabs for primary and secondary medications in the Ask flow.

**Question Evidence Map V1**
- Question-level Evidence Map connecting extracted concepts, resolved medications, label sources, and label sections.
- OpenFDA interaction-targeted hits represented as weak label-text mention edges, not clinical interaction claims.
- Clicking map nodes navigates into Supporting Evidence tabs.
- Single "Explore evidence" reveal opening both Evidence Map and Supporting Evidence.
- D3 force Evidence Map only; React Flow removed from Ask flow.
- Selected-node details, graph controls, node-type legend, hover tooltips, supporting-evidence navigation.
- OpenFDA label RXCUIs preserved separately from RxNorm concept RXCUIs in Evidence Map nodes.
- One-token scanner false positives filtered (e.g. "eyes" resolving to unrelated RxNorm products).
- Default Evidence Map layout: parent-centered radial clusters, less tree-like label-section placement.

**Drug Network / graph polish**
- Improved graph limits and default rendering behavior.
- Layout/navigation details adjusted during Evidence Map V1 polish.

**C1 — Unified Drug Network (pair-level interaction evidence view)**
- Replaced per-drug RxNorm graphs and "RxNorm terminology context" panels with a
  single Drug Network tab as the first Supporting Evidence tab.
- Merges every resolved drug's neighborhood (all drugs at depth 2) with a fair
  per-center edge budget (total ÷ centers), interleaved round-robin so each drug
  is represented evenly instead of the primary dominating.
- Shared RxNorm nodes (reachable from more than one drug) tracked via
  `node_membership` and highlighted with a purple ring in the graph.
- Displayed-relationships slider defaults to the fewest edges that visually
  connect the drugs (falls back to 200 when they share no path); Fewer/More scale.
- Visual node cap scales with the number of drug centers.
- Node-click panel: center drugs get "Open [drug] tab"; other nodes get
  "Search in Drug Dossier".
- UI copy is explicit: shared nodes are RxNorm vocabulary overlap only, never
  clinical interaction evidence.
- Backend: `QuestionRxNormNetwork` model + `build_question_rxnorm_network()` in
  `src/query_answer/network.py`; parameters in `parameters.yml` / `config.py`.
- Frontend: `QuestionRxNormNetworkGraph` component in `rxnorm-knowledge-graph.tsx`;
  `buildVisualGraph` / `buildDepthLevels` generalized to multi-center sets.

**OpenFDA source profiles V1**
- Compact inline source profiles on Drug Labels source cards.
- Brand, generic, manufacturer, route, product type, substances, RXCUIs, effective date, and version surfaced from existing OpenFDA metadata.
- Source cards compact by default; profile details expand inline.
- Label details links from section cards select and toggle the matching label profile.
- Compact source profile metadata passed into Evidence Map selected label-source details.

**Context-targeted OpenFDA retrieval V1**
- Targeted OpenFDA label lookups for extracted conditions, allergies, and patient context.
- Searches relevant label fields: indications, warnings, contraindications, pregnancy/lactation, specific populations, active/inactive ingredient.
- Context-specific labels tagged and merged into primary/secondary Drug Labels evidence bundles.
- Context-specific Evidence Map edges from extracted concepts to returned label sources/sections.
- Coverage updated so context items can be addressed by context-targeted label text (without implying medical suitability).
- Generic allergy terms prevented from leaking into condition or patient-context state.
- Noun-phrase allergies (e.g. "pollen allergy") extracted into allergy state; common non-medication allergens excluded from RxNorm medication tabs.
