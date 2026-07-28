"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import styles from "./AppShell.module.css";

const NAV_LINKS = [
  { href: "/", label: "New Analysis" },
  { href: "/results", label: "Results" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname.startsWith(href);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <span className={styles.brand}>ThesisLedger</span>
          <nav className={styles.nav} aria-label="Primary">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`${styles.navLink} ${
                  isActive(pathname, link.href) ? styles.navLinkActive : ""
                }`}
                aria-current={isActive(pathname, link.href) ? "page" : undefined}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className={styles.main}>{children}</main>
    </>
  );
}
