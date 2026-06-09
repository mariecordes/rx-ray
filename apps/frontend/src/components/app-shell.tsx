"use client";

import { Info } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Ask a Question" },
  { href: "/dossier", label: "Drug Dossier" },
  { href: "/about", label: "About" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-[#F8F4FC]">
      <header className="w-full bg-[#05021D] px-4 pb-5 pt-4 sm:px-6 lg:px-8">
        <nav
          aria-label="Primary"
          className="mx-auto mb-4 flex w-full max-w-xl items-center justify-center gap-2"
        >
          {navItems.map((item) => {
            const isActive =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition",
                  isActive
                    ? "bg-white/15 text-white shadow-sm"
                    : "text-white/70 hover:bg-white/10 hover:text-white"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mx-auto max-w-3xl">
          <Image
            priority
            alt="rx-ray"
            className="mx-auto h-auto w-full rounded-[20px]"
            height={724}
            src="/images/rx-ray-banner.png"
            width={2172}
          />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-4xl items-center gap-2 rounded-md border border-[#D7C8F4] bg-[#EEE7FA] px-3 py-2 text-sm leading-5 text-[#3B2478]">
          <Info className="size-4 shrink-0" />
          <span>
            Educational prototype using public drug terminology and FDA label
            data. Not medical advice.
          </span>
        </div>
        {children}
      </main>
    </div>
  );
}
