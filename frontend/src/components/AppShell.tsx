"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import styles from "./AppShell.module.css";

const NAV_LINKS = [
  {
    href: "/",
    label: "New Analysis",
    icon: (
      <path
        d="M12 5v14M5 12h14"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    ),
  },
  {
    href: "/results",
    label: "Results",
    icon: (
      <path
        d="M4 19V10M10 19V5M16 19v-7M20 19H3"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand}>
            <span className={styles.brandMark} aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="14" width="4.5" height="7" rx="1.5" fill="currentColor" fillOpacity="0.5" />
                <rect x="9.75" y="9" width="4.5" height="12" rx="1.5" fill="currentColor" fillOpacity="0.8" />
                <rect x="16.5" y="3" width="4.5" height="18" rx="1.5" fill="currentColor" />
              </svg>
            </span>
            ThesisLedger
          </Link>
          <nav className={styles.topNav} aria-label="Primary">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`${styles.topLink} ${
                  isActive(pathname, link.href) ? styles.topLinkActive : ""
                }`}
                aria-current={isActive(pathname, link.href) ? "page" : undefined}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className={styles.main}>
        <div key={pathname} className={styles.page}>
          {children}
        </div>
      </main>

      <nav className={styles.tabBar} aria-label="Primary">
        {NAV_LINKS.map((link) => {
          const active = isActive(pathname, link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`${styles.tab} ${active ? styles.tabActive : ""}`}
              aria-current={active ? "page" : undefined}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                {link.icon}
              </svg>
              {link.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
