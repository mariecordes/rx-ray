import type { Metadata } from "next";

import { ComparePage } from "@/components/compare/compare-page";

export const metadata: Metadata = {
  title: "Compare — rx-ray",
  description:
    "The same medication question answered three ways: unconstrained LLM, symbolic layer only, and the full neuro-symbolic pipeline.",
};

export default function Compare() {
  return <ComparePage />;
}
