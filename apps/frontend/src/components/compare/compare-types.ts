export type CompareMode = "neural" | "symbolic" | "combined";

export interface CompareCitation {
  source_id: string;
  section: string;
  support_status: string | null;
}

export interface CompareBullet {
  text: string;
  citations: CompareCitation[];
}

export interface CombinedView {
  response: string;
  bullets: CompareBullet[];
  limitations: string[];
  safety_note: string;
}

export interface SymbolicResolved {
  text: string;
  role: string;
  rxcui: string | null;
  name: string | null;
  tty: string | null;
}

export interface SymbolicCoverageItem {
  category: string;
  label: string;
  status: string;
  reason: string;
}

export interface SymbolicView {
  state: {
    drugs: string[];
    current_medications: string[];
    allergies: string[];
    conditions: string[];
    patient_context: string[];
    intents: string[];
  };
  resolved: SymbolicResolved[];
  coverage: SymbolicCoverageItem[];
  section_counts: Record<string, number>;
  source_labels: Record<string, string>;
}

export interface NeuralView {
  text: string;
  advice_phrases: string[];
}

export type ScorecardRow<T> = Record<CompareMode, T | null>;

export interface Scorecard {
  cited_sources: ScorecardRow<number>;
  advice_language_hits: ScorecardRow<number>;
  advice_language_phrases: ScorecardRow<string[]>;
  trap_handled: ScorecardRow<boolean>;
  stated_limitations: ScorecardRow<number>;
  safety_note: ScorecardRow<boolean>;
}

export interface CompareQuestion {
  id: string;
  question: string;
  category: string;
  hint: string;
  neural: NeuralView;
  symbolic: SymbolicView;
  combined: CombinedView;
  scorecard: Scorecard;
}

export interface CompareFixtures {
  generated_at: string;
  synthesis_model: string;
  questions: CompareQuestion[];
}
