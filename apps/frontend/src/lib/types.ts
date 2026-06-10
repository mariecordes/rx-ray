export type RxNormConcept = {
  rxcui: string;
  name: string;
  tty?: string | null;
  sab?: string | null;
};

export type ResolutionCandidate = {
  concept: RxNormConcept;
  match_type: string;
  score: number;
};

export type RxNormEdge = {
  source_rxcui: string;
  source_name: string;
  source_tty?: string | null;
  target_rxcui: string;
  target_name: string;
  target_tty?: string | null;
  relation: string;
  source: string;
};

export type RxNormNeighborhood = {
  nodes: RxNormConcept[];
  edges: RxNormEdge[];
  depth: number;
  truncated: boolean;
};

export type LabelSection = {
  section: string;
  text: string;
  source_id?: string | null;
  effective_time?: string | null;
  source: string;
};

export type OpenFDALabelRecord = {
  source_id?: string | null;
  id?: string | null;
  set_id?: string | null;
  spl_ids: string[];
  spl_set_ids: string[];
  effective_time?: string | null;
  version?: string | null;
  brand_names: string[];
  generic_names: string[];
  manufacturer_names: string[];
  product_ndcs: string[];
  product_types: string[];
  routes: string[];
  substance_names: string[];
  rxcuis: string[];
};

export type OpenFDALabelEvidence = {
  rxcui: string;
  labels_found: number;
  label_limit?: number | null;
  retrieval_mode: string;
  label_records: OpenFDALabelRecord[];
  summary_metadata: Record<string, string[]>;
  sections: Record<string, LabelSection[]>;
  section_flags: Record<string, boolean>;
  errors: string[];
};

export type DrugDossier = {
  query: string;
  generated_at: string;
  resolved_drug?: RxNormConcept | null;
  resolution_candidates: ResolutionCandidate[];
  rxnorm_neighborhood: RxNormNeighborhood;
  label_evidence?: OpenFDALabelEvidence | null;
  notes: string[];
};

export type QueryState = {
  primary_drug?: string | null;
  all_drugs_mentioned: string[];
  current_medications: string[];
  allergies: string[];
  conditions: string[];
  patient_context: string[];
  intent?: string | null;
};

export type DrugMentionRole =
  | "primary_drug"
  | "current_medication"
  | "allergy"
  | "mentioned_drug";

export type ResolvedDrugMention = {
  text: string;
  role: DrugMentionRole;
  candidates: ResolutionCandidate[];
  selected_concept?: RxNormConcept | null;
};

export type QueryUnderstandingResponse = {
  query: string;
  extraction_mode: "deterministic" | "llm" | "hybrid";
  state: QueryState;
  resolved_drugs: ResolvedDrugMention[];
  primary_dossier?: DrugDossier | null;
  warnings: string[];
  errors: string[];
};

export type EvidenceCitation = {
  source_id: string;
  section: string;
  snippet?: string | null;
};

export type EvidenceBullet = {
  text: string;
  citations: EvidenceCitation[];
};

export type EvidenceAnswer = {
  summary: string;
  bullets: EvidenceBullet[];
  limitations: string[];
  safety_note: string;
};

export type EvidenceCoverageStatus =
  | "addressed"
  | "not_found_in_evidence"
  | "not_retrieved"
  | "out_of_scope";

export type EvidenceCoverageItem = {
  category: string;
  label: string;
  status: EvidenceCoverageStatus;
  reason: string;
  matched_evidence?: string | null;
};

export type EvidenceCoverageReport = {
  items: EvidenceCoverageItem[];
  summary_counts: Record<string, number>;
};

export type QueryAnswerResponse = {
  understanding: QueryUnderstandingResponse;
  answer?: EvidenceAnswer | null;
  coverage: EvidenceCoverageReport;
  warnings: string[];
  errors: string[];
};
