import type { ClaimSummary, Evidence, EvidenceStatus } from "@/lib/api/types";
import styles from "./EvidenceCard.module.css";

export interface EvidenceCardProps {
  claim: Pick<ClaimSummary, "ordinal" | "text">;
  evidence: Evidence;
}

const STATUS_LABEL: Record<EvidenceStatus, string> = {
  supported: "Supported",
  contradicted: "Contradicted",
  insufficient_evidence: "Insufficient evidence",
};

const STATUS_BADGE_CLASS: Record<EvidenceStatus, string> = {
  supported: styles.badgeSupported,
  contradicted: styles.badgeContradicted,
  insufficient_evidence: styles.badgeInsufficient,
};

export function EvidenceCard({ claim, evidence }: EvidenceCardProps) {
  const { source } = evidence;

  return (
    <article className={`card ${styles.card}`}>
      <div className={styles.claimRow}>
        <p className={styles.claimText}>
          <span className={styles.ordinal}>#{claim.ordinal + 1}</span>
          {claim.text}
        </p>
        <span className={`${styles.badge} ${STATUS_BADGE_CLASS[evidence.status]}`}>
          {STATUS_LABEL[evidence.status]}
        </span>
      </div>

      {evidence.explanation && <p className={styles.explanation}>{evidence.explanation}</p>}

      {evidence.quote && <blockquote className={styles.quote}>&ldquo;{evidence.quote}&rdquo;</blockquote>}

      {evidence.similarity !== null && (
        <p className={styles.similarity}>Similarity score: {evidence.similarity.toFixed(2)}</p>
      )}

      {source ? (
        <div className={styles.citation}>
          <div className={styles.citationHeading}>
            <span className={styles.citationBadge}>{source.filing_type}</span>
            <span className={styles.citationSection}>{source.section}</span>
          </div>
          <span className={styles.citationDates}>
            Period ending {source.period_end} &middot; Filed {source.filed_at}
          </span>
          <a
            className={styles.sourceLink}
            href={source.source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              aria-hidden="true"
              className={styles.sourceLinkIcon}
            >
              <path
                d="M5 1H1v10h10V7M7 1h4v4M11 1 5.5 6.5"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            View filing
          </a>
        </div>
      ) : (
        <p className={styles.noCitation}>
          No supporting passage was found in the filings reviewed.
        </p>
      )}
    </article>
  );
}
