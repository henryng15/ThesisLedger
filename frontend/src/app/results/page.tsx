"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getLastJobId } from "@/lib/storage";
import styles from "./results.module.css";

export default function ResultsPage() {
  const router = useRouter();

  useEffect(() => {
    const jobId = getLastJobId();
    if (jobId) {
      router.replace(`/jobs/${jobId}`);
    }
  }, [router]);

  return (
    <div className={styles.empty}>
      <span className={styles.icon} aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
          <path
            d="M4 19V10M10 19V5M16 19v-7M20 19H3"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <h1 className={styles.title}>No analysis results yet</h1>
      <p className={styles.text}>
        Once you run an analysis, its verdicts and citations show up here.
      </p>
      <Link href="/" className="button buttonPrimary">
        Start a new analysis
      </Link>
    </div>
  );
}
