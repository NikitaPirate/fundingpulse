import { Suspense } from "react";

import { AssetFundingClient } from "./_components/AssetFundingClient";
import styles from "./page.module.css";

function AssetFundingFallback() {
  return (
    <article className={styles.page}>
      <section className={styles.messagePanel}>Loading asset funding...</section>
    </article>
  );
}

export default function AssetFundingPage() {
  return (
    <Suspense fallback={<AssetFundingFallback />}>
      <AssetFundingClient />
    </Suspense>
  );
}
