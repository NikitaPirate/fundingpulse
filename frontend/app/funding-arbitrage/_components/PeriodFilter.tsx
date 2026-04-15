"use client";

import { useState } from "react";

import styles from "../page.module.css";
import { createCustomPeriod } from "../_lib/query-state";
import type { PeriodPreset, PeriodState } from "../_lib/types";
import { FilterPopover } from "./FilterPopover";

const PERIOD_PRESETS: Array<{ value: PeriodPreset; label: string }> = [
  { value: "8h", label: "8 Hours" },
  { value: "1d", label: "1 Day" },
  { value: "3d", label: "3 Days" },
  { value: "7d", label: "7 Days" },
  { value: "14d", label: "14 Days" },
  { value: "30d", label: "30 Days" },
  { value: "90d", label: "90 Days" },
];

type PeriodFilterProps = {
  value: PeriodState;
  onChange: (value: PeriodState) => void;
};

export function PeriodFilter({ value, onChange }: PeriodFilterProps) {
  const [fromDate, setFromDate] = useState(
    value.type === "custom" ? value.fromDate : "",
  );
  const [toDate, setToDate] = useState(value.type === "custom" ? value.toDate : "");

  return (
    <FilterPopover
      active={value.type !== "live"}
      label="Period"
      panelClassName={styles.periodPanel}
      summary={
        value.type === "live" ? (
          <span className={styles.liveSummary}>
            <span aria-hidden="true" className={styles.liveIndicator} />
            <span>{value.label}</span>
          </span>
        ) : (
          value.label
        )
      }
    >
      {({ close }) => (
        <>
          <div className={styles.panelHeader}>
            <strong className={styles.panelTitle}>Period</strong>
          </div>

          <div className={styles.periodGrid}>
            <button
              className={`${styles.periodButton} ${
                value.type === "live" ? styles.periodButtonActive : ""
              }`}
              onClick={() => {
                onChange({ type: "live", label: "Live" });
                close();
              }}
              type="button"
            >
              Live
            </button>

            {PERIOD_PRESETS.map((preset) => {
              const active =
                value.type === "preset" && value.preset === preset.value;

              return (
                <button
                  className={`${styles.periodButton} ${
                    active ? styles.periodButtonActive : ""
                  }`}
                  key={preset.value}
                  onClick={() => {
                    onChange({
                      type: "preset",
                      preset: preset.value,
                      label: preset.label,
                    });
                    close();
                  }}
                  type="button"
                >
                  {preset.label}
                </button>
              );
            })}
          </div>

          <div className={styles.customRange}>
            <div className={styles.customRangeHeader}>
              <strong className={styles.panelSubtitle}>Custom range</strong>
            </div>

            <div className={styles.customRangeFields}>
              <label className={styles.dateField}>
                <span>From</span>
                <input
                  className={styles.dateInput}
                  onChange={(event) => setFromDate(event.target.value)}
                  type="date"
                  value={fromDate}
                />
              </label>

              <label className={styles.dateField}>
                <span>To</span>
                <input
                  className={styles.dateInput}
                  onChange={(event) => setToDate(event.target.value)}
                  type="date"
                  value={toDate}
                />
              </label>
            </div>

            <button
              className={styles.applyCustomButton}
              disabled={!fromDate || !toDate || fromDate > toDate}
              onClick={() => {
                onChange(createCustomPeriod(fromDate, toDate));
                close();
              }}
              type="button"
            >
              Apply custom range
            </button>
          </div>
        </>
      )}
    </FilterPopover>
  );
}
