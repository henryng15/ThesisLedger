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
        <div className={styles.metaRow}>
          <span className={styles.metaItem}>
            <span className={styles.metaLabel}>Section:</span> {source.section}
          </span>
          <span className={styles.metaItem}>
            <span className={styles.metaLabel}>Filing:</span> {source.filing_type}
          </span>
          <span className={styles.metaItem}>
            <span className={styles.metaLabel}>Period end:</span> {source.period_end}
          </span>
          <span className={styles.metaItem}>
            <span className={styles.metaLabel}>Filed:</span> {source.filed_at}
          </span>
          <a
            className={styles.sourceLink}
            href={source.source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
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
