import { Suspense } from "react";

import { AskQuestionPage } from "@/components/ask-question-page";

export default function Home() {
  // AskQuestionExperience reads useSearchParams() (?q= deep-link from the
  // /compare "run live" link); Next.js requires a Suspense boundary above it
  // so the route can still be statically prerendered.
  return (
    <Suspense>
      <AskQuestionPage />
    </Suspense>
  );
}
