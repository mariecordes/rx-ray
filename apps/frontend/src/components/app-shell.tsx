"use client";

import { Info } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Ask a Question" },
  { href: "/compare", label: "Compare" },
  { href: "/dossier", label: "Drug Dossier" },
  { href: "/about", label: "About" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-[#F8F4FC]">
      <header className="w-full bg-[#05021D] py-3">
        <div className="mx-auto flex w-full max-w-[92rem] flex-col gap-4 px-4 sm:flex-row sm:items-center sm:gap-8 sm:px-6 lg:px-8">
          <Link href="/" className="block w-fit" aria-label="rx-ray home">
            <Image
              priority
              alt="rx-ray"
              className="h-22 w-66 rounded-md object-contain object-left"
              height={724}
              src="/images/rx-ray-banner.png"
              width={2172}
            />
          </Link>
          <nav
            aria-label="Primary"
            className="flex items-center gap-1 sm:gap-2"
          >
            {navItems.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
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
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[92rem] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <div className="mx-auto flex w-full items-center gap-2 rounded-md border border-[#D7C8F4] bg-[#EEE7FA] px-3 py-2 text-sm leading-5 text-[#3B2478]">
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
