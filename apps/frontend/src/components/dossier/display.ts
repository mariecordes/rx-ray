import { EvidenceCitation, OpenFDALabelRecord } from "@/lib/types";
import {
  displayBrandName,
  displayGenericName,
  primaryValue,
  sectionLabels,
} from "@/lib/format";

export const unidentifiedDrugLabel = "Unidentified drug label";
export const metadataUnavailableLabel = "OpenFDA metadata unavailable";

export const sourceSelectionClasses =
  "border-[#C7B4EF] bg-[#E8DDF9] shadow-sm hover:border-[#C7B4EF]";
export const nodeSpecificClasses =
  "border-[#EACB96] bg-[#FAE8CD] hover:border-[#DDBB7E]";
export const searchSourceClasses =
  "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50";
export const nodeSpecificBadgeClasses =
  "border-slate-300 bg-slate-100 text-slate-700";
export const searchSpecificBadgeClasses =
  "border-slate-300 bg-slate-100 text-slate-700";
export const interactionSpecificBadgeClasses =
  "border-slate-300 bg-slate-100 text-slate-700";
export const contextSpecificBadgeClasses =
  "border-slate-300 bg-slate-100 text-slate-700";
export const sourceNumberBadgeClasses =
  "border-slate-200 bg-white text-slate-800";

export function displaySectionName(section: string) {
  return sectionLabels[section] ?? section.replaceAll("_", " ");
}

export function citationDisplayLabel(
  citation: EvidenceCitation,
  sourceById: Map<string, OpenFDALabelRecord>
) {
  const source = sourceById.get(citation.source_id);
  const brandName = primaryValue(source?.brand_names);
  const genericName = primaryValue(source?.generic_names);
  const manufacturerName = primaryValue(source?.manufacturer_names);
  const productName = brandName
    ? displayBrandName(brandName)
    : genericName
      ? displayGenericName(genericName)
      : unidentifiedDrugLabel;
  return [productName, manufacturerName, displaySectionName(citation.section)]
    .filter(Boolean)
    .join(" · ");
}

export function hasOpenFdaProductMetadata(record?: OpenFDALabelRecord | null) {
  return Boolean(
    record &&
      (record.brand_names.length ||
        record.generic_names.length ||
        record.manufacturer_names.length)
  );
}
