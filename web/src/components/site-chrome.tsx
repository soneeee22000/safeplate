import Link from "next/link";

const REPO_URL = "https://github.com/RitaTY/gemma4";

export function SiteHeader() {
  return (
    <header className="border-console-line bg-console/90 sticky top-0 z-10 border-b backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-4">
        <Link
          href="/"
          className="font-display text-lg font-bold tracking-tight"
        >
          SafePlate
        </Link>
        <nav className="flex items-center gap-6 font-mono text-xs tracking-wider uppercase">
          <Link
            href="/order"
            className="border-paper bg-paper text-console hover:bg-paper-shade flex min-h-11 items-center border px-4 transition-colors"
          >
            Try it
          </Link>
          <Link
            href="/verify"
            className="text-muted-foreground hover:text-paper hidden transition-colors sm:inline"
          >
            Staff console
          </Link>
          <Link
            href="/#how-it-works"
            className="text-muted-foreground hover:text-paper hidden transition-colors md:inline"
          >
            How it works
          </Link>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="border-console-line hover:border-paper flex min-h-11 items-center border px-3 transition-colors"
          >
            Repo
          </a>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mx-auto max-w-6xl px-6 py-14">
      <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-4">
        <p className="text-muted-foreground max-w-xl text-sm leading-6">
          SafePlate is a hackathon prototype, not a certified food-safety
          device. It is built to refuse rather than to reassure, and a refusal
          always means: ask a human before serving.
        </p>
        <div className="flex gap-6 font-mono text-xs tracking-wider uppercase">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground hover:text-paper transition-colors"
          >
            GitHub
          </a>
          <span className="text-muted-foreground">MIT</span>
        </div>
      </div>
    </footer>
  );
}
