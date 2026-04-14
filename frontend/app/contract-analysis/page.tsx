import styles from "./page.module.css";

const selectorSlots = [
  "Asset context",
  "Contract 1",
  "Contract 2",
  "Swap action",
];

const summarySlots = [
  "Current rate or spread",
  "Settled reference",
  "Accumulated windows",
];

const chartSlots = [
  "Live Funding Rates",
  "Historical Funding Rates",
  "Live vs Historical",
];

const headerStats = [
  ["Mode", "One or two contracts"],
  ["Order", "Role-sensitive"],
  ["Next", "Charts and spread"],
];

export default function ContractAnalysisPage() {
  return (
    <article className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <h1 className={styles.title}>Contract Analysis</h1>
        </div>
        <div className={styles.modePlate}>
          {headerStats.map(([label, value]) => (
            <div key={label} className={styles.statusCell}>
              <span className={styles.statusLabel}>{label}</span>
              <span className={styles.statusValue}>{value}</span>
            </div>
          ))}
        </div>
      </header>

      <section className={styles.workspace} aria-label="Contract analysis workspace shell">
        <section className={styles.topStrips}>
          <section className={styles.selectorBand} aria-label="Selector shell">
            <div className={styles.sectionHeader}>
              <span className={styles.sectionTitle}>Selection</span>
            </div>
            <div className={styles.selectorGrid}>
              {selectorSlots.map((slot) => (
                <div key={slot} className={styles.selectorSlot}>
                  <span>{slot}</span>
                </div>
              ))}
            </div>
          </section>

          <section className={styles.summaryBand} aria-label="Summary shell">
            <div className={styles.sectionHeader}>
              <span className={styles.sectionTitle}>Summary</span>
            </div>

            <div className={styles.summaryGrid}>
              {summarySlots.map((slot) => (
                <div key={slot} className={styles.summarySlot}>
                  <span>{slot}</span>
                </div>
              ))}
            </div>
          </section>
        </section>

        <section className={styles.chartStack} aria-label="Charts shell">
          {chartSlots.map((slot) => (
            <section key={slot} className={styles.chartPanel}>
              <div className={styles.chartHeader}>
                <span className={styles.sectionTitle}>{slot}</span>
                <div className={styles.chartMeta}>
                  <span>timeline</span>
                  <span>mode switch</span>
                  <span>cursor legend</span>
                </div>
              </div>

              <div className={styles.chartCanvas} aria-hidden="true">
                <span className={styles.tracePrimary} />
                <span className={styles.traceSecondary} />
                <span className={styles.traceAccent} />
              </div>
            </section>
          ))}
        </section>
      </section>
    </article>
  );
}
