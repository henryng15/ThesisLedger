"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getLastJobId } from "@/lib/storage";

export default function ResultsPage() {
  const router = useRouter();

  useEffect(() => {
    const jobId = getLastJobId();
    if (jobId) {
      router.replace(`/jobs/${jobId}`);
    }
  }, [router]);

  return (
    <div>
      <h1 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "0.6rem" }}>
        No analysis results yet
      </h1>
      <p style={{ color: "var(--color-text-muted)", marginBottom: "1rem" }}>
        Start a new analysis to generate claims and check them against SEC filings.
      </p>
      <Link href="/" className="button buttonPrimary">
        Start a new analysis
      </Link>
    </div>
  );
}
