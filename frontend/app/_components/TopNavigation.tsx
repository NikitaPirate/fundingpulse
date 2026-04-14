"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "./ThemeToggle";
import styles from "./TopNavigation.module.css";

const routes = [
  {
    href: "/funding-arbitrage",
    label: "Funding Arbitrage",
  },
  {
    href: "/asset-funding",
    label: "Asset Funding",
  },
  {
    href: "/contract-analysis",
    label: "Contract Analysis",
  },
];

export function TopNavigation() {
  const pathname = usePathname();

  return (
    <header className={styles.header}>
      <div className={styles.frame}>
        <Link className={styles.brand} href="/funding-arbitrage">
          <Image
            alt=""
            aria-hidden="true"
            className={styles.brandMark}
            height={30}
            priority
            src="/logo.svg"
            width={30}
          />
          <span className={styles.brandText}>
            <span className={styles.brandTitle}>FundingPulse</span>
            <span className={styles.brandMeta}>funding rates workbench</span>
          </span>
        </Link>

        <nav aria-label="Primary" className={styles.nav}>
          {routes.map((route) => {
            const isActive = pathname === route.href;

            return (
              <Link
                key={route.href}
                aria-current={isActive ? "page" : undefined}
                className={isActive ? styles.linkActive : styles.link}
                href={route.href}
              >
                {route.label}
              </Link>
            );
          })}
        </nav>

        <ThemeToggle />
      </div>
    </header>
  );
}
