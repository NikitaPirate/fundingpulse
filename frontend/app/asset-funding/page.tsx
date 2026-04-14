import styles from "./page.module.css";

const controlSlots = [
  "Asset selector",
  "Period mode",
  "Normalization",
];

const statColumns = [
  "Exchange",
  "Quote",
  "Live",
  "7d",
  "30d",
  "90d",
];

const statSlots = [
  ["Scope", "Single asset"],
  ["Rows", "Exchange quotes"],
  ["Next", "Selector to URL"],
];

export default function AssetFundingPage() {
  return (
    <article className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h1 className={styles.title}>Asset Funding</h1>
        </div>
        <div className={styles.headerStack}>
          {statSlots.map(([label, value]) => (
            <div key={label} className={styles.statusCell}>
              <span className={styles.statusLabel}>{label}</span>
              <span className={styles.statusValue}>{value}</span>
            </div>
          ))}
        </div>
      </header>

      <section className={styles.workspace} aria-label="Asset funding workspace shell">
        <section className={styles.controls}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>Controls</span>
          </div>
          <div className={styles.controlGrid}>
            {controlSlots.map((slot) => (
              <div key={slot} className={styles.controlSlot}>
                <span>{slot}</span>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.tableZone} aria-label="Contracts table shell">
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>Contracts Surface</span>
            <div className={styles.legend}>
              <span>row jump</span>
              <span>window columns</span>
              <span>sign-safe color</span>
            </div>
          </div>

          <div className={styles.tableShell}>
            <div className={styles.tableHead}>
              {statColumns.map((column) => (
                <span key={column}>{column}</span>
              ))}
            </div>

            <div className={styles.tableBody} aria-hidden="true">
              {Array.from({ length: 11 }).map((_, index) => (
                <div key={index} className={styles.tableRow}>
                  {Array.from({ length: statColumns.length }).map((__, cellIndex) => (
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
