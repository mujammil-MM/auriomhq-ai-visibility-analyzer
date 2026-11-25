import clsx from 'clsx';
import { AlertTriangle, ArrowLeft, Clock3, Loader2, RotateCcw, ShieldCheck } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { Dashboard } from '../components/Dashboard';
import { Card, Eyebrow, Skeleton } from '../components/Primitives';
import { ProgressTimeline } from '../components/ProgressTimeline';
import { ShareDialog } from '../components/ShareDialog';
import { api, ApiError } from '../lib/api';
import { formatDate, prettyUrl } from '../lib/utils';
import type { AuditStatus, ShareResult } from '../lib/types';

const RECENT_KEY = 'auriomhq.recent-audits';
const CACHE_PREFIX = 'auriomhq.audit.';

function cacheAudit(status: AuditStatus) {
  try {
    window.sessionStorage.setItem(CACHE_PREFIX + status.id, JSON.stringify(status));
  } catch {
    /* storage unavailable — polling covers it */
  }
}

function readCachedAudit(id: string): AuditStatus | null {
  try {
    const raw = window.sessionStorage.getItem(CACHE_PREFIX + id);
    return raw ? (JSON.parse(raw) as AuditStatus) : null;
  } catch {
    return null;
  }
}

export function rememberAudit(id: string, url?: string, score?: number) {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    const list: { id: string; url?: string; at: string; score?: number }[] = raw ? JSON.parse(raw) : [];
    const next = [{ id, url, at: new Date().toISOString(), score }, ...list.filter((item) => item.id !== id)].slice(0, 8);
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* localStorage unavailable — history is a convenience only */
  }
}

export function AuditPage() {
  const { auditId = '' } = useParams();
  const location = useLocation();
  const [status, setStatus] = useState<AuditStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [share, setShare] = useState<ShareResult | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [maxPages, setMaxPages] = useState(10);
  const startedAt = useRef<number>(Date.now());
  const pollRef = useRef<number | undefined>(undefined);

  const poll = useCallback(async () => {
    try {
      const data = await api.getAudit(auditId);
      setStatus(data);
      if (data.url) rememberAudit(auditId, data.url, data.report?.scores.overall ?? undefined);
      if (data.status === 'completed' || data.status === 'failed') {
        cacheAudit(data);
        window.clearInterval(pollRef.current);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
        window.clearInterval(pollRef.current);
      } else {
        setError(err instanceof Error ? err.message : 'Could not load the audit.');
      }
    }
  }, [auditId]);

  useEffect(() => {
    api.config().then((config) => setMaxPages(config.maxPages)).catch(() => undefined);
  }, []);

  useEffect(() => {
    startedAt.current = Date.now();
    setError(null);
    setNotFound(false);

    // A serverless deployment returns the finished audit from the POST request.
    // Prefer that result (and the session cache) over a network round-trip that
    // could land on a different instance.
    const handedOver = (location.state as { initial?: AuditStatus } | null)?.initial ?? null;
    const seeded = handedOver ?? readCachedAudit(auditId);
    if (seeded && seeded.report) {
      setStatus(seeded);
      if (seeded.url) rememberAudit(auditId, seeded.url, seeded.report.scores.overall ?? undefined);
      return;
    }

    setStatus(null);
    void poll();
    pollRef.current = window.setInterval(() => void poll(), 1100);
    const ticker = window.setInterval(() => setElapsed(Math.round((Date.now() - startedAt.current) / 1000)), 1000);
    return () => {
      window.clearInterval(pollRef.current);
      window.clearInterval(ticker);
    };
  }, [auditId, poll, location.state]);

  if (notFound) {
    return (
      <div className="mx-auto max-w-xl px-5 py-24 text-center sm:px-8">
        <h1 className="text-2xl font-semibold tracking-[-0.02em]">Audit not found</h1>
        <p className="mt-2 text-sm text-muted">
          This audit ID does not exist on this server. Audits are stored locally in this prototype — if the server
          was reset, run a fresh audit.
        </p>
        <Link to="/" className="btn-primary mt-6">
          <RotateCcw className="h-4 w-4" /> Run a new audit
        </Link>
      </div>
    );
  }

  if (status?.status === 'completed' && status.report) {
    return (
      <>
        <Dashboard
          report={status.report}
          auditId={auditId}
          onShare={() => setShareOpen(true)}
        />
        <ShareDialog
          auditId={auditId}
          open={shareOpen}
          onClose={() => setShareOpen(false)}
          existing={status.share ?? null}
          onShared={(result) => setShare(result)}
        />
        {share?.url ? (
          <div className="fixed bottom-5 left-1/2 z-30 -translate-x-1/2 animate-fadeUp rounded-full border border-line bg-surface px-4 py-2 text-xs text-muted shadow-lift">
            Share link ready — {share.url}
          </div>
        ) : null}
      </>
    );
  }

  if (status?.status === 'failed') {
    return (
      <div className="mx-auto w-full max-w-2xl px-5 py-20 sm:px-8">
        <Card className="p-8">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-failSoft text-fail">
              <AlertTriangle className="h-4 w-4" />
            </span>
            <div>
              <Eyebrow>Audit failed</Eyebrow>
              <h1 className="mt-1 text-lg font-semibold tracking-[-0.02em]">We could not analyse this website</h1>
            </div>
          </div>
          <p className="mt-4 rounded-xl border border-fail/20 bg-failSoft px-4 py-3 text-sm leading-relaxed text-fail">
            {status.error ?? 'The audit did not complete.'}
          </p>
          <ul className="mt-5 space-y-2 text-[13px] leading-relaxed text-muted">
            <li>· The site must be publicly reachable over http or https (private IPs and localhost are blocked).</li>
            <li>· The homepage must return HTML — login walls, JS-only shells and PDFs cannot be audited.</li>
            <li>· Sites that block automated crawlers, or take longer than the timeout, will fail.</li>
          </ul>
          <div className="mt-6 flex flex-wrap gap-2">
            <Link to="/" className="btn-primary">
              <ArrowLeft className="h-4 w-4" /> Try another URL
            </Link>
            <button type="button" onClick={() => window.location.reload()} className="btn-secondary">
              <RotateCcw className="h-4 w-4" /> Retry this audit
            </button>
          </div>
        </Card>
      </div>
    );
  }

  const events = status?.events ?? [];
  const progress = status?.progress ?? 4;

  return (
    <div className="mx-auto w-full max-w-[1080px] px-5 py-12 sm:px-8 sm:py-16">
      <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <Eyebrow>Audit in progress</Eyebrow>
          <h1 className="mt-2 text-[28px] font-semibold leading-tight tracking-[-0.03em] sm:text-[34px]">
            Analysing {status?.url ? prettyUrl(status.url) : 'your website'}
          </h1>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-muted">
            We crawl up to {maxPages} pages, read robots.txt and the sitemap, then score every signal we can
            measure directly from your HTML.
          </p>

          <div className="mt-8">
            {status ? (
              <ProgressTimeline
                events={events}
                progress={progress}
                currentStage={status.stage}
                error={status.error}
              />
            ) : (
              <div className="space-y-4">
                <Skeleton className="h-2 w-full" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-3/5" />
              </div>
            )}
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-4 text-[11px] text-faint">
            <span className="inline-flex items-center gap-1.5">
              <Clock3 className="h-3.5 w-3.5" /> {elapsed}s elapsed
            </span>
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5" /> Public pages only
            </span>
            {status?.createdAt ? <span>Started {formatDate(status.createdAt)}</span> : null}
          </div>
        </div>

        <Card className="h-fit p-6">
          <Eyebrow>What is happening</Eyebrow>
          <ul className="mt-4 space-y-4">
            {[
              { title: 'Safety checks', text: 'The URL is validated, DNS is resolved once, and every IP must be public. Redirects are re-validated at each hop.' },
              { title: 'robots.txt & sitemap', text: 'Crawl rules are respected, including AI crawler directives. Sitemaps are read for page discovery.' },
              { title: 'Page analysis', text: 'Titles, meta, headings, links, images, JSON-LD, text structure and answer patterns.' },
              { title: 'Scoring', text: 'Each check returns pass, warning, fail or not-tested with the evidence that produced it.' },
            ].map((item) => (
              <li key={item.title} className="flex gap-3">
                <Loader2 className={clsx('mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-faint')} />
                <div>
                  <p className="text-[13px] font-medium text-ink">{item.title}</p>
                  <p className="mt-0.5 text-[12px] leading-relaxed text-muted">{item.text}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-6 border-t border-line pt-4 text-[11px] leading-relaxed text-faint">
            You can leave this page — the audit continues on the server. Keep the URL if you want to come back.
          </p>
        </Card>
      </div>
    </div>
  );
}
