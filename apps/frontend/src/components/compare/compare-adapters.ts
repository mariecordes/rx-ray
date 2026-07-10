import type {
  EvidenceCoverageReport,
  EvidenceCoverageStatus,
  QueryState,
} from "@/lib/types";

import type { SymbolicCoverageItem } from "./compare-types";

/** The trimmed state shape shared by the symbolic and combined fixtures. */
type CompareState = {
  primary_drug?: string | null;
  drugs: string[];
  current_medications: string[];
  allergies: string[];
  conditions: string[];
  patient_context: string[];
  intents: string[];
};

/**
 * Adapt a trimmed compare state into the real `QueryState` the Ask-page
 * components consume, so /compare can reuse them verbatim instead of
 * re-implementing look-alikes.
 */
export function toQueryState(state: CompareState): QueryState {
  const drugs = state.drugs ?? [];
  const primary =
    state.primary_drug != null && state.primary_drug !== ""
      ? state.primary_drug
      : (drugs[0] ?? null);
  return {
    primary_drug: primary,
    all_drugs_mentioned: drugs,
    current_medications: state.current_medications ?? [],
    allergies: state.allergies ?? [],
    conditions: state.conditions ?? [],
    patient_context: state.patient_context ?? [],
    intent: null,
    intents: state.intents ?? [],
  };
}

/**
 * Adapt trimmed coverage items into a real `EvidenceCoverageReport`. The
 * compare fixtures omit the interactive fields (matched_evidence, source_id,
 * target_rxcui), so the shared coverage list degrades to non-clickable
 * reasons — exactly the read-only behavior we want on /compare.
 */
export function toCoverageReport(
  items: SymbolicCoverageItem[]
): EvidenceCoverageReport {
  const summaryCounts: Record<string, number> = {};
  for (const item of items) {
    summaryCounts[item.status] = (summaryCounts[item.status] ?? 0) + 1;
  }
  return {
    items: items.map((item) => ({
      category: item.category,
      label: item.label,
      status: item.status as EvidenceCoverageStatus,
      reason: item.reason,
    })),
    summary_counts: summaryCounts,
  };
}
