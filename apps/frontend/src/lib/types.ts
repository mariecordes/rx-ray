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
  provenance_tags: string[];
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
  descriptions: string[];
  package_label_principal_display_panels: string[];
  active_ingredients: string[];
  inactive_ingredients: string[];
  purposes: string[];
  dosages: string[];
  rxcuis: string[];
  provenance_tags: string[];
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

export type LabelSourceProfile = {
  source_id?: string | null;
  brand_name?: string | null;
  generic_name?: string | null;
  manufacturer_name?: string | null;
  route?: string | null;
  product_type?: string | null;
  substances: string[];
  descriptions: string[];
  product_display_names: string[];
  active_ingredients: string[];
  inactive_ingredients: string[];
  purposes: string[];
  dosages: string[];
  rxcuis: string[];
  product_ndcs: string[];
  spl_ids: string[];
  spl_set_ids: string[];
  label_id?: string | null;
  set_id?: string | null;
  effective_time?: string | null;
  version?: string | null;
  provenance_tags: string[];
};

export type IngredientFallbackEvidence = {
  ingredient: RxNormConcept;
  label_evidence: OpenFDALabelEvidence;
};

export type DrugDossier = {
  query: string;
  generated_at: string;
  resolved_drug?: RxNormConcept | null;
  resolution_candidates: ResolutionCandidate[];
  rxnorm_neighborhood: RxNormNeighborhood;
  label_evidence?: OpenFDALabelEvidence | null;
  label_evidence_scope?: string;
  ingredient_fallback?: IngredientFallbackEvidence[];
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
  intents: string[];
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
  rxcui?: string | null;
};

export type ClaimSupportStatus = "strong" | "partial" | "limited" | "none";

export type EvidenceBullet = {
  text: string;
  citations: EvidenceCitation[];
  support_status?: ClaimSupportStatus | null;
};

export type EvidenceAnswer = {
  response?: string | null;
  evidence_summary?: string | null;
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
  source_id?: string | null;
  section?: string | null;
  target_rxcui?: string | null;
};

export type EvidenceCoverageReport = {
  items: EvidenceCoverageItem[];
  summary_counts: Record<string, number>;
};

export type AnswerContractKind = "must_mention" | "must_caveat";

export type AnswerCoverageLevel = "direct" | "partial" | "limited" | "none";

export type AnswerContractItem = {
  kind: AnswerContractKind;
  topic: string;
  intent?: string | null;
  statement: string;
  evidence_available: boolean;
  required_sections: string[];
  coverage_category?: string | null;
  coverage_label?: string | null;
  target_rxcui?: string | null;
};

export type AnswerContract = {
  items: AnswerContractItem[];
  coverage_level: AnswerCoverageLevel;
};

export type ValidationSeverity = "info" | "warning";

export type ValidationFinding = {
  kind: string;
  severity: ValidationSeverity;
  message: string;
  topic?: string | null;
};

export type AnswerValidationReport = {
  findings: ValidationFinding[];
  enforced_caveats: string[];
  passed: boolean;
};

export type ClaimCritique = {
  bullet_index: number;
  support_status: ClaimSupportStatus;
  rationale: string;
  issues: string[];
};

export type CritiqueSource = "llm" | "deterministic";

export type AnswerCritique = {
  enabled: boolean;
  source: CritiqueSource;
  claims: ClaimCritique[];
  global_findings: ValidationFinding[];
  regenerated: boolean;
  notes: string[];
};

export type RxNormNetworkCenter = {
  rxcui: string;
  name: string;
  tty?: string | null;
  role: string;
};

export type QuestionRxNormNetwork = {
  centers: RxNormNetworkCenter[];
  nodes: RxNormConcept[];
  edges: RxNormEdge[];
  node_membership: Record<string, string[]>;
  shared_rxcuis: string[];
  truncated: boolean;
};

export type RxNormPairContext = {
  primary_rxcui: string;
  secondary_rxcui: string;
  status: string;
  summary: string;
  direct_edges: RxNormEdge[];
  shared_neighbors: RxNormConcept[];
};

export type QuestionEvidenceMapNode = {
  id: string;
  kind: string;
  label: string;
  subtitle?: string | null;
  role?: string | null;
  rxcui?: string | null;
  label_rxcuis?: string[];
  source_id?: string | null;
  section?: string | null;
  evidence_scope?: string | null;
  tags: string[];
};

export type QuestionEvidenceMapEdge = {
  id: string;
  source: string;
  target: string;
  kind: string;
  label: string;
  rxcui?: string | null;
  source_id?: string | null;
  section?: string | null;
  evidence_scope?: string | null;
  interaction_terms?: string[];
  context_terms?: string[];
  tags: string[];
};

export type QuestionEvidenceMap = {
  nodes: QuestionEvidenceMapNode[];
  edges: QuestionEvidenceMapEdge[];
  summary_counts: Record<string, number>;
};

export type SecondaryDrugEvidence = {
  mention_text: string;
  role: string;
  resolved_concept: RxNormConcept;
  label_evidence?: OpenFDALabelEvidence | null;
  interaction_label_evidence?: OpenFDALabelEvidence | null;
  retrieval_modes: string[];
  rxnorm_context?: RxNormPairContext | null;
};

export type ContextTargetedEvidence = {
  target_label: string;
  target_category: string;
  resolved_concept: RxNormConcept;
  searched_fields: string[];
  label_evidence?: OpenFDALabelEvidence | null;
  retrieval_modes: string[];
};

export type QueryAnswerResponse = {
  understanding: QueryUnderstandingResponse;
  answer?: EvidenceAnswer | null;
  secondary_evidence: SecondaryDrugEvidence[];
  context_evidence?: ContextTargetedEvidence[];
  question_rxnorm_network: QuestionRxNormNetwork;
  question_evidence_map: QuestionEvidenceMap;
  coverage: EvidenceCoverageReport;
  contract: AnswerContract;
  validation: AnswerValidationReport;
  critique: AnswerCritique;
  warnings: string[];
  errors: string[];
};
