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
[A1](#a1--clone-and-run-bootstrap) clone-and-run · [A2](#a2--neuro-symbolic--safety-narrative-about-page) About narrative · [A3](#a3--readme-refresh) README · [A4](#a4--live-demo-deployment) live demo · [A5](#a5--architecture-doc) architecture doc.
These determine first impressions.

**Phase 1 — Quality + speed foundation (1–2 weeks):**
[B1](#b1--rxnorm-resolver-indexing--performance)/[E1](#e1--resolver--neighborhood-performance) resolver perf · [B5](#b5--query-to-concept-matching--display-fidelity) query to concept matching & display fidelity · [B2](#b2--specific-concept-resolution-priority--ingredient-fallback) specific-concept priority + ingredient fallback · [D1](#d1--guardrails-v2) Guardrails V2 ·
[E2](#e2--test-fixtures-fast-suite--ci) fixtures + CI · [E3](#e3--lint-scope--legacy-module-triage) lint cleanup. Makes the system faster, more correct, and protected.

**Phase 2 — Research showcase (1–2 weeks):**
[D3a](#d3a--evaluation-harness--curated-question-set) evaluation harness · [D3b](#d3b--critic-accuracy-labeling-study) critic accuracy study · [D4](#d4--neural-vs-symbolic-vs-combined) neural-vs-symbolic-vs-combined, then [D7](#d7--evaluation-docs--plan-cleanup) turns the working eval plan into `docs/EVALUATION.md`. The most distinctive material; depends on Phase 1 being stable.

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
| [A4](#a4--live-demo-deployment) | Live demo | Foundation | M | High | ✅ done | A1 |
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
| [C5](#c5--synthesis-requested-retrieval-expansion) | Synthesis-requested retrieval expansion | Evidence | M–L | Med | todo | — |
| [D1](#d1--guardrails-v2) | Guardrails V2 | Safety | M | High | ✅ done | — |
| [D2](#d2--guardrails-v3) | Guardrails V3 | Safety | L | High | ✅ done | D1 |
| [D2b](#d2b--fix-cross-intent-leakage-in-the-deterministic-support-status-floor) | Fix cross-intent support-status leakage | Safety | S | High | ✅ done | D2 |
| [D2c](#d2c--fix-evidence-packet-truncation-starving-later-label-sections) | Fix evidence-packet truncation | Safety | S–M | High | ✅ done | D1, D2 |
| [D2d](#d2d--fix-uncited-sources-scope-the-support-status-gap-check-and-reframe-the-critic) | Fix uncited "sources", scope the gap check, reframe critic as source-faithfulness | Safety | M | High | ✅ done | D1, D2 |
| [D2e](#d2e--replace-the-deterministic-support-status-floor-with-a-source-faithfulness-critic) | Replace the deterministic floor with a source-faithfulness LLM critic | Safety | M | High | ✅ done | D1, D2 |
| [D2f](#d2f--more-direct-answer-tone-two-axis-support-badges-remove-critique-clutter) | More direct answer tone, two-axis support badges, remove critique clutter | Safety | S–M | Med | ✅ done | D2e |
| [D2g](#d2g--cover-the-misreads-source--contradicted-gap-in-the-critic-taxonomy) | Cover the "misreads + contradicted" gap in the critic taxonomy | Safety | S | Low | todo | D2e, D2f |
| [D2h](#d2h--joint-multi-citation-judgment-in-the-critic) | Joint multi-citation judgment in the critic | Safety | S–M | Med–High | todo | D2e, D3b |
| [D3a](#d3a--evaluation-harness--curated-question-set) | Evaluation harness | Safety | L | High | ✅ done | — |
| [D3b](#d3b--critic-accuracy-labeling-study) | Critic accuracy labeling study | Safety | S–M | High | ✅ done | D3a |
| [D4](#d4--neural-vs-symbolic-vs-combined) | Neural vs symbolic vs combined | Safety | L | High | ✅ done | D3a |
| [D5](#d5--reasoning--execution-traces) | Reasoning/execution traces | Safety | M | Med | todo | — |
| [D6](#d6--ablation-studies-on-the-eval-harness) | Ablation studies | Safety | M | Med | todo | D3a |
| [D7](#d7--evaluation-docs--plan-cleanup) | Evaluation docs & plan cleanup | Safety | S | Med | in progress | D3a, D3b, D4 |
| [E1](#e1--resolver--neighborhood-performance) | Resolver/neighborhood perf | Engineering | M | Med | todo | (=B1) |
| [E2](#e2--test-fixtures-fast-suite--ci) | Fixtures + fast suite + CI | Engineering | M | Med | todo | — |
| [E3](#e3--lint-scope--legacy-module-triage) | Lint scope / legacy triage | Engineering | S | Med | todo | — |
| [E4](#e4--generate-ts-types-from-openapi-schema) | OpenAPI→TS types | Engineering | M | Med | todo | — |
| [E5](#e5--frontend-performance-for-the-evidence-map) | Evidence map perf | Engineering | M | Low–Med | todo | — |
| [F1–F5](#theme-f--ux-polish--smaller-improvements) | UX polish & small items | Polish | S–M | Low | todo | — |
| [F6](#theme-f--ux-polish--smaller-improvements) | Richer drug-label cards & medication overview | Polish | M | Low | ✅ done | — |
| [F7](#theme-f--ux-polish--smaller-improvements) | Hide demo mode from the public Ask page | Polish | S | Low | ✅ done | — |

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

### ✅ A4 — Live demo deployment

**Effort:** M · **Impact:** High · **Status:** done · **Depends on:** A1

**Goal:** A public URL (or a polished recorded walkthrough) so no local setup is required to see the project working.

**Scope:**
- Frontend on Vercel; backend on a small host (Fly/Render/Railway) or a serverless wrapper; wire `BACKEND_URL`.
- Decide how to ship the parquet data to the backend host (depends on A1).
- Demo mode already runs without a live LLM API — make that the safe default for the public demo, with optional live mode behind a key.
- Fallback: if hosting the data backend is heavy, ship a recorded 60–90s walkthrough.

**Done when:** A link in the README opens a working demo.

> **Done.** The live app is deployed at
> [rx-ray.vercel.app](https://rx-ray.vercel.app/) with the FastAPI backend on
> Railway and the Next.js frontend on Vercel. The frontend calls same-origin
> `/api/*` proxy routes that forward to the Railway backend via `BACKEND_URL`;
> Railway builds the backend from the root Dockerfile, installs the LLM-enabled
> package, serves on the provider `PORT`, and exposes `/health` through the
> public service domain. README and About now include the live link, deployment
> stack, and repository link.

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

### C5 — Synthesis-requested retrieval expansion

**Effort:** M–L · **Impact:** Med · **Status:** todo

**Goal:** Let the synthesis step *request* more evidence instead of silently working
from truncated sections: when a cited section was capped (D2c truncation) or a
relevant section wasn't included in the packet, the model can ask for the full text
of specific, named label sections and synthesis re-runs once with the expanded
packet. Idea raised during the D3b label review.

**Why it matters:** The evidence packet caps (per-section and per-drug) exist to
bound prompt size, but they can starve the answer of detail that *was* retrieved.
A bounded request loop keeps prompts small in the common case while removing the
cap as a hard ceiling on answer quality.

**Invariant check:** compatible with the neuro-symbolic boundary — the model may
only request sections that already exist in the retrieved, whitelisted label store;
the symbolic layer decides what is served, and citations stay whitelisted.
Alternative/simpler variant to evaluate first: rank label sections by relevance to
the question intent and give the top-ranked section(s) untruncated up front, no
request loop at all.

**Done when:** Truncation-starved answers can obtain the full text of specific
retrieved sections (or the ranking variant demonstrably reduces truncation-caused
gaps), with bounded cost and unchanged citation whitelisting.

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

### ✅ D2 — Guardrails V3

**Effort:** L · **Impact:** High · **Status:** done · **Depends on:** D1

**Goal:** Extract each generated claim, map it to supporting citations, and run an optional LLM critic that flags unsupported claims, missing caveats, or overconfident wording — regenerating once on important issues.

**Scope:**
- Claim extraction + claim-to-citation alignment.
- Optional LLM critic after deterministic checks.
- One feedback-driven regeneration when important issues are found.
- Confidence language: strong / partial / limited / no retrieved coverage.

**Done when:** Answers carry per-claim support status and a critic pass with bounded regeneration.

> **Done.** Every generated bullet now carries a `support_status`
> (`strong`/`partial`/`limited`/`none`). A deterministic classifier
> (`src/query_answer/critic.py`) always runs as the floor — it checks each
> bullet's cited sections against the D1 answer_contract's addressed intents,
> so support status is populated even with no LLM critic configured (e.g. demo
> mode). An optional LLM critic (`enable_answer_critic`, off by default) reads
> each numbered claim against the same evidence packet and may override the
> deterministic status, flag issues (unsupported, overconfident, missing
> caveat, yes/no framing), and request regeneration; `finalize_answer_critique`
> performs at most one feedback-driven regeneration before re-validating and
> re-critiquing the new answer. The synthesizer gained a `critic_feedback`
> path that reuses its existing prompt/citation machinery. Per-claim support
> badges and a collapsible "Answer critique" audit section (shown only when
> the critic actually ran) are wired into the Generated response UI.
>
> Also as part of this package: removed the redundant `evidence_summary`
> field (and the `summary` field, which had become a pure duplicate of
> `response`). It was a second LLM-written paragraph largely restating the
> same evidence as `response`, with no citations of its own — the
> citation-backed bullets already do that job better. The synthesis prompt
> now directs any nuance not captured by `response` or an existing bullet
> into its own cited bullet (or a limitation, if it reflects a gap) instead
> of a freeform summary, so removing the field didn't open a path for
> unsourced claims.

---

### ✅ D2b — Fix cross-intent leakage in the deterministic support-status floor

**Effort:** S · **Impact:** High · **Status:** done · **Depends on:** D2

**Goal:** Fix a bug found while reviewing D2: the deterministic support-status
floor pooled `required_sections` across *every* addressed intent into one flat
set, so a citation that genuinely backed one intent (e.g. an allergy caveat
citing `warnings`) could spuriously "support" an unrelated bullet (e.g. an
interaction claim) just because both intents happened to share a section
name. Reproduced with *"Can I take ibuprofen for my migraine if I'm allergic
to aspirin?"*: a bullet stating no `drug_interactions` text was retrieved was
labeled "Strong support" in one run and "limited" in another, purely
depending on which section the LLM happened to cite — directly undercutting
the "I don't have evidence for that is a first-class output" invariant.

**Scope:**
- Tag each generated bullet with the `answer_contract` topic it primarily
  addresses (whitelisted against the contract's own topics, same pattern as
  citation whitelisting).
- Score `deterministic_support_status` against *that topic's* required
  sections when a match exists, falling back to the legacy pooled check for
  untagged bullets.
- Use each intent's actually-matched section(s) in the contract instead of
  the full static `INTENT_REQUIRED_SECTIONS` allow-list.

**Done when:** The reported query consistently scores the interaction-gap
bullet as `none`/`limited` regardless of which section the LLM cites, with no
regression to legitimate same-intent matches.

> **Done.** `EvidenceBullet.topic` is now parsed from synthesis output and
> whitelisted against the contract (`synthesizer.py`). `critic.py`'s
> `deterministic_support_status` scopes its section check to the matching
> contract item when a bullet's topic resolves to one, instead of pooling
> sections from every addressed intent (`_topic_required_sections`,
> falling back to `_addressed_intent_sections` for untagged bullets).
> `contract.py` also now uses each intent's actually-matched section(s)
> (`EvidenceCoverageItem.matched_sections`) instead of the static
> `INTENT_REQUIRED_SECTIONS` tuple. Verified against two live re-runs of the
> reported query: the interaction-gap bullet is now consistently tagged
> `topic="interaction_check"` and scored `none`/`limited`, while allergy
> bullets citing `warnings`/`contraindications` remain correctly `strong`.

---

### ✅ D2c — Fix evidence-packet truncation starving later label sections

**Effort:** S–M · **Impact:** High · **Status:** done · **Depends on:** D1, D2

**Goal:** Fix a retrieval/packet-construction bug found while investigating D2b: `EvidenceAnswerSynthesizer.label_section_payloads()` truncates per drug to `MAX_LABEL_SECTIONS = 16` entries, walking sections in a fixed priority order (`boxed_warning`, `contraindications`, `warnings`, `drug_interactions`, ...) with no per-section sub-limit and no deduplication. For drugs with many OTC label-record variants, near-duplicate boilerplate in the earlier sections alone can exceed the cap before later sections — including `drug_interactions` — are ever reached, even though the deterministic coverage layer (which runs on the untruncated dossier data) already confirmed that evidence exists and told the LLM to address it via the contract. Confirmed live with *"Can I take ibuprofen for my migraine if I'm allergic to aspirin?"*: ibuprofen has 2 boxed_warning + 2 contraindications + 13 warnings (10 of which are near-identical "allergy alert" boilerplate from different manufacturer records) = 17 non-empty entries before `drug_interactions` (2 real entries) is reached, so zero `drug_interactions` text ever reaches the LLM, despite `interaction_check` being marked "addressed." Aspirin shows the same pattern (24 entries before `drug_interactions`, 6 real entries dropped).

**Scope:**
- Cap entries **per section**, not just per drug overall, so one bloated section (typically `warnings`) can't crowd out every later section in the priority order.
- Make the cap **contract-aware**: guarantee at least one representative entry from any section the contract already marked `addressed`/required, since that's exactly the evidence the LLM is being instructed to address.
- Deduplicate near-identical boilerplate text across label records (same drug, same section) before applying any cap, so redundant manufacturer copies don't consume slots that could carry distinct information.

**Done when:** The reported query's evidence packet includes `drug_interactions` text for both ibuprofen and aspirin, and the synthesized answer no longer reports missing `drug_interactions` evidence that was actually retrieved but previously dropped before reaching the prompt.

> **Done.** `label_section_payloads()` now deduplicates near-identical
> boilerplate per section (normalized-text-prefix comparison) before
> counting it against any cap, caps each section to `MAX_SECTION_ENTRIES`
> so one bloated section can't crowd out the rest, and guarantees any
> section the contract relies on (`required_label_sections(contract)`, a
> new shared helper in `contract.py` also used by `critic.py`'s
> deterministic floor, replacing duplicated logic) survives the overall
> `MAX_LABEL_SECTIONS` cap by evicting from the lowest-priority tail.
> Verified against two live re-runs of the reported query: the evidence
> packet now includes `drug_interactions` text for both ibuprofen and
> aspirin, and the synthesized answer cites the real retrieved interaction
> text (`topic="interaction_check"`, `strong`) instead of falsely
> reporting that no interaction evidence was retrieved.

---

### ✅ D2d — Fix uncited sources, scope the support-status gap check, and reframe the critic

**Effort:** M · **Impact:** High · **Status:** done · **Depends on:** D1, D2

**Goal:** Found while reviewing the cetirizine/ibuprofen/aspirin query: the Sources list showed a "No citation" entry (a bullet with zero citations, displayed as if it were a retrieved source) and two well-matched bullets were rated "Partial support" despite directly reflecting their cited sections. Both traced to real bugs, plus a third, conceptual issue raised in review of the critic prompt:
1. A bullet with no citations isn't a source — it's the model noting an absence of evidence, which is a caveat. The prompt didn't forbid this, and nothing deterministic caught it before display.
2. `_has_unresolved_gap()` checks the *whole contract* for any open `must_caveat`, not just ones related to the bullet's own topic — so an unrelated gap (e.g. the patient's stated allergy term not found in any label text) capped every bullet's status at "partial," even ones whose own topic was cleanly addressed.
3. The critic prompt asks the LLM to judge "claims" in the abstract, but the UI displays the resulting status next to a *source* citation — a conceptual mismatch, since a retrieved source isn't itself "partial" or "limited." The judgment is really about whether the generated text faithfully reflects what its cited source says.

**Scope:**
- Relocate any citation-less bullet's text into `limitations` deterministically (`validate_and_enforce`), regardless of why it ended up uncited; tighten the synthesis prompt to forbid uncited bullets in the first place.
- Scope the unresolved-gap check to the bullet's own topic: a bullet whose topic resolves to a confirmed, addressed, section-bearing contract item can't have its own open caveat by construction, so it's no longer capped by gaps elsewhere in the contract. Untagged bullets keep the legacy pooled/global check.
- Reframe the `evidence_answer_critic` prompt's instructions around source-faithfulness ("does this claim accurately reflect what its cited source says") rather than abstract claim support.
- Show a bullet's support-status badge on *every* citation it has, not just the first, and add an info icon next to "Sources" explaining what each status means and that it's a structural check, not a full semantic read.

**Done when:** The Sources list never shows a citation-less entry, a bullet's status reflects only gaps related to its own topic, and the critic prompt's framing matches what's actually displayed.

> **Done.** `validate_and_enforce` now relocates any citation-less bullet's
> text into `limitations` (deduplicated against existing entries) and
> records an `uncited_bullet_relocated` finding; the synthesis prompt
> explicitly forbids uncited bullets. `deterministic_support_status` skips
> the global gap check entirely for topic-tagged bullets that resolve to a
> confirmed addressed intent (only untagged bullets keep the pooled,
> contract-wide fallback). The `evidence_answer_critic` prompt now frames
> its per-claim judgment as source-faithfulness rather than abstract claim
> support. The frontend filters citation-less bullets out of the Sources
> render as a defensive backstop, shows the support badge on every citation
> in a bullet (not just the first), and an info icon on "Sources" explains
> the status semantics. Verified live against the cetirizine/ibuprofen/
> aspirin query: all topic-tagged bullets scored `strong` despite the
> contract still carrying its own unrelated context gap, zero uncited
> bullets reached the answer, and cetirizine ended up addressed via an
> actual cited bullet instead of an uncited "no evidence" statement.

---

### ✅ D2e — Replace the deterministic support-status floor with a source-faithfulness critic

**Effort:** M · **Impact:** High · **Status:** done · **Depends on:** D1, D2

**Goal:** The deterministic floor from D2 (topic-scoped since D2b, gap-check scoped since D2d) measured something real but narrow: does a citation's section *category* belong to a contract-confirmed intent for the topic it's about. It never read the cited label text or the final response, and since the same model call that writes a bullet also picks its citation, that check was almost always trivially satisfied — it produced a badge that looked like a quality signal without reliably being one. Raised and discussed in review: is it more useful to check whether a citation actually supports what's claimed, and whether the response uses it correctly?

**Scope:**
- Delete the deterministic floor entirely (`deterministic_support_status`, `apply_deterministic_statuses`, `_topic_required_sections`, `_addressed_intent_sections`, `_has_unresolved_gap`) and the bullet-level `topic` field that only existed to feed it. The contract-level `topic` on `AnswerContractItem` (used by `validate_and_enforce`'s deterministic caveat enforcement) is untouched.
- Make the LLM critic — turned **on by default** (`enable_answer_critic: true`) — the only source of a support-status badge; when it's off or unavailable (no LLM configured, demo mode), citations simply carry no status and no badge renders, rather than falling back to a structural guess.
- Re-scope the critic from per-bullet to per-citation (`EvidenceCitation.support_status`, not `EvidenceBullet.support_status`), since a bullet can carry more than one citation and each should be judged independently.
- New two-axis, five-tier taxonomy (`accurate`, `not_reflected`, `contradicted`, `misrepresented`, `misrepresented_used`) judging each citation against (1) does the claim faithfully represent the real cited label text, and (2) does the response correctly reflect that.
- Keep the critic's prompt input minimal: query, response, limitations, and — per citation actually used — its claim text and the real cited label-section text (the same text, same D2c truncation, the synthesis model saw). Never the full evidence packet, `label_product_context`, or `answer_contract`. Defensive caps (`MAX_CRITIC_BULLETS`, `MAX_CRITIC_CITATIONS`) bound the prompt size.

**Done when:** Every citation actually used in an answer can carry its own independent support status from the critic, no structural floor exists as a fallback, and the critic's input is limited to what's strictly needed to judge faithfulness.

> **Done.** `src/query_answer/models.py`/`critic.py` rewritten per scope;
> `enable_answer_critic` defaults to `true` in both `QueryAnswerParameters`
> and `conf/base/parameters.yml`. Verified live against a multi-citation
> cetirizine/ibuprofen/aspirin query: the critic caught a citation that
> faithfully reflected its source's GI-bleeding warning but whose claim
> never actually appeared in the final response text (scored
> `not_reflected`) — exactly the kind of faithfulness gap the deleted
> structural floor could never detect. Frontend badges now read per-citation
> status across five tiers; demo mode (critic disabled) correctly renders no
> badges at all. Backend (103 tests) and frontend (`tsc`/`eslint`)
> verification clean; `notebooks/05_guardrails_v2_v3_walkthrough.ipynb`
> updated and re-executed end to end with the new design.

---

### ✅ D2f — More direct answer tone, two-axis support badges, remove critique clutter

**Effort:** S–M · **Impact:** Med · **Status:** done · **Depends on:** D2e

**Goal:** Three product/UX refinements found reviewing D2e's live output, addressed
together since two of them share a root cause:
1. The evidence-based answer narrated what the labels said but never offered a
   directional takeaway, even a hedged one — reads as evasive rather than careful.
2. The five one-word `support_status` labels (`accurate`, `contradicted`, ...) aren't
   intuitive; each secretly encodes two facts (does the claim match the source, does
   the answer reflect it), forcing readers back to a long info-tooltip paragraph to
   decode a single word.
3. The "Answer critique" section — present since the original D2 but only now
   rendering on every answer because D2e turned the critic on by default — is mostly
   clutter, and its open-ended `global_findings` output actively contradicted the
   synthesis prompt: it flagged a response for not giving a direct yes/no, which is
   exactly what the prompt forbids.

**Scope:**
- Loosen `evidence_answer_synthesis`'s framing paragraph to require a clear,
  evidence-attributed directional takeaway ("the retrieved labels point toward
  caution about combining these, because ...") instead of pure narration, while
  keeping the same hard prohibition on personal-permission phrasing ("you can/can't
  take X"). The deterministic `YES_NO_FRAMING_PATTERNS` regex backstop in
  `validation.py` is untouched — it remains the hard floor under the loosened tone.
- Frontend-only: derive two self-describing tags from each citation's existing
  single `support_status` (source-match axis + answer-use axis), collapsing the
  all-good case to a single "Verified" chip, and replace the Sources info-tooltip
  paragraph with a compact 2×3 matrix. No backend, type, or API change — this is a
  display-only derivation of D2e's existing status.
- Remove `global_findings` from the `evidence_answer_critic` prompt entirely (the
  critic now does only its per-citation faithfulness job) and delete the "Answer
  critique" section from the UI; keep only a one-line inline note when a
  regeneration happened.

**Done when:** the evidence-based answer gives a hedged but real directional
takeaway; each citation's badge is self-explanatory without the info tooltip; the
critic no longer produces or the UI no longer shows open-ended findings that can
contradict the synthesis prompt.

> **Done.** `conf/base/prompts.yml`'s synthesis framing paragraph rewritten per
> scope; `validation.py`'s yes/no regex left untouched as the hard floor. Frontend
> `generated-response.tsx` now derives `Verified` / `Matches source` + `Misreads
> source` / `Reflected in answer` + `Not reflected in answer` + `Contradicted in
> answer` tags from the existing `support_status`, with a matrix in `InfoTooltip`
> (extended to accept `ReactNode` content); header chips simplified to
> `Verified N` / `Flagged M`. `evidence_answer_critic` prompt no longer requests
> `global_findings`; `AnswerCritiqueSection` removed, replaced by a one-line
> regeneration note. Verified live against the cetirizine/ibuprofen/aspirin query:
> response now gives a hedged directional takeaway ("this is a 'discuss with a
> clinician/pharmacist' situation based on the label cautions") instead of pure
> narration; critic returns empty `global_findings` and correctly caught a citation
> whose cardiovascular-risk claim was never reflected in the response
> (`not_reflected`). Backend (103 tests, ruff) and frontend (`tsc`/`eslint`) clean;
> demo mode (critic disabled) browser-verified showing zero badges and no critique
> section; all 5 badge tiers spot-checked via a temporary demo-fixture edit,
> reverted before commit. `notebooks/05_guardrails_v2_v3_walkthrough.ipynb` updated
> and re-executed end to end, 0 errors.

---

### D2g — Cover the "misreads source + contradicted" gap in the critic taxonomy

**Effort:** S · **Impact:** Low · **Status:** todo · **Depends on:** D2e, D2f

**Goal:** D2f's two-axis badge display (source-match: matches/misreads; answer-use:
reflected/not_reflected/contradicted) exposed that the critic's 5-tier
`support_status` doesn't actually cover all 6 cells of that 2×3 matrix. The
uncovered cell is "the cited text doesn't say what the claim says, **and** the
final response says something that actively conflicts with it" — a citation that's
both misread *and* whose (incorrect) claim is then contradicted by the response.
Today the critic has no tier for this; it would presumably fall into whichever of
`misrepresented` / `misrepresented_used` the model picks, silently losing the
"contradicted" signal.

**Why it matters:** Low priority — this is a narrow edge case (the response would
have to actively conflict with something the citation never said in the first
place), not a common failure mode. Documented here mainly so the gap is a known,
deliberate trade-off rather than something rediscovered as a surprise later.

**Scope:** If ever pursued, this likely means asking the critic to report the two
axes independently (`source_match` + `answer_use` as separate enum fields) rather
than one collapsed 5-tier `support_status` — a prompt/schema change, not just a
display tweak, since the frontend's two-axis badges are currently *derived from*
the single backend status, not sourced independently.

**Done when:** Either explicitly decided not worth pursuing, or the critic reports
both axes independently and all 6 matrix cells are reachable.

---

### D2h — Joint multi-citation judgment in the critic

**Effort:** S–M · **Impact:** Med–High · **Status:** todo · **Depends on:** D2e, D3b

**Goal:** Fix a taxonomy limitation surfaced during the D3b label review: the critic
judges each citation **independently** — the same bullet text against one cited
section at a time — so a bullet legitimately synthesized from multiple sources
looks "broader than the source" against any single one of them and gets flagged
as misreading. The D3b labeling protocol deliberately shares this 1:1 framing (so
the study measures the critic on its defined task), which means human and critic
over-flag multi-source bullets *together*; the D3b error analysis should quantify
how much of the flag volume this explains before this package is scoped further.

**Scope:**
- Restructure the critic input from per-citation rows to per-bullet groups: the
  claim text together with **all** of its cited section texts.
- Two-level judgment: does the claim hold against the union of its cited texts
  (faithfulness), and per citation, does that source support its part of the claim
  (contribution). Keep per-citation `support_status` badges, but computed in
  context rather than in isolation.
- Update the D3b labeling guide/protocol to match, so any future labeling round
  measures the new task.

**Done when:** A multi-source bullet whose sources jointly support it is no longer
flaggable for being broader than any single source, verified against examples from
the D3b disagreement list.

---

### ✅ D3a — Evaluation harness & curated question set

**Effort:** L · **Impact:** High · **Status:** done

**Goal:** A reproducible eval over a curated question set, tracking citation coverage and state coverage as quality metrics.

**Why it matters:** Makes the guardrails *measurable* and the system auditable. Coverage already exists deterministically; this formalizes it into a trackable metric. Every guardrail claim is currently verified against single live queries; this is the package that replaces anecdotes with numbers.

**Scope:**
- ~32 questions in `evals/questions.yml`, stratified by intent (indication, side-effect, 2- and 3-drug interaction, allergy, pregnancy/lactation, patient context, formulation-specific), reusing the documented D2b/D2c/D2d/D2e and B2/B5 regression queries, plus 5 **trap questions** (fictional drug, false premise, out-of-scope, leading yes/no, no-product-label concept) so abstention correctness is a first-class metric.
- Expectations are behavioral and structured (what resolved, what coverage said, which guardrails fired) — never golden answer text — so they're robust to LLM nondeterminism.
- Harness in `src/evals/` consuming the existing `QueryAnswerResponse` (no production changes): extraction P/R/F1 per field, resolution rate, coverage-expectation pass rate, abstention pass rate on traps, guardrail intervention rates (enforced caveats, relocated bullets, yes/no catches, regenerations), critic status distribution, latency, and stability (mean ± std over `--repeats`).
- `make eval` (full, LLM) and `make eval-offline` (symbolic-only, keyless — later the E2 CI smoke eval); committed headline report at `evals/results/latest.{json,md}`; README gains a **Results** section quoting the numbers.

**Done when:** `make eval` produces the metrics report over the question set, including all-trap abstention results and repeat-stability, and the README Results section quotes it.

> **Done.** Harness (`src/evals/`), 42-question set, run modes
> (`combined` / `combined_extraction_only` / `symbolic`), metrics with
> match-quality tiers and the per-question matrix, `make eval` /
> `make eval-offline`, and 16 unit tests landed via PR #17. Closed out with
> the headline combined run (42 × 3 repeats): **40/42 questions pass every
> check in every repeat** (99% of 504 checks, 1 verdict flip, 0 errors),
> all 5 traps abstain correctly in every repeat, yes/no framing 0%.
> Committed to `evals/results/latest.{json,md}` alongside per-mode reports
> (`latest_symbolic`, `latest_combined_extraction_only`) backing the
> three-mode progression 28/42 → 39/42 → 40/42; headline numbers quoted in
> the README Results block and `docs/EVALUATION.md`. Both persistent
> failures are documented known gaps (q41 paracetamol resolver synonym;
> q18 intermittent pollen→`unspecified` revision regression — also the one
> verdict flip).

---

### ✅ D3b — Critic accuracy labeling study

**Effort:** S–M · **Impact:** High · **Status:** done · **Depends on:** D3a

**Goal:** Measure the LLM critic itself. Since D2e it is the *only* source of citation support-status badges — an LLM judging an LLM, currently unmeasured.

**Scope:**
- Export ~60–80 citations from eval runs into a **blind** label sheet, stratified by critic status (oversampling flagged ones).
- Hand-label the two axes the UI already derives (claim-matches-source, answer-reflects-claim).
- Score script reports per-axis raw agreement, Cohen's κ, precision/recall of "flagged" vs human labels, and a confusion matrix; short error-analysis paragraph in the eval report. Single-annotator limitation stated explicitly.

**Done when:** The eval report carries a critic-accuracy table (κ, precision/recall) with error analysis.

> **Done.** Run as a one-off experiment against the frozen 2026-07-04
> combined run: 75 citations (all 58 flagged + 17 accurate) labeled blind
> and scored (`src/evals/critic_study.py`, export/score CLIs). Results in
> `docs/EVALUATION.md` §4: flag precision 0.76, flag recall 0.96, per-axis
> κ 0.49/0.45; the 36 disagreements bucket into paraphrase-blindness (20),
> over-called misreads from per-citation judging (9), and under-called
> misreads (10, of which only 2 escaped flagging entirely). Derived next
> steps recorded as D2h and C5; synthesis-prompt fixes (evidence-scope
> statements → limitations, no retrieval-mechanics narration) landed during
> the study.

---

### ✅ D4 — Neural vs symbolic vs combined

**Effort:** L · **Impact:** High · **Status:** ✅ done · **Depends on:** D3a

**Goal:** For a given question, compare neural-only, symbolic-only, and combined outputs side by side.

**Why it matters:** Directly demonstrates the neuro-symbolic thesis in concrete, observable terms — and does it **on the live deployment**, where recruiters and casual reviewers actually look. Neural-only shows what the LLM does without grounding; symbolic-only shows what deterministic extraction + retrieval + coverage alone produces; combined shows how the two layers work together.

**Scope:**
- **Showcase deliverable: a `/compare` page in the UI** (replaces the previously planned notebook 06). Precomputed fixtures, not live calls: ~8 curated questions from `evals/questions.yml` (traps included) run through all three modes once by `scripts/build_compare_fixtures.py`, committed as static JSON, rendered as three mode columns + question picker. Default question: the fictional-drug trap, so every visitor sees the unconstrained LLM overclaim while rx-ray abstains. Zero backend/deployment changes; works in demo mode; no per-visitor LLM cost.
- Neural mode: one neutral, un-sabotaged LLM call (`neural_only_answer` prompt, neutrality requirement documented in the YAML) in `src/evals/neural.py`, shared by the fixture script and a new `run_eval.py --mode neural`.
- Deterministic property scorecard per question (`src/evals/compare.py`, unit-tested): cited-source count, personal-advice / definitive-language hits (reusing `YES_NO_FRAMING_PATTERNS`), trap handling, limitations count, safety-note presence — kept in the fixtures and the eval report's three-mode table, but not currently rendered on the page (see Shipped note). No single shared quality score (neural-only has no citations by construction) and no LLM-graded hallucination scoring (a second unvalidated judge — the D3b pattern applies first).
- The neural column always renders with a banner framing it as a demonstration of what the guardrails prevent (component-level, per the careful-framing invariant); all fixture content is eyeballed before commit.
- Phase 2 (explicitly out of scope now): env-gated, rate-limited live compare.

**Done when:** `/compare` on the live deployment shows the curated questions across all three modes, defaulting to the fictional-drug trap; `--mode neural` produces the property metrics in the eval report; the page is linked from the About page and README. (Originally also required `docs/EVALUATION.md` §3 and the README to quote 2–3 headline contrast numbers in a static table — dropped, see Shipped note: not impactful enough to justify given the interactive page already shows the difference directly.)

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

### D6 — Ablation studies on the eval harness

**Effort:** M · **Impact:** Med · **Status:** todo · **Depends on:** D3a

**Goal:** Quantify what each optional pipeline component actually contributes, reusing the D3a harness unchanged — each ablation is one flag plus one eval run.

**Scope (opportunistic, in rough value order):**
- LLM state revision on/off: does neural refinement of extracted state earn its latency?
- Critic on/off: what changes in final answers beyond badges (regenerations, caveats)?
- `default_openfda_limit` sensitivity: evidence budget vs coverage.
- Bootstrap CIs for headline metrics once the question set grows beyond ~30; until then, ±std over repeats is the honest granularity.

**Done when:** At least the first two ablations are run and written up in the eval report.

---

### D7 — Evaluation docs & plan cleanup

**Effort:** S · **Impact:** Med · **Status:** in progress · **Depends on:** D3a, D3b, D4

> **Progress:** `docs/EVALUATION.md` skeleton landed (question-set design,
> harness modes/metrics, critic-study design, D4 plan, design principles),
> with placeholders for the headline run, critic-study scores, and D4
> results.

**Goal:** Once the evaluation packages have landed and stabilized, turn the working evaluation plan into a permanent `docs/EVALUATION.md` explaining the question set design, metrics, labeling study, and mode comparison — and ensure no committed file references local-only `.claude/` paths.

**Scope:**
- Write `docs/EVALUATION.md` from the (local) working plan, updated to match what was actually built.
- Sweep committed docs for `.claude/` references and remove/repoint them.

**Done when:** A reader can understand the whole eval setup from `docs/EVALUATION.md` alone, and no committed file references `.claude/` paths.

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
- **✅ F7 — Hide demo mode from the public Ask page** (`S`): the local-fixture "Demo mode" checkbox on the Ask page was a dev convenience for reviewing frontend changes, never documented as a feature, and not something to show users on the live app. Replaced with a hidden, unlinked, `noindex` `/demo` route that auto-runs the same fixture on load - same capability, no visible toggle.

---

## Shipped

A record of completed work.

**F7 — Hide demo mode from the public Ask page**
- Removed the "Demo mode" checkbox and its caption from the Ask page. It was a dev convenience for reviewing frontend changes without live API calls, never documented anywhere as a feature, and not something to surface to users on the live app.
- Added a hidden `/demo` route (`noindex, nofollow`, not linked from nav) that auto-fills and auto-runs the same local fixture on mount. Same capability as the old checkbox, just reachable only if you know the URL. `AskQuestionExperience` gained an `autoDemo` prop reusing the same auto-run-once-on-mount pattern already built for the `/compare` "run this question live" deep link.

**D4 — Neural vs symbolic vs combined**
- `/compare` page rendering 8 curated questions (traps included) across
  neural-only, symbolic-only, and combined modes from fixtures precomputed by
  `scripts/build_compare_fixtures.py` — no per-visitor LLM cost, defaults to
  the fictional-drug trap. Columns reuse the Ask page's own components
  (query understanding, coverage audit, evidence-based answer, sources,
  caveats) rather than lookalikes, with a custom question picker (category
  chips, full question text), the rx-ray column centered and visually
  highlighted, and all three columns held to equal height.
- The deterministic property scorecard (`src/evals/compare.py`) is built and
  unit-tested but hidden on the page for now — it read as noisy this far down
  the page and didn't clearly tell the intended "raw LLM looks reckless"
  story; the code is kept to revisit later rather than deleted.
- Fixture-building surfaced and fixed two real pipeline bugs (not
  compare-specific — both apply to the live Ask page too): a drug-fragment
  extraction regex that swallowed "together" into the drug name ("Zortivan
  together with ibuprofen" → drug name "Zortivan together"), and a coverage
  item that mislabeled which drug's evidence was actually retrieved when the
  stated primary drug failed to resolve and the pipeline fell back to a
  different mentioned drug's dossier.
- Sources in the combined column now show real OpenFDA product names
  ("IBUPROFEN · Aurobindo Pharma Limited · Boxed Warning") instead of a
  synthetic "label N" placeholder, reusing the Ask page's own
  `citationDisplayLabel` formatter.
- Linked from the About page (a third entry point alongside Ask a Question
  and Drug Dossier) and the README (`What it does` + a pointer from the
  evaluation section to the live page as a hands-on version of the ablation
  story).
- Dropped from the original scope: a static comparison table with 2–3
  headline contrast numbers in `docs/EVALUATION.md` §3 — not impactful
  enough to justify, since the interactive page already lets a reader
  inspect the difference directly on any of the 8 questions.

**D3a — Evaluation harness & curated question set**
- Behavioral eval harness in `src/evals/` consuming the pipeline's structured
  `QueryAnswerResponse` (no production changes): extraction P/R/F1 with
  match-quality tiers (exact/extra/partial/none + per-question 🟢🔵🟡🔴
  matrix), coverage assertions, trap/abstention checks, guardrail
  intervention rates, latency, and repeat-stability.
- 42-question curated set stratified across 12 categories, incl. traps,
  expected-gap, complex, and typo probes; behavioral expectations only,
  calibrated to the extractor's normalized vocabulary.
- Run modes isolating each layer: `symbolic` (keyless/deterministic),
  `combined_extraction_only`, `combined`; `make eval` / `make eval-offline`;
  `scripts/run_eval.py` with `--repeats/--only/--category/--update-latest`.
- Headline run (42 × 3 repeats) committed to `evals/results/latest.{json,md}`:
  40/42 questions pass every check in every repeat (99% of 504 checks,
  1 verdict flip, 0 errors), 5/5 traps abstain in every repeat, yes/no
  framing 0%; drugs F1 0.99. Persistent failures are the two documented
  known gaps (q41 resolver synonym, q18 intermittent revision regression).
- README Results block and `docs/EVALUATION.md` headline section quote the
  numbers; the harness found real bugs during construction (pronoun→
  itraconazole resolution, revision regression, resolver synonym gap).

**D3b — Critic accuracy labeling study**
- One-off experiment against the frozen 2026-07-04 combined run over the
  42-question set: 75 citations (all 58 critic-flagged + 17 sampled accurate)
  exported to a blind sheet, hand-labeled on the two badge axes, and scored.
- Tooling: `src/evals/critic_study.py` (axis mapping mirroring the frontend
  badge derivation, Cohen's κ, flagged precision/recall, confusion matrices,
  disagreement list), `scripts/export_critic_sample.py` (blind sheet + sealed
  key from any combined run), `scripts/score_critic_labels.py`; 10 unit tests.
- Results (`docs/EVALUATION.md` §4): the critic is a strong flagger (precision
  0.76, recall 0.96) and a moderate diagnoser (per-axis κ 0.49/0.45); the 36
  disagreements bucket into paraphrase-blindness (20), over-called misreads
  from per-citation judging (9), and under-called misreads (10, only 2 of
  which escaped flagging entirely).
- Derived and recorded next steps: D2h (joint multi-citation judgment, folds
  in D2g), C5 (synthesis-requested retrieval expansion); synthesis-prompt
  fixes landed during the study (evidence-scope statements are limitations,
  no retrieval-mechanics narration).
- `docs/EVALUATION.md` created (question-set design, harness, critic study,
  D4 plan, design principles), started ahead of D7.

**A4 — Live demo deployment**
- Deployed the live app at [rx-ray.vercel.app](https://rx-ray.vercel.app/).
- Vercel serves the Next.js frontend from `apps/frontend`; browser requests stay
  same-origin through `/api/*` route handlers.
- Railway serves the FastAPI backend from the repo root Dockerfile, installs the
  LLM-enabled package, listens on the provider `PORT`, and exposes `/health`.
- `BACKEND_URL` connects the Vercel proxy routes to the Railway backend; the
  README and About page now show the live link, deployment stack, and repo link.

**D2 — Guardrails V3 (per-claim support + LLM critic)**
- Every generated bullet carries a `support_status`
  (`strong`/`partial`/`limited`/`none`) via a new `src/query_answer/critic.py`.
- A deterministic classifier always runs as the floor: it checks each bullet's
  cited sections against the D1 answer_contract's addressed intents, so
  support status is populated even with no LLM critic configured (e.g. demo
  mode); structural caveats that apply regardless of evidence quality (e.g.
  the interaction-terminology note) don't by themselves downgrade a
  well-cited claim.
- An optional LLM critic (`enable_answer_critic`, off by default, off in
  demo) reads each numbered claim against the same evidence packet used for
  synthesis and may override the deterministic status, flag issues
  (unsupported, overconfident, missing caveat, yes/no framing), and request
  regeneration.
- `finalize_answer_critique` performs at most one feedback-driven regeneration when
  the critic flags important issues, then re-validates and re-critiques the
  regenerated answer; `EvidenceAnswerSynthesizer.synthesize()` gained a
  `critic_feedback` path that reuses the existing prompt/citation machinery
  (new `evidence_answer_critic` / `evidence_answer_critic_regen` prompts).
- `QueryAnswerResponse.critique` (`AnswerCritique`) carries the outcome:
  whether the critic ran, its source, per-claim assessments, global findings,
  and whether a regeneration occurred.
- Frontend: per-claim support badges next to citations on each bullet, and a
  collapsible "Answer critique" audit section (shown only when the critic
  actually ran) below limitations.
- Removed the `evidence_summary`/`summary` fields: a second LLM-written
  paragraph largely restating `response` with no citations of its own, while
  the citation-backed bullets already did that job better. The synthesis
  prompt now directs any nuance not captured by `response` or an existing
  bullet into its own cited bullet, or a limitation if it reflects a gap.

**D2b — Fix cross-intent leakage in the deterministic support-status floor**
- Found while reviewing D2: the deterministic floor pooled `required_sections`
  across every addressed intent into one flat set, so a citation backing one
  intent (e.g. an allergy caveat citing `warnings`) could spuriously "support"
  an unrelated bullet (e.g. an interaction claim) on section-name overlap
  alone — reproduced with a query where an honest "no interaction evidence
  retrieved" bullet was inconsistently scored `strong` vs `limited` purely
  depending on which section the LLM happened to cite.
- Each generated bullet now carries a `topic` (`EvidenceBullet.topic`),
  parsed from synthesis output and whitelisted against the answer_contract's
  own topics, same pattern as citation whitelisting.
- `deterministic_support_status` scopes its section check to the matching
  contract item's `required_sections` when a bullet's topic resolves to one,
  falling back to the legacy pooled check for untagged bullets — a strict
  tightening with no regression risk.
- `build_answer_contract` now uses each intent's actually-matched section(s)
  (`EvidenceCoverageItem.matched_sections`) instead of the static
  `INTENT_REQUIRED_SECTIONS` allow-list.

**D2c — Fix evidence-packet truncation starving later label sections**
- Found while investigating D2b: even after that fix, the same query kept
  reporting missing `drug_interactions` text for ibuprofen despite the
  contract marking `interaction_check` "addressed" — because
  `label_section_payloads()` truncated per drug to a flat 16-entry cap in a
  fixed section priority order, with no per-section sub-limit and no
  deduplication, so near-duplicate boilerplate in earlier sections
  (`boxed_warning`/`contraindications`/`warnings`) exhausted the cap before
  `drug_interactions` was ever reached.
- `label_section_payloads()` now deduplicates near-identical boilerplate per
  section, caps each section to `MAX_SECTION_ENTRIES`, and guarantees any
  section the contract relies on survives the overall cap by evicting from
  the lowest-priority tail if needed.
- `required_label_sections(contract)` is a new shared helper in
  `contract.py`, used by both `build_evidence_packet` (to know which
  sections to guarantee) and `critic.py`'s deterministic floor (replacing
  duplicated logic).

**D2d — Fix uncited sources, scope the support-status gap check, and reframe the critic**
- A bullet with no citations isn't a retrieved source; `validate_and_enforce`
  now relocates its text into `limitations` (deduplicated) and the synthesis
  prompt forbids uncited bullets outright, so "No citation" entries no
  longer show up in the Sources list.
- `deterministic_support_status` no longer lets a gap unrelated to a
  bullet's own topic cap its status at "partial" — a topic-tagged bullet
  resolving to a confirmed addressed intent skips the global gap check
  entirely (only untagged bullets keep the legacy pooled fallback).
- The `evidence_answer_critic` prompt now frames its per-claim judgment as
  source-faithfulness ("does this claim accurately reflect what its cited
  source says") rather than abstract claim support, matching what the UI
  actually displays.
- Frontend: citation-less bullets are filtered out of the Sources render as
  a defensive backstop, every citation in a bullet shows its support badge
  (not just the first), and an info icon on "Sources" explains the status
  semantics and that it's a structural, not semantic, check.

**D2e — Replace the deterministic support-status floor with a source-faithfulness critic**
- Deleted the deterministic floor outright (`deterministic_support_status`,
  `apply_deterministic_statuses`, `_topic_required_sections`,
  `_addressed_intent_sections`, `_has_unresolved_gap`) along with the
  bullet-level `topic` field that only existed to feed it — the floor only
  ever checked a citation's section *category* against the topic it was
  about, never the cited text or the response, and that check was almost
  always trivially satisfied.
- The LLM critic — now **on by default** (`enable_answer_critic: true`) — is
  the only source of a support-status badge; when it's off or unavailable,
  citations simply carry no status and no badge renders.
- Re-scoped the critic from per-bullet to per-citation
  (`EvidenceCitation.support_status`), with a new two-axis, five-tier
  taxonomy (`accurate`, `not_reflected`, `contradicted`, `misrepresented`,
  `misrepresented_used`) judging each citation against the real cited label
  text and whether the response correctly reflects it.
- The critic's prompt input is deliberately minimal — query, response,
  limitations, and per-citation claim text + real cited label-section text —
  never the full evidence packet, `label_product_context`, or
  `answer_contract`; `MAX_CRITIC_BULLETS`/`MAX_CRITIC_CITATIONS` bound the
  prompt size defensively.

**D2f — More direct answer tone, two-axis support badges, remove critique clutter**
- The synthesis prompt now asks for a hedged, evidence-attributed directional
  takeaway ("the retrieved labels point toward caution...") instead of pure
  label narration, while keeping the same hard prohibition on personal
  yes/no permission phrasing and the deterministic `YES_NO_FRAMING_PATTERNS`
  regex backstop in `validation.py`, both untouched.
- The Sources badges now render each citation's existing `support_status` as
  two self-describing tags (source-match axis + answer-use axis) instead of
  one five-tier word, collapsing to a single "Verified" chip for the all-good
  case; the info tooltip is now a compact matrix instead of a paragraph. This
  is a display-only derivation — no backend, type, or API change.
- Removed the "Answer critique" section and the critic's open-ended
  `global_findings` output entirely — it rendered on every answer once D2e
  turned the critic on by default, and its advisory findings sometimes
  contradicted the synthesis prompt's own instructions (e.g. flagging a
  response for not giving a direct yes/no). Only a one-line inline note now
  surfaces when a regeneration happened.

**D1 — Guardrails V2**
- Each intent (`patient_context_check`, `allergy_context_check`,
  `interaction_check`, `side_effect_check`, `indication_check`,
  `label_context_check`) has a deterministic coverage check
  (`intent_evidence_status`) against the actual retrieved label sections,
  with matched evidence linked back into Supporting evidence in the UI.
- `build_answer_contract` turns coverage into a must-mention/must-caveat
  checklist built before synthesis and fed into the prompt, alongside a
  bounded, non-citable `label_product_context` block.
- `validate_and_enforce` runs post-generation: deterministically appends any
  must-caveat the model dropped, flags yes/no medical-advice framing, and
  records unaddressed must-mention topics as validation findings.

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
