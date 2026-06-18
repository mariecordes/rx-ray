import {
  DrugDossier,
  LabelSourceProfile,
  OpenFDALabelRecord,
  QueryAnswerResponse,
} from "@/lib/types";
import {
  displayProductType,
  formatEffectiveDate,
  primaryValue,
  sentenceCase,
} from "@/lib/format";

export type SourceProfileField = {
  label: string;
  values: string[];
};

export function buildLabelSourceProfile(
  record: OpenFDALabelRecord
): LabelSourceProfile {
  return {
    source_id: record.source_id,
    brand_name: primaryValue(record.brand_names),
    generic_name: primaryValue(record.generic_names),
    manufacturer_name: primaryValue(record.manufacturer_names),
    route: primaryValue(record.routes),
    product_type: primaryValue(record.product_types),
    substances: uniqueProfileValues(record.substance_names),
    descriptions: uniqueProfileValues(record.descriptions ?? []),
    product_display_names: uniqueProfileValues(
      record.package_label_principal_display_panels ?? []
    ),
    active_ingredients: uniqueProfileValues(record.active_ingredients ?? []),
    inactive_ingredients: uniqueProfileValues(record.inactive_ingredients ?? []),
    purposes: uniqueProfileValues(record.purposes ?? []),
    dosages: uniqueProfileValues(record.dosages ?? []),
    rxcuis: uniqueProfileValues(record.rxcuis),
    product_ndcs: uniqueProfileValues(record.product_ndcs),
    spl_ids: uniqueProfileValues(record.spl_ids),
    spl_set_ids: uniqueProfileValues(record.spl_set_ids),
    label_id: record.id,
    set_id: record.set_id,
    effective_time: formatEffectiveDate(record.effective_time),
    version: record.version,
    provenance_tags: uniqueProfileValues(record.provenance_tags),
  };
}

export function buildLabelSourceProfilesBySourceId(
  records: OpenFDALabelRecord[]
): Map<string, LabelSourceProfile> {
  const profiles = new Map<string, LabelSourceProfile>();
  for (const record of records) {
    if (record.source_id && !profiles.has(record.source_id)) {
      profiles.set(record.source_id, buildLabelSourceProfile(record));
    }
  }
  return profiles;
}

export function labelSourceProfilesFromEvidence(
  dossier: DrugDossier | null,
  response: QueryAnswerResponse | null
) {
  return buildLabelSourceProfilesBySourceId([
    ...(dossier?.label_evidence?.label_records ?? []),
    ...(response?.secondary_evidence ?? []).flatMap(
      (item) => item.label_evidence?.label_records ?? []
    ),
  ]);
}

export function uniqueProfileValues(values: string[]) {
  return Array.from(
    new Set(values.map((value) => value.trim()).filter(Boolean))
  );
}

export function sourceProfileProductFields(
  profile: LabelSourceProfile
): SourceProfileField[] {
  return compactProfileFields([
    { label: "Route", values: profile.route ? [sentenceCase(profile.route)] : [] },
    {
      label: "Product type",
      values: profile.product_type ? [displayProductType(profile.product_type)] : [],
    },
    { label: "Substances", values: profile.substances.map(sentenceCase) },
    { label: "RXCUI", values: profile.rxcuis },
  ]);
}

export function sourceProfileIdentifierFields(
  profile: LabelSourceProfile
): SourceProfileField[] {
  return compactProfileFields([
    {
      label: "Effective date",
      values: profile.effective_time ? [profile.effective_time] : [],
    },
    { label: "Version", values: profile.version ? [profile.version] : [] },
  ]);
}

export function compactProfileFields(fields: SourceProfileField[]) {
  return fields.filter((field) => field.values.length > 0);
}

export function hasLabelSourceProfileDetails(profile: LabelSourceProfile) {
  return (
    sourceProfileProductFields(profile).length > 0 ||
    sourceProfileIdentifierFields(profile).length > 0
  );
}

export function compactProfileValue(values: string[], maxValues = 3) {
  const visibleValues = values.slice(0, maxValues);
  const hiddenCount = Math.max(0, values.length - visibleValues.length);
  return {
    visible: hiddenCount
      ? `${visibleValues.join(", ")} +${hiddenCount} more`
      : visibleValues.join(", "),
    title: values.join(", "),
  };
}

export function LabelSourceProfileDetails({
  profile,
}: {
  profile: LabelSourceProfile;
}) {
  const fields = [
    ...sourceProfileProductFields(profile),
    ...sourceProfileIdentifierFields(profile),
  ];

  if (!fields.length) {
    return null;
  }

  return (
    <div className="mt-2 rounded-md border border-slate-200/80 bg-white/70 p-2 text-xs leading-5 text-slate-600">
      <SourceProfileFields fields={fields} />
    </div>
  );
}

export function SourceProfileFields({
  fields,
}: {
  fields: SourceProfileField[];
}) {
  return (
    <dl className="space-y-1">
      {fields.map((field) => {
        const value = compactProfileValue(field.values);
        return (
          <div
            key={field.label}
            className="grid grid-cols-[88px_minmax(0,1fr)] gap-2"
          >
            <dt className="text-slate-500">{field.label}</dt>
            <dd className="min-w-0 truncate text-slate-800" title={value.title}>
              {value.visible}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
