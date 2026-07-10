import type { Metadata } from "next";
import { Suspense } from "react";

import { AskQuestionExperience } from "@/components/dossier-explorer";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function Demo() {
  // AskQuestionExperience reads useSearchParams(); Next.js requires a
  // Suspense boundary above it so the route can still be statically
  // prerendered.
  return (
    <Suspense>
      <AskQuestionExperience autoDemo />
    </Suspense>
  );
}
