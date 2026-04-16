"use client";

import styles from "./FundingChart.module.css";

type SpreadToggleProps = {
  value: "individual" | "spread";
  onChange: (value: "individual" | "spread") => void;
};

export function SpreadToggle({ value, onChange }: SpreadToggleProps) {
  return (
    <div className={styles.toggleGroup} role="tablist" aria-label="Chart display mode">
      <button
        aria-selected={value === "individual"}
        className={`${styles.toggleButton} ${
          value === "individual" ? styles.toggleButtonActive : ""
        }`}
        onClick={() => onChange("individual")}
        role="tab"
        type="button"
      >
        Individual
      </button>
      <button
        aria-selected={value === "spread"}
        className={`${styles.toggleButton} ${
          value === "spread" ? styles.toggleButtonActive : ""
        }`}
        onClick={() => onChange("spread")}
        role="tab"
        type="button"
      >
        Spread
      </button>
    </div>
  );
}
