import { Suspense } from "react";

import { FundingArbitrageClient } from "./_components/FundingArbitrageClient";
import styles from "./page.module.css";

function FundingArbitrageFallback() {
  return (
    <article className={styles.page}>
      <section className={styles.messagePanel}>Loading funding arbitrage...</section>
    </article>
  );
}

export default function FundingArbitragePage() {
  return (
    <Suspense fallback={<FundingArbitrageFallback />}>
      <FundingArbitrageClient />
    </Suspense>
  );
}
