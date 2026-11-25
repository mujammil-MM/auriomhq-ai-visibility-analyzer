import clsx from 'clsx';
import { ArrowUpRight, Menu, X } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="group inline-flex items-center gap-2.5" aria-label="AuriomHQ AI Visibility Analyzer home">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-paper transition-transform duration-300 ease-smooth group-hover:-translate-y-0.5">
        <svg viewBox="0 0 32 32" className="h-4 w-4" aria-hidden="true">
          <path d="M16 5.5 25 26h-4.6l-1.7-3.9h-5.4L11.6 26H7L16 5.5Zm0 6.6-1.8 4.7h3.6L16 12.1Z" fill="currentColor" />
        </svg>
      </span>
      <span className="leading-none">
        <span className="block text-[15px] font-semibold tracking-[-0.02em]">AuriomHQ</span>
        {!compact ? (
          <span className="mt-0.5 block font-mono text-[9px] uppercase tracking-[0.18em] text-faint">
            AI Visibility Analyzer
          </span>
        ) : null}
      </span>
    </Link>
  );
}

const NAV_LINKS = [
  { to: '/', label: 'Analyzer' },
  { to: '/methodology', label: 'Methodology' },
];

export function Layout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-line/80 bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 w-full max-w-[1180px] items-center justify-between px-5 sm:px-8">
          <Logo />
          <nav className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                className={({ isActive }) =>
                  clsx(
                    'rounded-lg px-3 py-2 text-sm transition-colors duration-200',
                    isActive ? 'text-ink' : 'text-muted hover:text-ink',
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
            <a
              href="https://auriomhq.work"
              target="_blank"
              rel="noreferrer"
              className="ml-1 inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:text-ink"
            >
              AuriomHQ
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
            <Link to="/#audit" className="btn-primary ml-2 h-9 px-4 text-xs">
              Analyse my website
            </Link>
          </nav>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="btn-ghost h-9 w-9 p-0 md:hidden"
            aria-label="Toggle navigation"
            aria-expanded={open}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {open ? (
          <div className="border-t border-line bg-paper px-5 pb-4 pt-2 md:hidden">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                className="block rounded-lg px-3 py-2.5 text-sm text-muted hover:bg-mist hover:text-ink"
              >
                {link.label}
              </NavLink>
            ))}
            <a
              href="https://auriomhq.work"
              target="_blank"
              rel="noreferrer"
              className="block rounded-lg px-3 py-2.5 text-sm text-muted hover:bg-mist hover:text-ink"
            >
              auriomhq.work ↗
            </a>
            <Link to="/#audit" className="btn-primary mt-2 w-full">
              Analyse my website
            </Link>
          </div>
        ) : null}
      </header>

      <main className="flex-1">{children}</main>

      <footer className="mt-24 border-t border-line bg-[#F6F4EE]">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-14 sm:px-8">
          <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr]">
            <div>
              <Logo />
              <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
                Make your website visible everywhere people search. SEO, AEO and GEO auditing by AuriomHQ.
              </p>
            </div>
            <div>
              <div className="label mb-3">Product</div>
              <ul className="space-y-2 text-sm text-muted">
                <li><Link to="/" className="link-underline">Visibility analyzer</Link></li>
                <li><Link to="/methodology" className="link-underline">Scoring methodology</Link></li>
                <li><Link to="/#audit" className="link-underline">Run an audit</Link></li>
              </ul>
            </div>
            <div>
              <div className="label mb-3">AuriomHQ</div>
              <ul className="space-y-2 text-sm text-muted">
                <li>
                  <a href="https://auriomhq.work" target="_blank" rel="noreferrer" className="link-underline">
                    auriomhq.work
                  </a>
                </li>
                <li>
                  <a href="https://auriomhq.work/contact" target="_blank" rel="noreferrer" className="link-underline">
                    Talk to us
                  </a>
                </li>
                <li>
                  <a href="https://auriomhq.work/services/aeo-geo" target="_blank" rel="noreferrer" className="link-underline">
                    AEO &amp; GEO services
                  </a>
                </li>
              </ul>
            </div>
          </div>
          <div className="mt-12 flex flex-col gap-3 border-t border-line pt-6 text-xs text-faint sm:flex-row sm:items-center sm:justify-between">
            <p>© {new Date().getFullYear()} AuriomHQ. All rights reserved.</p>
            <p className="max-w-xl sm:text-right">
              Scores describe measurable on-page readiness. They are not search rankings, traffic figures or
              observed AI citations.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
