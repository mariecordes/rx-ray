import type { ReactNode } from "react";

import { Info } from "lucide-react";

import { cn } from "@/lib/utils";

export function InfoTooltip({
  content,
  text,
}: {
  content?: ReactNode;
  text?: string;
}) {
  return (
    <span className="group relative inline-flex">
      <Info className="size-3.5 text-slate-400" />
      <span
        className={cn(
          "pointer-events-none absolute left-0 top-full z-20 mt-2 hidden max-w-[85vw] rounded-md border border-slate-200 bg-white px-3 py-2 text-xs normal-case leading-5 text-slate-700 shadow-lg group-hover:block",
          content ? "w-max" : "w-72"
        )}
      >
        {content ?? text}
      </span>
    </span>
  );
}
