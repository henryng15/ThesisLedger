import styles from "./Spinner.module.css";

export interface SpinnerProps {
  label: string;
  size?: "md" | "lg";
}

/** Inline loading indicator. Respects prefers-reduced-motion automatically. */
export function Spinner({ label, size = "md" }: SpinnerProps) {
  return (
    <p className={styles.wrap} role="status">
      <span className={`${styles.ring} ${size === "lg" ? styles.ringLg : ""}`} aria-hidden="true" />
      {label}
    </p>
  );
}
