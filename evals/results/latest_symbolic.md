# rx-ray evaluation report

Mode `symbolic` · 42 questions × 1 repeat(s) · started 2026-07-07T15:52:59+00:00

## Headline

- Questions passing all behavioral checks in every repeat: **28/42**
- Behavioral checks passed: **139/162** (86%)
- Verdict flips across repeats: 0
- Latency p50/p95: 2.5s / 7.3s
- Errors: 0

Guardrail intervention rates measure how often the deterministic
layer had to correct the neural layer — the quantity the
architecture exists to control, not an error rate of the system.

## Guardrail interventions (share of answered runs)


## Extraction & resolution (macro means)

| field | precision | recall | f1 |
|---|---|---|---|
| drugs | 0.94 | 0.93 | 0.98 |
| intents | 0.33 | 0.81 | 0.65 |
| conditions | 1.00 | 0.50 | 1.00 |
| allergies | 1.00 | 1.00 | 1.00 |
| current_medications | 0.50 | 0.12 | 0.67 |
| patient_context | 1.00 | 0.86 | 1.00 |

## Extraction match quality

Set comparison per field: `exact` = expected matched, nothing extra ·
`extra` = expected matched but extractor added more · `partial` = some
expected matched · `none` = nothing matched. Checks gate on recall
(expectations are minimum requirements), so `extra` never fails a
question — this table makes it visible instead.

| field | exact | extra | partial | none |
|---|---|---|---|---|
| drugs | 35 | 3 | 0 | 3 |
| intents | 0 | 35 | 0 | 7 |
| conditions | 4 | 0 | 0 | 4 |
| allergies | 7 | 0 | 0 | 0 |
| current_medications | 0 | 1 | 1 | 3 |
| patient_context | 6 | 0 | 0 | 1 |

## Per-question extraction match quality

🟢 exact · 🔵 extra (expected matched, extractor added more) · 🟡 partial · 🔴 none · — not graded. With repeats, each cell shows the worst grade observed.

| question | drugs | current_medications | allergies | conditions | patient_context | intents |
|---|---|---|---|---|---|---|
| q01_indication_amoxicillin | 🟢 | — | — | — | — | 🔵 |
| q02_indication_metformin | 🟢 | — | — | — | — | 🔵 |
| q03_indication_omeprazole | 🟢 | — | — | — | — | 🔵 |
| q04_indication_loratadine_hayfever | 🟢 | — | — | 🟢 | — | 🔵 |
| q05_side_effects_ibuprofen | 🟢 | — | — | — | — | 🔵 |
| q06_side_effect_amoxicillin_diarrhea | 🟢 | — | — | — | — | 🔴 |
| q07_side_effects_sertraline | 🟢 | — | — | — | — | 🔵 |
| q08_side_effect_cetirizine_drowsy | 🟢 | — | — | — | — | 🔴 |
| q09_interaction_ibuprofen_aspirin | 🟢 | — | — | — | — | 🔵 |
| q10_interaction_ibuprofen_aspirin_allergy | 🟢 | — | 🟢 | 🟢 | — | 🔵 |
| q11_interaction_sertraline_ibuprofen | 🔵 | — | — | — | — | 🔴 |
| q12_interaction_omeprazole_clopidogrel | 🟢 | — | — | — | — | 🔵 |
| q13_interaction_amoxicillin_warfarin | 🟢 | — | — | — | — | 🔵 |
| q14_interaction_cetirizine_ibuprofen_aspirin | 🟢 | 🔵 | — | — | — | 🔵 |
| q15_interaction_lisinopril_metformin_naproxen | 🟢 | 🟡 | — | — | — | 🔴 |
| q16_allergy_tretinoin_clindamycin | 🟢 | — | 🟢 | — | — | 🔵 |
| q17_allergy_amoxicillin_penicillin | 🔵 | — | 🟢 | — | — | 🔵 |
| q18_allergy_cetirizine_pollen | 🟢 | — | 🟢 | — | — | 🔵 |
| q19_allergy_hctz_sulfa | 🟢 | — | 🟢 | — | — | 🔵 |
| q20_pregnancy_acetaminophen | 🟢 | — | — | — | 🟢 | 🔵 |
| q21_lactation_ibuprofen | 🟢 | — | — | — | 🟢 | 🔵 |
| q22_pregnancy_loratadine | 🟢 | — | — | — | 🟢 | 🔵 |
| q23_context_child_cetirizine | 🟢 | — | — | — | 🟢 | 🔴 |
| q24_context_ibuprofen_hypertension | 🟢 | — | — | 🔴 | — | 🔵 |
| q25_formulation_hctz_tablet | 🟢 | — | — | — | — | 🔵 |
| q26_formulation_fluoxetine_solution | 🟢 | — | — | — | — | 🔵 |
| q27_formulation_benzoyl_peroxide_gel | 🟢 | — | — | — | — | 🔵 |
| q28_trap_fictional_drug | 🟢 | — | — | — | — | 🔵 |
| q29_trap_false_premise | 🟢 | — | — | 🔴 | — | 🔵 |
| q30_trap_out_of_scope | — | — | — | — | — | 🔵 |
| q31_trap_leading_yes_no | 🟢 | — | — | — | — | 🔵 |
| q32_trap_no_product_label | 🟢 | — | — | — | — | 🔵 |
| q33_gap_loratadine_metformin_interaction | 🟢 | — | — | — | — | 🔵 |
| q34_gap_metformin_latex_allergy | 🟢 | — | 🟢 | — | — | 🔵 |
| q35_gap_loratadine_gout | 🟢 | — | — | 🔴 | — | 🔵 |
| q36_gap_cetirizine_amoxicillin_interaction | 🟢 | — | — | — | — | 🔵 |
| q37_complex_pregnant_sertraline_penicillin_acetaminophen | 🔵 | 🔴 | 🟢 | 🟢 | 🟢 | 🔵 |
| q38_complex_elderly_warfarin_metformin_ibuprofen | 🟢 | 🔴 | — | 🟢 | 🟢 | 🔴 |
| q39_complex_multi_intent_naproxen_lisinopril | 🟢 | 🔴 | — | 🔴 | — | 🔵 |
| q40_typo_ibuprofin_asprin | 🔴 | — | — | — | — | 🔵 |
| q41_typo_paracetamol_pregant | 🔴 | — | — | — | 🔴 | 🔴 |
| q42_typo_omeprazol | 🔴 | — | — | — | — | 🔵 |

## Per category

| category | questions | passed | pass rate |
|---|---|---|---|
| allergy | 4 | 4 | 100% |
| complex | 3 | 0 | 0% |
| expected_gap | 4 | 3 | 75% |
| formulation | 3 | 3 | 100% |
| indication | 4 | 4 | 100% |
| interaction_2 | 5 | 4 | 80% |
| interaction_3 | 2 | 1 | 50% |
| patient_context | 2 | 0 | 0% |
| pregnancy_lactation | 3 | 3 | 100% |
| side_effect | 4 | 2 | 50% |
| trap | 5 | 4 | 80% |
| typo | 3 | 0 | 0% |

## Per question

| id | passed | failed checks |
|---|---|---|
| q01_indication_amoxicillin | ✅ | — |
| q02_indication_metformin | ✅ | — |
| q03_indication_omeprazole | ✅ | — |
| q04_indication_loratadine_hayfever | ✅ | — |
| q05_side_effects_ibuprofen | ✅ | — |
| q06_side_effect_amoxicillin_diarrhea | ❌ | coverage:intent:side_effect_check, intents_extracted |
| q07_side_effects_sertraline | ✅ | — |
| q08_side_effect_cetirizine_drowsy | ❌ | intents_extracted |
| q09_interaction_ibuprofen_aspirin | ✅ | — |
| q10_interaction_ibuprofen_aspirin_allergy | ✅ | — |
| q11_interaction_sertraline_ibuprofen | ❌ | coverage:intent:interaction_check, intents_extracted |
| q12_interaction_omeprazole_clopidogrel | ✅ | — |
| q13_interaction_amoxicillin_warfarin | ✅ | — |
| q14_interaction_cetirizine_ibuprofen_aspirin | ✅ | — |
| q15_interaction_lisinopril_metformin_naproxen | ❌ | coverage:intent:interaction_check, current_medications_extracted, intents_extracted |
| q16_allergy_tretinoin_clindamycin | ✅ | — |
| q17_allergy_amoxicillin_penicillin | ✅ | — |
| q18_allergy_cetirizine_pollen | ✅ | — |
| q19_allergy_hctz_sulfa | ✅ | — |
| q20_pregnancy_acetaminophen | ✅ | — |
| q21_lactation_ibuprofen | ✅ | — |
| q22_pregnancy_loratadine | ✅ | — |
| q23_context_child_cetirizine | ❌ | intents_extracted |
| q24_context_ibuprofen_hypertension | ❌ | conditions_extracted |
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
| q35_gap_loratadine_gout | ❌ | conditions_extracted |
| q36_gap_cetirizine_amoxicillin_interaction | ✅ | — |
| q37_complex_pregnant_sertraline_penicillin_acetaminophen | ❌ | current_medications_extracted |
| q38_complex_elderly_warfarin_metformin_ibuprofen | ❌ | coverage:intent:interaction_check, current_medications_extracted, intents_extracted |
| q39_complex_multi_intent_naproxen_lisinopril | ❌ | conditions_extracted, current_medications_extracted |
| q40_typo_ibuprofin_asprin | ❌ | drugs_resolved |
| q41_typo_paracetamol_pregant | ❌ | drugs_resolved, intents_extracted, patient_context_extracted |
| q42_typo_omeprazol | ❌ | drugs_resolved |
