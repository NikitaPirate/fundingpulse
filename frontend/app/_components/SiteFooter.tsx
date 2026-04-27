import styles from "./SiteFooter.module.css";

const projectLinks = [
  {
    href: "https://github.com/NikitaPirate/fundingpulse",
    label: "Project GitHub",
  },
  {
    href: "https://x.com/NikitaPirate",
    label: "X",
  },
  {
    href: "https://t.me/nikita_ko",
    label: "Telegram",
  },
];

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <span className={styles.brand}>FundingPulse</span>

        <nav className={styles.links} aria-label="Project links">
          {projectLinks.map((link) => (
            <a className={styles.link} href={link.href} key={link.href} rel="noreferrer" target="_blank">
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
