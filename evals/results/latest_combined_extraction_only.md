# rx-ray evaluation report

Mode `combined_extraction_only` · 42 questions × 3 repeat(s) · started 2026-07-07T15:55:24+00:00

## Headline

- Questions passing all behavioral checks in every repeat: **39/42**
- Behavioral checks passed: **480/486** (99%)
- Verdict flips across repeats: 2
- Latency p50/p95: 5.0s / 14.3s
- Errors: 0

Guardrail intervention rates measure how often the deterministic
layer had to correct the neural layer — the quantity the
architecture exists to control, not an error rate of the system.

## Guardrail interventions (share of answered runs)


## Extraction & resolution (macro means)

| field | precision | recall | f1 |
|---|---|---|---|
| drugs | 0.98 | 0.98 | 0.99 |
| intents | 0.65 | 1.00 | 0.84 |
| conditions | 1.00 | 0.96 | 1.00 |
| allergies | 0.90 | 0.90 | 1.00 |
| current_medications | 0.63 | 1.00 | 1.00 |
| patient_context | 0.63 | 1.00 | 0.87 |

## Extraction match quality

Set comparison per field: `exact` = expected matched, nothing extra ·
`extra` = expected matched but extractor added more · `partial` = some
expected matched · `none` = nothing matched. Checks gate on recall
(expectations are minimum requirements), so `extra` never fails a
question — this table makes it visible instead.

| field | exact | extra | partial | none |
|---|---|---|---|---|
| drugs | 114 | 6 | 0 | 3 |
| intents | 56 | 70 | 0 | 0 |
| conditions | 23 | 0 | 0 | 1 |
| allergies | 19 | 0 | 0 | 2 |
| current_medications | 12 | 7 | 0 | 0 |
| patient_context | 13 | 14 | 0 | 0 |

## Per-question extraction match quality

🟢 exact · 🔵 extra (expected matched, extractor added more) · 🟡 partial · 🔴 none · — not graded. With repeats, each cell shows the worst grade observed.

| question | drugs | current_medications | allergies | conditions | patient_context | intents |
|---|---|---|---|---|---|---|
| q01_indication_amoxicillin | 🟢 | — | — | — | — | 🔵 |
| q02_indication_metformin | 🟢 | — | — | — | — | 🔵 |
| q03_indication_omeprazole | 🟢 | — | — | — | — | 🔵 |
| q04_indication_loratadine_hayfever | 🟢 | — | — | 🟢 | — | 🟢 |
| q05_side_effects_ibuprofen | 🟢 | — | — | — | — | 🔵 |
| q06_side_effect_amoxicillin_diarrhea | 🟢 | — | — | — | — | 🔵 |
| q07_side_effects_sertraline | 🟢 | — | — | — | — | 🔵 |
| q08_side_effect_cetirizine_drowsy | 🟢 | — | — | — | — | 🔵 |
| q09_interaction_ibuprofen_aspirin | 🟢 | — | — | — | — | 🟢 |
| q10_interaction_ibuprofen_aspirin_allergy | 🟢 | — | 🟢 | 🟢 | — | 🟢 |
| q11_interaction_sertraline_ibuprofen | 🟢 | 🔵 | — | — | — | 🟢 |
| q12_interaction_omeprazole_clopidogrel | 🟢 | — | — | — | — | 🟢 |
| q13_interaction_amoxicillin_warfarin | 🟢 | — | — | — | — | 🟢 |
| q14_interaction_cetirizine_ibuprofen_aspirin | 🟢 | 🔵 | — | — | — | 🟢 |
| q15_interaction_lisinopril_metformin_naproxen | 🟢 | 🟢 | — | — | — | 🔵 |
| q16_allergy_tretinoin_clindamycin | 🟢 | — | 🟢 | — | — | 🔵 |
| q17_allergy_amoxicillin_penicillin | 🔵 | — | 🟢 | — | — | 🔵 |
| q18_allergy_cetirizine_pollen | 🟢 | — | 🔴 | — | — | 🔵 |
| q19_allergy_hctz_sulfa | 🟢 | — | 🟢 | — | — | 🟢 |
| q20_pregnancy_acetaminophen | 🟢 | — | — | — | 🟢 | 🔵 |
| q21_lactation_ibuprofen | 🟢 | — | — | — | 🟢 | 🔵 |
| q22_pregnancy_loratadine | 🟢 | — | — | — | 🔵 | 🟢 |
| q23_context_child_cetirizine | 🟢 | — | — | — | 🔵 | 🔵 |
| q24_context_ibuprofen_hypertension | 🟢 | — | — | 🟢 | 🔵 | 🔵 |
| q25_formulation_hctz_tablet | 🟢 | — | — | — | — | 🔵 |
| q26_formulation_fluoxetine_solution | 🟢 | — | — | — | — | 🔵 |
| q27_formulation_benzoyl_peroxide_gel | 🟢 | — | — | — | — | 🔵 |
| q28_trap_fictional_drug | 🟢 | — | — | — | — | 🟢 |
| q29_trap_false_premise | 🟢 | — | — | 🔴 | — | 🔵 |
| q30_trap_out_of_scope | — | — | — | — | — | 🔵 |
| q31_trap_leading_yes_no | 🟢 | 🔵 | — | — | — | 🔵 |
| q32_trap_no_product_label | 🟢 | — | — | — | — | 🟢 |
| q33_gap_loratadine_metformin_interaction | 🟢 | — | — | — | — | 🟢 |
| q34_gap_metformin_latex_allergy | 🟢 | — | 🟢 | — | — | 🔵 |
| q35_gap_loratadine_gout | 🟢 | — | — | 🟢 | — | 🔵 |
| q36_gap_cetirizine_amoxicillin_interaction | 🟢 | — | — | — | — | 🟢 |
| q37_complex_pregnant_sertraline_penicillin_acetaminophen | 🔵 | 🟢 | 🟢 | 🟢 | 🟢 | 🔵 |
| q38_complex_elderly_warfarin_metformin_ibuprofen | 🟢 | 🟢 | — | 🟢 | 🔵 | 🔵 |
| q39_complex_multi_intent_naproxen_lisinopril | 🟢 | 🟢 | — | 🟢 | 🔵 | 🟢 |
| q40_typo_ibuprofin_asprin | 🟢 | — | — | — | — | 🟢 |
| q41_typo_paracetamol_pregant | 🔴 | — | — | — | 🟢 | 🟢 |
| q42_typo_omeprazol | 🟢 | — | — | — | — | 🔵 |

## Per category

| category | questions | passed | pass rate |
|---|---|---|---|
| allergy | 4 | 3 | 75% |
| complex | 3 | 3 | 100% |
| expected_gap | 4 | 4 | 100% |
| formulation | 3 | 3 | 100% |
| indication | 4 | 4 | 100% |
| interaction_2 | 5 | 5 | 100% |
| interaction_3 | 2 | 2 | 100% |
| patient_context | 2 | 2 | 100% |
| pregnancy_lactation | 3 | 3 | 100% |
| side_effect | 4 | 4 | 100% |
| trap | 5 | 4 | 80% |
| typo | 3 | 2 | 67% |

## Per question

| id | passed | failed checks |
|---|---|---|
| q01_indication_amoxicillin | ✅ | — |
| q02_indication_metformin | ✅ | — |
| q03_indication_omeprazole | ✅ | — |
| q04_indication_loratadine_hayfever | ✅ | — |
| q05_side_effects_ibuprofen | ✅ | — |
| q06_side_effect_amoxicillin_diarrhea | ✅ | — |
| q07_side_effects_sertraline | ✅ | — |
| q08_side_effect_cetirizine_drowsy | ✅ | — |
| q09_interaction_ibuprofen_aspirin | ✅ | — |
| q10_interaction_ibuprofen_aspirin_allergy | ✅ | — |
| q11_interaction_sertraline_ibuprofen | ✅ | — |
| q12_interaction_omeprazole_clopidogrel | ✅ | — |
| q13_interaction_amoxicillin_warfarin | ✅ | — |
| q14_interaction_cetirizine_ibuprofen_aspirin | ✅ | — |
| q15_interaction_lisinopril_metformin_naproxen | ✅ | — |
| q16_allergy_tretinoin_clindamycin | ✅ | — |
| q17_allergy_amoxicillin_penicillin | ✅ | — |
| q18_allergy_cetirizine_pollen | ❌ | allergies_extracted |
| q19_allergy_hctz_sulfa | ✅ | — |
| q20_pregnancy_acetaminophen | ✅ | — |
| q21_lactation_ibuprofen | ✅ | — |
| q22_pregnancy_loratadine | ✅ | — |
| q23_context_child_cetirizine | ✅ | — |
| q24_context_ibuprofen_hypertension | ✅ | — |
| q25_formulation_hctz_tablet | ✅ | — |
| q26_formulation_fluoxetine_solution | ✅ | — |
| q27_formulation_benzoyl_peroxide_gel | ✅ | — |
| q28_trap_fictional_drug | ✅ | — |
| q29_trap_false_premise | ❌ | conditions_extracted |
| q30_trap_out_of_scope | ✅ | — |
| q31_trap_leading_yes_no | ✅ | — |
| q32_trap_no_product_label | ✅ | — |
| q33_gap_loratadine_metformin_interaction | ✅ | — |
| q34_gap_metformin_latex_allergy | ✅ | — |
| q35_gap_loratadine_gout | ✅ | — |
| q36_gap_cetirizine_amoxicillin_interaction | ✅ | — |
| q37_complex_pregnant_sertraline_penicillin_acetaminophen | ✅ | — |
| q38_complex_elderly_warfarin_metformin_ibuprofen | ✅ | — |
| q39_complex_multi_intent_naproxen_lisinopril | ✅ | — |
| q40_typo_ibuprofin_asprin | ✅ | — |
| q41_typo_paracetamol_pregant | ❌ | drugs_resolved |
| q42_typo_omeprazol | ✅ | — |
