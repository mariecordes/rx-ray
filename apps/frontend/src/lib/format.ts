export const sectionLabels: Record<string, string> = {
  boxed_warning: "Boxed Warning",
  contraindications: "Contraindications",
  warnings: "Warnings",
  drug_interactions: "Drug Interactions",
  pregnancy: "Pregnancy",
  lactation: "Lactation",
  adverse_reactions: "Adverse Reactions",
  indications_and_usage: "Indications & Usage",
  use_in_specific_populations: "Specific Populations",
  pediatric_use: "Pediatric Use",
  geriatric_use: "Geriatric Use",
  active_ingredient: "Active Ingredient",
  inactive_ingredient: "Inactive Ingredient",
  description: "What This Medication Is",
  product_context: "About",
  purpose: "Purpose",
  dosage_and_administration: "Dosage & Administration",
};

export const rxNormTypeLabels: Record<string, string> = {
  IN: "Ingredient",
  PIN: "Precise Ingredient",
  MIN: "Multiple Ingredients",
  BN: "Brand Name",
  SCDC: "Semantic Clinical Drug Component",
  SCDF: "Semantic Clinical Drug Form",
  SCDFP: "Semantic Clinical Drug Form Precise",
  SCDG: "Semantic Clinical Drug Group",
  SCDGP: "Semantic Clinical Drug Form Group Precise",
  SCD: "Semantic Clinical Drug",
  GPCK: "Generic Pack",
  SBDC: "Semantic Branded Drug Component",
  SBDF: "Semantic Branded Drug Form",
  SBDFP: "Semantic Branded Drug Form Precise",
  SBDG: "Semantic Branded Drug Group",
  SBD: "Semantic Branded Drug",
  BPCK: "Brand Name Pack",
  DF: "Dose Form",
  DFG: "Dose Form Group",
  PSN: "Prescribable Name",
  SY: "Synonym",
  TMSY: "Tall Man Lettering Synonym",
  DP: "Drug Product",
  SU: "Active Substance",
  MTH_RXN_DP: "Drug Product",
  PT: "Preferred Term",
};

export function sentenceCase(value: string) {
  return value
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function titleCase(value: string) {
  return value
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase())
    .replace(/\b&\b/g, "&");
}

export function displayGraphNodeName(name: string) {
  return name.toUpperCase();
}

export function displayBrandName(name: string) {
  return name.toUpperCase();
}

export function displayGenericName(name: string) {
  return sentenceCase(name);
}

export function displayProductType(value: string) {
  if (value.toLowerCase() === "human otc drug") {
    return "Human OTC Drug";
  }
  return sentenceCase(value);
}

export function displayMentionRole(value: string) {
  const labels: Record<string, string> = {
    primary_drug: "Primary medication",
    current_medication: "Current medication",
    mentioned_drug: "Mentioned medication",
    allergy: "Allergy",
  };
  return labels[value] ?? sentenceCase(value.replaceAll("_", " "));
}

export function displayRxNormType(tty?: string | null) {
  if (!tty) {
    return "Type unknown";
  }
  return rxNormTypeLabels[tty.toUpperCase()] ?? sentenceCase(tty);
}

export function displayStateLabel(value: string) {
  return value.replaceAll("_", " ");
}

export function primaryValue(values?: string[] | null) {
  if (!values || values.length === 0) {
    return null;
  }
  return values[0];
}

export function formatEffectiveDate(value?: string | null) {
  if (!value) {
    return null;
  }
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
  }
  return value;
}
