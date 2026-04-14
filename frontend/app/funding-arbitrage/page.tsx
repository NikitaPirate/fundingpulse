import styles from "./page.module.css";

const filterSlots = [
  "Asset scope",
  "Exchange scope",
  "Quote scope",
  "Comparison basis",
  "Period mode",
  "Normalization",
  "Delta threshold",
  "Saved presets",
];

const tableColumns = [
  "Asset",
  "Contract 1",
  "Contract 2",
  "Funding delta",
  "Abs delta",
];

const statSlots = [
  ["Mode", "Pair scan"],
  ["Density", "High-signal surface"],
  ["Next", "Filters to API"],
];

export default function FundingArbitragePage() {
  return (
    <article className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h1 className={styles.title}>Funding Arbitrage</h1>
        </div>
        <div className={styles.statusStrip}>
          {statSlots.map(([label, value]) => (
            <div key={label} className={styles.statusCell}>
              <span className={styles.headerLabel}>{label}</span>
              <span className={styles.headerValue}>{value}</span>
            </div>
          ))}
        </div>
      </header>

      <section className={styles.workspace} aria-label="Arbitrage workspace shell">
        <section className={styles.controlStrip} aria-label="Filters shell">
          <div className={styles.stripHeader}>
            <span className={styles.bandTitle}>Filters</span>
          </div>
          <div className={styles.slotRow}>
            {filterSlots.map((slot) => (
              <div key={slot} className={styles.slot}>
                <span>{slot}</span>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.surface} aria-label="Pairs table shell">
          <div className={styles.workspaceHeader}>
            <span className={styles.bandTitle}>Pairs Surface</span>
            <div className={styles.workspacePills}>
              <span>sortable</span>
              <span>click-through</span>
              <span>normalized</span>
            </div>
          </div>

          <div className={styles.tableShell}>
            <div className={styles.tableHead}>
              {tableColumns.map((column) => (
                <span key={column}>{column}</span>
              ))}
            </div>

            <div className={styles.tableBody} aria-hidden="true">
              {Array.from({ length: 10 }).map((_, index) => (
                <div key={index} className={styles.tableRow}>
                  {Array.from({ length: tableColumns.length }).map((__, cellIndex) => (
                    <span key={cellIndex} className={styles.cellBar} />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </section>
      </section>
    </article>
  );
}
