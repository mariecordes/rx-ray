import { Info } from "lucide-react";

export function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <Info className="size-3.5 text-slate-400" />
      <span className="pointer-events-none absolute left-0 top-full z-20 mt-2 hidden w-72 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs normal-case leading-5 text-slate-700 shadow-lg group-hover:block">
        {text}
      </span>
    </span>
  );
}
