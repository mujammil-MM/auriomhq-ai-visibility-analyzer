import clsx from 'clsx';
import {
  ChevronRight, Download, ExternalLink, Info, Link2, Plus, Share2, Sparkles,
} from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CategoryBreakdown, CheckCounts, PillarComparison, SeverityDistribution } from './Charts';
import { CheckList } from './CheckList';
import { Card, EmptyState, Eyebrow, SectionHeading, SeverityTag, StatusChip } from './Primitives';
import { PagesTable } from './PagesTable';
import { AiBadge, Drafts, Roadmap } from './Recommendations';
import { ScoreBar, ScoreRing } from './ScoreRing';
import { LeadForm } from './LeadForm';
import { PILLAR_META, formatDate, hostOf, scoreColor, scoreLabel } from '../lib/utils';
import type { Pillar, Report } from '../lib/types';

type TabKey = 'overview' | 'seo' | 'aeo' | 'geo' | 'recommendations' | 'pages';

const TABS: { key: TabKey; label: string; count?: (report: Report) => number }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'seo', label: 'SEO', count: (report) => report.scores.pillars.seo.failed + report.scores.pillars.seo.warnings },
  { key: 'aeo', label: 'AEO', count: (report) => report.scores.pillars.aeo.failed + report.scores.pillars.aeo.warnings },
  { key: 'geo', label: 'GEO', count: (report) => report.scores.pillars.geo.failed + report.scores.pillars.geo.warnings },
  {
    key: 'recommendations',
    label: 'Recommendations',
    count: (report) => report.recommendations.roadmap.reduce((sum, phase) => sum + phase.itemCount, 0),
  },
  { key: 'pages', label: 'Crawled pages', count: (report) => report.crawl.pagesAnalysed },
];

export function Dashboard({
  report,
  auditId,
  onShare,
  sharedView = false,
}: {
  report: Report;
  auditId?: string;
  onShare?: () => void;
  sharedView?: boolean;
}) {
  const [tab, setTab] = useState<TabKey>('overview');
  const [showMethod, setShowMethod] = useState(false);
  const scores = report.scores;
  const overall = scores.overall;

  return (
    <div className="mx-auto w-full max-w-[1180px] px-5 pb-20 sm:px-8">
      {/* header */}
      <div className="flex flex-wrap items-start justify-between gap-4 pt-10">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Eyebrow>{sharedView ? 'Shared report' : 'Audit complete'}</Eyebrow>
            {report.summary?.aiEnhanced ? (
              <span className="chip border-accent/25 bg-accentSoft text-accent">
                <Sparkles className="h-3 w-3" /> AI-enhanced
              </span>
            ) : null}
          </div>
          <h1 className="mt-2 truncate text-[26px] font-semibold tracking-[-0.03em] sm:text-[32px]">
            {hostOf(report.site.url)}
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-muted">
            <a
              href={report.site.url}
              target="_blank"
              rel="noreferrer nofollow"
              className="inline-flex items-center gap-1 font-mono text-[12.5px] text-muted underline decoration-lineStrong underline-offset-4 hover:text-ink"
            >
              {report.site.url}
              <ExternalLink className="h-3 w-3" />
            </a>
            <span className="text-faint">·</span>
            <span>Audited {formatDate(report.generatedAt)}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {auditId ? (
            <a href={`/api/audits/${auditId}/pdf`} className="btn-secondary h-9 px-3 text-xs">
              <Download className="h-3.5 w-3.5" /> PDF report
            </a>
          ) : null}
          {onShare && !sharedView ? (
            <button type="button" onClick={onShare} className="btn-secondary h-9 px-3 text-xs">
              <Share2 className="h-3.5 w-3.5" /> Share
            </button>
          ) : null}
          {!sharedView ? (
            <Link to="/" className="btn-primary h-9 px-3 text-xs">
              <Plus className="h-3.5 w-3.5" /> New audit
            </Link>
          ) : (
            <Link to="/" className="btn-primary h-9 px-3 text-xs">
              Run your own audit <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          )}
        </div>
      </div>

      {/* score hero */}
      <Card className="mt-6 overflow-hidden">
        <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[260px_1fr]">
          <div className="flex flex-col items-center justify-center gap-3 border-line lg:border-r lg:pr-8">
            <ScoreRing score={overall} size={168} thickness={11} label="Overall score" />
            <div className="text-center">
              <p className="text-sm font-medium" style={{ color: scoreColor(overall) }}>
                {scoreLabel(overall)}
              </p>
              <p className="mt-0.5 text-[11px] text-faint">
                {report.crawl.pagesAnalysed} page{report.crawl.pagesAnalysed === 1 ? '' : 's'} ·{' '}
                {scores.counts.total} checks
              </p>
            </div>
          </div>

          <div>
            <div className="grid gap-4 sm:grid-cols-3">
              {(['seo', 'aeo', 'geo'] as Pillar[]).map((pillar) => {
                const data = scores.pillars[pillar];
                return (
                  <button
                    key={pillar}
                    type="button"
                    onClick={() => setTab(pillar)}
                    className="group rounded-xl border border-line bg-surface p-4 text-left transition-all duration-300 hover:border-lineStrong hover:shadow-card"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-mono text-2xs uppercase tracking-[0.14em] text-faint">{data.label}</p>
                        <p className="mt-1 text-[11px] text-muted">{PILLAR_META[pillar].name}</p>
                      </div>
                      <span className="text-2xl font-semibold tracking-[-0.03em]" style={{ color: scoreColor(data.score) }}>
                        {data.score ?? '—'}
                      </span>
                    </div>
                    <ScoreBar score={data.score} className="mt-3" height={4} />
                    <p className="mt-2.5 text-[11px] text-faint">
                      {data.passed} passed · {data.warnings} warned · {data.failed} failed
                    </p>
                    <span className="mt-2 inline-flex items-center gap-1 text-[11px] text-muted opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                      View checks <ChevronRight className="h-3 w-3" />
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="mt-5">
              <CheckCounts scores={scores} />
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-muted">
              <span className="inline-flex items-center gap-1.5">
                HTTPS: <span className={report.site.httpsAvailable ? 'text-pass' : 'text-fail'}>
                  {report.site.httpsAvailable ? 'yes' : 'no'}
                </span>
              </span>
              <span>Homepage: HTTP {report.site.homepageStatus ?? '—'}</span>
              <span>robots.txt: {report.crawl.robots.available ? 'found' : 'missing'}</span>
              <span>Sitemap: {report.crawl.sitemap.available ? `${report.crawl.sitemap.urlCount} URLs` : 'missing'}</span>
              <span>Crawl: {(report.crawl.durationMs / 1000).toFixed(1)}s</span>
              <button
                type="button"
                onClick={() => setShowMethod((value) => !value)}
                className="inline-flex items-center gap-1 text-ink underline decoration-lineStrong underline-offset-4 hover:decoration-ink"
              >
                <Info className="h-3 w-3" /> How this is scored
              </button>
            </div>
          </div>
        </div>

        {showMethod ? (
          <div className="animate-fadeIn border-t border-line bg-mist/40 px-6 py-5 sm:px-8">
            <p className="label mb-2">Score calculation</p>
            <ul className="space-y-1.5">
              {scores.explanation.map((line) => (
                <li key={line} className="text-[13px] leading-relaxed text-muted">
                  · {line}
                </li>
              ))}
            </ul>
            <Link to="/methodology" className="mt-3 inline-flex items-center gap-1 text-xs text-ink underline decoration-lineStrong underline-offset-4">
              Full methodology <ExternalLink className="h-3 w-3" />
            </Link>
          </div>
        ) : null}
      </Card>

      {/* tabs */}
      <div className="sticky top-16 z-20 -mx-5 mt-8 border-b border-line bg-paper/95 px-5 backdrop-blur sm:-mx-8 sm:px-8">
        <div className="scrollbar-thin flex gap-1 overflow-x-auto">
          {TABS.map((item) => {
            const count = item.count?.(report);
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                className={clsx(
                  'relative whitespace-nowrap px-3 py-3 text-sm transition-colors duration-200',
                  tab === item.key ? 'text-ink' : 'text-muted hover:text-ink',
                )}
              >
                {item.label}
                {count ? (
                  <span className="ml-1.5 font-mono text-[10px] text-faint">{count}</span>
                ) : null}
                {tab === item.key ? (
                  <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-ink" />
                ) : null}
              </button>
            );
          })}
        </div>
      </div>

      <div key={tab} className="animate-fadeUp pt-8">
        {tab === 'overview' ? <OverviewTab report={report} onJump={(pillar) => setTab(pillar)} /> : null}
        {tab === 'seo' || tab === 'aeo' || tab === 'geo' ? (
          <PillarTab report={report} pillar={tab} />
        ) : null}
        {tab === 'recommendations' ? (
          <div className="space-y-10">
            <Roadmap data={report.recommendations} />
            <div className="hairline pt-8">
              <SectionHeading
                eyebrow="Drafts"
                title="Content improvements generated from your evidence"
                description="These are drafts assembled from the text, headings and schema found during the crawl. Review before publishing."
                className="mb-6"
              />
              <Drafts data={report.recommendations} />
            </div>
            {report.recommendations.untested.length ? (
              <div className="rounded-xl border border-line bg-mist/40 p-4">
                <p className="label mb-2">Not tested ({report.recommendations.untested.length})</p>
                <p className="text-[13px] leading-relaxed text-muted">
                  These checks could not be performed on this site and were excluded from the score rather than
                  marked as passed: {report.recommendations.untested.join(', ')}.
                </p>
              </div>
            ) : null}
          </div>
        ) : null}
        {tab === 'pages' ? (
          <div className="space-y-8">
            <PagesTable crawl={report.crawl} />
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-line bg-surface p-5">
                <p className="label mb-2">Scope &amp; limitations</p>
                <ul className="space-y-1.5">
                  {report.limitations.map((limitation) => (
                    <li key={limitation} className="text-[12.5px] leading-relaxed text-muted">
                      · {limitation}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-xl border border-line bg-surface p-5">
                <p className="label mb-2">Crawl notes</p>
                {report.crawl.notes.length ? (
                  <ul className="space-y-1.5">
                    {report.crawl.notes.map((note) => (
                      <li key={note} className="text-[12.5px] leading-relaxed text-muted">
                        · {note}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[12.5px] leading-relaxed text-muted">
                    All {report.crawl.pagesAnalysed} discovered pages were crawled without restrictions.
                  </p>
                )}
                {report.crawl.inaccessiblePages.length ? (
                  <>
                    <p className="label mb-2 mt-4">Inaccessible pages</p>
                    <ul className="space-y-1">
                      {report.crawl.inaccessiblePages.map((page) => (
                        <li key={page.url} className="text-[12px] text-muted">
                          <span className="font-mono">{page.url}</span> — {page.error}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* CTA */}
      {!sharedView ? (
        <div className="mt-16 overflow-hidden rounded-2xl border border-line bg-[#F6F4EE]">
          <div className="grid gap-8 p-6 sm:p-9 lg:grid-cols-[1fr_1.1fr]">
            <div>
              <Eyebrow>Next step</Eyebrow>
              <h2 className="mt-2 text-[24px] font-semibold leading-tight tracking-[-0.03em] sm:text-[28px]">
                Your website has opportunities to improve its search and AI visibility.
              </h2>
              <p className="mt-3 max-w-md text-sm leading-relaxed text-muted">
                {scores.counts.fail + scores.counts.warning > 0
                  ? `This audit found ${scores.counts.fail} failure${scores.counts.fail === 1 ? '' : 's'} and ${scores.counts.warning} warning${scores.counts.warning === 1 ? '' : 's'}. AuriomHQ implements these fixes — schema, entity setup, answer-focused content, crawler access and technical corrections.`
                  : 'AuriomHQ can review the remaining opportunities and build on this baseline with a professional implementation plan.'}
              </p>
              <ul className="mt-6 space-y-2.5 border-t border-lineStrong/60 pt-5 text-[12.5px] text-muted">
                {[
                  'Fixes implemented in priority order — schema, entity data, metadata',
                  'Answer-focused content written from your real services and FAQs',
                  'Crawler access, technical SEO and verification re-checked after launch',
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-lineStrong" />
                    {item}
                  </li>
                ))}
              </ul>
              <p className="mt-5 inline-flex items-center gap-2 text-[12px] text-muted">
                <Link2 className="h-3.5 w-3.5" /> AuriomHQ · AI growth partner
                <span className="text-faint">·</span>
                <a href="https://auriomhq.work/contact" target="_blank" rel="noreferrer" className="link-underline">
                  auriomhq.work/contact
                </a>
              </p>
            </div>
            <div className="rounded-xl border border-line bg-surface p-5 sm:p-6">
              <LeadForm auditId={auditId} website={report.site.url} source="report" />
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-16 rounded-2xl border border-line bg-[#F6F4EE] p-6 sm:p-9">
          <Eyebrow>AuriomHQ</Eyebrow>
          <h2 className="mt-2 max-w-xl text-[22px] font-semibold leading-tight tracking-[-0.03em] sm:text-[26px]">
            Want the same audit — with implementation — for your business?
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
            Run a free audit of your own website, or talk to AuriomHQ about a professional SEO, AEO and GEO
            implementation.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to="/" className="btn-primary">
              Analyse my website
            </Link>
            <a href="https://auriomhq.work/contact" target="_blank" rel="noreferrer" className="btn-secondary">
              Contact AuriomHQ
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

function OverviewTab({ report, onJump }: { report: Report; onJump: (pillar: Pillar) => void }) {
  const summary = report.summary;
  const critical = report.criticalFindings ?? [];
  const allChecks = report.checks ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[1.55fr_1fr]">
      <div className="space-y-6">
        <Card className="p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Eyebrow>Executive summary</Eyebrow>
              <h2 className="mt-1.5 text-lg font-semibold tracking-[-0.02em]">What this audit found</h2>
            </div>
            <AiBadge enhanced={Boolean(summary?.aiEnhanced)} />
          </div>
          <p className="mt-4 text-[14px] leading-[1.75] text-muted">{summary?.executiveSummary}</p>
          {summary?.disclaimer ? (
            <p className="mt-3 text-[11px] text-faint">{summary.disclaimer}</p>
          ) : null}

          {summary?.keyFindings?.length ? (
            <div className="mt-6 space-y-3 border-t border-line pt-5">
              {summary.keyFindings.map((finding) => (
                <div key={finding.title} className="flex gap-3">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ink" />
                  <div>
                    <p className="text-sm font-medium text-ink">{finding.title}</p>
                    <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{finding.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between">
            <Eyebrow>Priority findings</Eyebrow>
            {critical.length > 0 ? (
              <span className="font-mono text-2xs uppercase tracking-[0.14em] text-faint">
                Top {Math.min(5, critical.length)}
              </span>
            ) : null}
          </div>
          {critical.length === 0 ? (
            <p className="mt-3 text-sm text-muted">
              No critical or high-severity failures were detected. Review the warnings in each pillar tab.
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-line">
              {critical.slice(0, 5).map((check) => (
                <li key={check.id} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusChip status={check.status} />
                    <span className="text-sm font-medium text-ink">{check.title}</span>
                    <SeverityTag severity={check.severity} />
                  </div>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{check.evidence}</p>
                  <button
                    type="button"
                    onClick={() => onJump(check.pillar)}
                    className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-ink underline decoration-lineStrong underline-offset-4 hover:decoration-ink"
                  >
                    Open {PILLAR_META[check.pillar].label} checks <ChevronRight className="h-3 w-3" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-6">
          <Eyebrow>Weakest categories</Eyebrow>
          <div className="mt-3">
            <CategoryBreakdown
              categories={[...report.scores.categories]
                .filter((category) => category.score !== null)
                .sort((a, b) => (a.score ?? 100) - (b.score ?? 100))
                .slice(0, 6)}
            />
          </div>
        </Card>
      </div>

      <div className="space-y-6">
        <Card className="p-6">
          <Eyebrow>Issue distribution</Eyebrow>
          <div className="mt-4">
            <SeverityDistribution checks={allChecks} />
          </div>
        </Card>

        <Card className="p-6">
          <Eyebrow>Pillars</Eyebrow>
          <div className="mt-4">
            <PillarComparison scores={report.scores} />
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between">
            <Eyebrow>Quick wins</Eyebrow>
            <span className="font-mono text-2xs uppercase tracking-[0.14em] text-faint">
              {report.recommendations.quickWins.length}
            </span>
          </div>
          {report.recommendations.quickWins.length === 0 ? (
            <p className="mt-3 text-sm text-muted">No low-effort, high-impact items were detected.</p>
          ) : (
            <ul className="mt-3 space-y-2.5">
              {report.recommendations.quickWins.map((item) => (
                <li key={item.id} className="flex items-start gap-2">
                  <ChevronRight className="mt-1 h-3 w-3 shrink-0 text-accent" />
                  <div>
                    <p className="text-[13px] leading-snug text-ink">{item.title}</p>
                    <p className="text-[11px] text-faint">
                      {item.impact} impact · {item.difficulty}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {summary?.priorityActions?.length ? (
          <Card className="p-6">
            <Eyebrow>Recommended next actions</Eyebrow>
            <ol className="mt-3 space-y-3">
              {summary.priorityActions.map((action, index) => (
                <li key={`${action.title}-${index}`} className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-line font-mono text-[10px] text-muted">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-[13px] font-medium text-ink">{action.title}</p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-muted">{action.detail}</p>
                    {action.effort ? (
                      <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
                        Effort: {action.effort}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function PillarTab({ report, pillar }: { report: Report; pillar: Pillar }) {
  const checks = report.checksByPillar[pillar];
  const data = report.scores.pillars[pillar];
  const meta = PILLAR_META[pillar];

  if (!checks?.length) {
    return <EmptyState title="No checks available" description="This pillar could not be analysed for this site." />;
  }

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-6">
          <ScoreRing score={data.score} size={96} thickness={7} animate={false} />
          <div className="min-w-0 flex-1">
            <Eyebrow>{meta.label}</Eyebrow>
            <h2 className="mt-1 text-lg font-semibold tracking-[-0.02em]">{meta.name}</h2>
            <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-muted">{meta.blurb}</p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-faint">
              <span>{data.tested} of {data.checksTotal} checks tested</span>
              <span className="text-pass">{data.passed} passed</span>
              <span className="text-warn">{data.warnings} warnings</span>
              <span className="text-fail">{data.failed} failed</span>
              {data.notTested ? <span>{data.notTested} not tested</span> : null}
              <span>
                {data.earned.toFixed(1)} / {data.available.toFixed(0)} points
              </span>
            </div>
          </div>
        </div>
        <div className="mt-6 border-t border-line pt-4">
          <p className="label mb-2">Category performance</p>
          <CategoryBreakdown categories={report.scores.categories} pillar={pillar} />
        </div>
      </Card>

      <CheckList checks={checks} />
    </div>
  );
}
