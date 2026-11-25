import clsx from 'clsx';
import { AlertTriangle, ChevronDown, ExternalLink, FileText, Link2 } from 'lucide-react';
import { useState } from 'react';
import { prettyUrl } from '../lib/utils';
import type { CrawlInfo, PageInfo } from '../lib/types';

export function PagesTable({ crawl }: { crawl: CrawlInfo }) {
  const [openUrl, setOpenUrl] = useState<string | null>(null);

  return (
    <div className="space-y-8">
      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <div className="hidden grid-cols-[minmax(0,2.4fr)_56px_56px_minmax(0,1.1fr)_16px] items-center gap-3 border-b border-line bg-mist/60 px-4 py-2.5 sm:grid">
          {['Page', 'Status', 'Words', 'Structured data', ''].map((label, index) => (
            <span key={index} className="label">
              {label}
            </span>
          ))}
        </div>
        {crawl.pages.map((page) => (
          <PageRow
            key={page.url}
            page={page}
            open={openUrl === page.url}
            onToggle={() => setOpenUrl((current) => (current === page.url ? null : page.url))}
          />
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-line bg-surface p-5">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-muted" />
            <h4 className="text-sm font-medium">robots.txt</h4>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">
            {crawl.robots.available
              ? `Found at ${crawl.robots.url}. ${crawl.robots.blockedPaths.length} disallow rule(s).`
              : `Not found (HTTP ${crawl.robots.status ?? '—'}). Crawling is allowed by default.`}
          </p>
          {crawl.robots.blockedPaths.length > 0 ? (
            <ul className="mt-3 space-y-1">
              {crawl.robots.blockedPaths.slice(0, 5).map((path) => (
                <li key={path} className="font-mono text-[11px] text-muted">
                  Disallow: {path}
                </li>
              ))}
            </ul>
          ) : null}
          {crawl.robots.available ? (
            <div className="mt-4 border-t border-line pt-3">
              <p className="label mb-2">AI crawler access</p>
              <ul className="grid grid-cols-2 gap-1.5">
                {Object.entries(crawl.robots.aiAccess).slice(0, 12).map(([bot, info]) => (
                  <li key={bot} className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="truncate text-muted">{bot}</span>
                    <span className={info.allowed ? 'text-pass' : 'text-fail'}>
                      {info.allowed ? 'allowed' : 'blocked'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-line bg-surface p-5">
          <div className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-muted" />
            <h4 className="text-sm font-medium">Sitemap &amp; llms.txt</h4>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">
            {crawl.sitemap.available
              ? `Sitemap at ${prettyUrl(crawl.sitemap.url)} lists ${crawl.sitemap.urlCount} URLs${
                  crawl.sitemap.sitemapCount ? ` across ${crawl.sitemap.sitemapCount} child sitemaps` : ''
                }.`
              : 'No readable XML sitemap was found.'}
          </p>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">
            {crawl.llmsTxt.available
              ? `llms.txt published at ${prettyUrl(crawl.llmsTxt.url)}.`
              : `No llms.txt found (HTTP ${crawl.llmsTxt.status ?? '—'}).`}
          </p>
          {crawl.brokenLinks.length > 0 ? (
            <div className="mt-4 border-t border-line pt-3">
              <p className="label mb-2">Broken / unreachable links</p>
              <ul className="space-y-1.5">
                {crawl.brokenLinks.slice(0, 6).map((link) => (
                  <li key={link.url} className="text-[11px] text-muted">
                    <span className="font-mono text-fail">{link.status ?? 'ERR'}</span>{' '}
                    <span className="font-mono">{prettyUrl(link.url)}</span>
                    <span className="text-faint"> · found on {prettyUrl(link.found_on)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-4 border-t border-line pt-3 text-[13px] text-pass">
              No broken internal links detected.
            </p>
          )}
          {crawl.inaccessiblePages.length > 0 ? (
            <div className="mt-3">
              <p className="label mb-1">Inaccessible</p>
              <ul className="space-y-1">
                {crawl.inaccessiblePages.slice(0, 4).map((page) => (
                  <li key={page.url} className="text-[11px] text-muted">
                    <AlertTriangle className="mr-1 inline h-3 w-3 text-warn" />
                    {prettyUrl(page.url)} — {page.error}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function PageRow({ page, open, onToggle }: { page: PageInfo; open: boolean; onToggle: () => void }) {
  const missingAlt = page.imagesTotal - page.imagesMissingAlt;
  return (
    <div className={clsx('border-b border-line last:border-b-0', open && 'bg-mist/40')}>
      <button
        type="button"
        onClick={onToggle}
        className="grid w-full grid-cols-[minmax(0,1fr)_16px] items-center gap-3 px-4 py-3 text-left sm:grid-cols-[minmax(0,2.4fr)_56px_56px_minmax(0,1.1fr)_16px]"
      >
        <span className="min-w-0">
          <span className="block truncate font-mono text-[12.5px] text-ink">{prettyUrl(page.url)}</span>
          <span className="mt-0.5 block truncate text-xs text-muted">{page.title || 'No title tag'}</span>
        </span>
        <span className="hidden sm:block">
          <span className={clsx('font-mono text-xs', page.status && page.status < 400 ? 'text-pass' : 'text-fail')}>
            {page.status ?? 'ERR'}
          </span>
        </span>
        <span className="hidden font-mono text-xs text-muted sm:block">{page.wordCount}</span>
        <span className="hidden min-w-0 sm:block">
          {page.schemaTypes.length ? (
            <span className="block truncate font-mono text-[11px] text-muted">
              {page.schemaTypes.filter(Boolean).slice(0, 2).join(', ')}
            </span>
          ) : (
            <span className="font-mono text-[11px] text-fail">none detected</span>
          )}
        </span>
        <ChevronDown
          className={clsx('h-4 w-4 shrink-0 text-faint transition-transform duration-300', open && 'rotate-180')}
        />
      </button>

      {open ? (
        <div className="animate-fadeIn px-4 pb-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="H1 headings" value={`${page.h1.length}`} detail={page.h1[0] ?? 'none'} />
            <Stat label="H2 sections" value={`${page.h2.length}`} />
            <Stat label="Internal links" value={`${page.internalLinks}`} detail={`${page.externalLinks} external`} />
            <Stat
              label="Images with alt"
              value={`${missingAlt}/${page.imagesTotal}`}
              detail={page.imagesMissingAlt ? `${page.imagesMissingAlt} missing` : 'all labelled'}
            />
            <Stat label="Question headings" value={`${page.questionHeadings.length}`} />
            <Stat label="List items" value={`${page.listItems}`} />
            <Stat label="Text / HTML ratio" value={`${Math.round(page.textHtmlRatio * 100)}%`} />
            <Stat label="Language / viewport" value={page.lang || '—'} detail={page.viewport ? 'responsive' : 'missing'} />
          </div>

          <div className="mt-4 space-y-2 text-[12px] text-muted">
            {page.metaDescription ? (
              <p>
                <span className="label mr-2">Meta description</span>
                {page.metaDescription}
              </p>
            ) : (
              <p className="text-fail">No meta description.</p>
            )}
            {page.canonical ? (
              <p>
                <span className="label mr-2">Canonical</span>
                <span className="font-mono text-[11px]">{page.canonical}</span>
              </p>
            ) : (
              <p className="text-fail">No canonical URL.</p>
            )}
            {page.redirectChain.length ? (
              <p>
                <span className="label mr-2">Redirects</span>
                {[...page.redirectChain, page.finalUrl].join(' → ')}
              </p>
            ) : null}
            {page.schemaTypes.length ? (
              <p>
                <span className="label mr-2">Schema</span>
                {page.schemaTypes.join(', ')}
              </p>
            ) : null}
            {page.schemaErrors.length ? (
              <p className="text-warn">Schema errors: {page.schemaErrors.join('; ')}</p>
            ) : null}
            {page.author ? (
              <p>
                <span className="label mr-2">Author</span>
                {page.author}
              </p>
            ) : null}
            <a
              href={page.url}
              target="_blank"
              rel="noreferrer nofollow"
              className="inline-flex items-center gap-1 text-[11px] text-muted underline decoration-lineStrong underline-offset-2 hover:text-ink"
            >
              View page <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div>
      <p className="label">{label}</p>
      <p className="mt-0.5 font-mono text-sm text-ink">{value}</p>
      {detail ? <p className="mt-0.5 truncate text-[11px] text-faint">{detail}</p> : null}
    </div>
  );
}
