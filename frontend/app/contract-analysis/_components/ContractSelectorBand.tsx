"use client";

import { OptionsFilter } from "../../_components/OptionsFilter";
import styles from "../page.module.css";
import type { ContractMeta, Normalization } from "../_lib/types";
import { ContractSelector } from "./ContractSelector";

type ContractSelectorBandProps = {
  c1Meta: ContractMeta | null;
  c1MetaError: string | null;
  c2Meta: ContractMeta | null;
  c2MetaError: string | null;
  normalize: Normalization;
  onUpdateC1: (contractId: string | null) => void;
  onUpdateC2: (contractId: string | null) => void;
  onNormalizeChange: (normalize: Normalization) => void;
  onSwap: () => void;
  onClearAll: () => void;
};

const NORMALIZATION_OPTIONS: Array<{ value: Normalization; label: string }> = [
  { value: "raw", label: "Raw" },
  { value: "1h", label: "1 Hour" },
  { value: "8h", label: "8 Hours" },
  { value: "1d", label: "1 Day" },
  { value: "365d", label: "365 Days" },
];

export function ContractSelectorBand({
  c1Meta,
  c1MetaError,
  c2Meta,
  c2MetaError,
  normalize,
  onUpdateC1,
  onUpdateC2,
  onNormalizeChange,
  onSwap,
  onClearAll,
}: ContractSelectorBandProps) {
  return (
    <section className={styles.controlStrip} aria-label="Contract analysis selection">
      <div className={styles.stripHeader}>
        <span className={styles.bandTitle}>Selection</span>
        <button className={styles.clearFiltersButton} onClick={onClearAll} type="button">
          Clear all
        </button>
      </div>

      <div className={styles.selectorGrid}>
        <ContractSelector
          error={c1MetaError}
          label="Contract 1"
          onChange={onUpdateC1}
          selectedMeta={c1Meta}
        />
        <ContractSelector
          error={c2MetaError}
          label="Contract 2"
          onChange={onUpdateC2}
          selectedMeta={c2Meta}
        />
        <button className={styles.swapButton} onClick={onSwap} type="button">
          Swap order
        </button>
        <OptionsFilter
          active={normalize !== "365d"}
          label="Normalization"
          multiple={false}
          onChange={(value) => onNormalizeChange((value as Normalization | null) ?? "365d")}
          options={NORMALIZATION_OPTIONS}
          value={normalize}
        />
      </div>
    </section>
  );
}
