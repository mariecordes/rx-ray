import { Suspense } from "react";

import { DrugDossierPage } from "@/components/drug-dossier-page";

export default function DossierPage() {
  // DrugDossierExperience reads useSearchParams(); Next.js requires a Suspense
  // boundary above it so the route can be statically prerendered.
  return (
    <Suspense>
      <DrugDossierPage />
    </Suspense>
  );
}
