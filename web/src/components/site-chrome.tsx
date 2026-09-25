import Link from "next/link";

export const REPO_URL = "https://github.com/soneeee22000/safeplate";
export const ORIGINAL_SUBMISSION_URL = "https://github.com/RitaTY/gemma4";

/**
 * The mark: a ticket stub with a refusal bar across it. Drawn in the paper and
 * refuse tokens so it matches the tickets the agent prints.
 */
export function BrandMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path
        className="fill-paper"
        d="M6 3h20v23l-2.5 3-2.5-3-2.5 3-2.5-3-2.5 3-2.5-3-2.5 3L6 26z"
      />
      <rect className="fill-refuse" x="4" y="12" width="24" height="6" />
      <rect className="fill-ink" x="10" y="7" width="12" height="2" />
      <rect className="fill-ink" x="10" y="21" width="8" height="2" />
    </svg>
  );
}

/** Site header shared by every route. */
export function SiteHeader() {
  return (
    <header className="border-console-line bg-console/90 sticky top-0 z-10 border-b backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link
          href="/"
          aria-label="SafePlate home"
          className="flex min-h-11 items-center"
        >
          <span className="brand">
            <BrandMark />
            SafePlate
          </span>
        </Link>
        <nav
          aria-label="Main"
          className="flex items-center gap-2 text-sm sm:gap-5"
        >
          <Link
            href="/#layers"
            className="text-muted-foreground hover:text-paper hidden min-h-11 min-w-11 items-center justify-center px-2 transition-colors md:flex"
          >
            How it decides
          </Link>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground hover:text-paper hidden min-h-11 min-w-11 items-center justify-center px-2 transition-colors sm:flex"
          >
            Code
          </a>
          <Link
            href="/verify"
            className="bg-paper text-console hover:bg-paper-shade flex min-h-11 items-center px-4 font-semibold transition-colors"
          >
            Try the demo
          </Link>
        </nav>
      </div>
    </header>
  );
}

const FOOTER_LINKS = [
  { href: REPO_URL, label: "GitHub repository", external: true },
  {
    href: ORIGINAL_SUBMISSION_URL,
    label: "Original hackathon submission",
    external: true,
  },
  { href: "/order", label: "Diner view (experiment)", external: false },
] as const;

/** Site footer shared by every route. */
export function SiteFooter() {
  return (
    <footer className="border-console-line border-t">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-12 sm:px-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-md">
          <span className="brand">
            <BrandMark className="size-6" />
            SafePlate
          </span>
          <p className="text-muted-foreground mt-4 text-sm leading-6">
            Hackathon project, not a product. It is not a certified food-safety
            tool, and when it refuses, ask the kitchen before serving.
          </p>
        </div>
        <ul className="flex flex-col text-sm">
          {FOOTER_LINKS.map((link) => (
            <li key={link.href}>
              {link.external ? (
                <a
                  href={link.href}
                  target="_blank"
                  rel="noreferrer"
                  className="text-muted-foreground hover:text-paper flex min-h-11 items-center transition-colors"
                >
                  {link.label}
                </a>
              ) : (
                <Link
                  href={link.href}
                  className="text-muted-foreground hover:text-paper flex min-h-11 items-center transition-colors"
                >
                  {link.label}
                </Link>
              )}
            </li>
          ))}
        </ul>
      </div>
    </footer>
  );
}
