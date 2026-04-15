"use client";

import { useEffect, useEffectEvent, useState } from "react";

import styles from "../page.module.css";

type MinDiffFilterProps = {
  value: number | null;
  onChange: (value: number | null) => void;
};

function formatPercentage(value: number) {
  return String(Number.parseFloat((value * 100).toPrecision(12)));
}

export function MinDiffFilter({ value, onChange }: MinDiffFilterProps) {
  const [draftValue, setDraftValue] = useState(value === null ? "" : formatPercentage(value));
  const emitChange = useEffectEvent(onChange);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      const trimmed = draftValue.trim();
      if (trimmed === "") {
        emitChange(null);
        return;
      }

      const parsed = Number.parseFloat(trimmed);
      if (!Number.isFinite(parsed) || parsed < 0) {
        return;
      }

      emitChange(parsed / 100);
    }, 250);

    return () => window.clearTimeout(timeout);
  }, [draftValue]);

  return (
    <label className={styles.minDiffFilter}>
      <span className={styles.filterLabel}>Min Delta</span>
      <span className={styles.minDiffControl}>
        <input
          className={styles.minDiffInput}
          min="0"
          onChange={(event) => setDraftValue(event.target.value)}
          placeholder="0.5"
          step="0.1"
          type="number"
          value={draftValue}
        />
        <span className={styles.minDiffSuffix}>%</span>
        {draftValue ? (
          <button
            className={styles.clearInlineButton}
            onClick={() => setDraftValue("")}
            type="button"
          >
            Clear
          </button>
        ) : null}
      </span>
    </label>
  );
}
