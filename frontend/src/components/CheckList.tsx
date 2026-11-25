import clsx from 'clsx';
import { ChevronDown, ExternalLink } from 'lucide-react';
import { useMemo, useState } from 'react';
import { SeverityTag, StatusChip } from './Primitives';
import { prettyUrl, SEVERITY_META, STATUS_META } from '../lib/utils';
import type { Check, Status } from '../lib/types';

type Filter = 'all' | Status;

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'fail', label: 'Failures' },
  { key: 'warning', label: 'Warnings' },
  { key: 'pass', label: 'Passed' },
  { key: 'not_tested', label: 'Not tested' },
];

export function CheckList({ checks }: { checks: Check[] }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [openId, setOpenId] = useState<string | null>(checks.find((c) => c.status === 'fail')?.id ?? null);

  const counts = useMemo(() => {
    const map: Record<string, number> = { all: checks.length };
    for (const check of checks) map[check.status] = (map[check.status] ?? 0) + 1;
    return map;
  }, [checks]);

  const visible = filter === 'all' ? checks : checks.filter((check) => check.status === filter);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setFilter(item.key)}
            className={clsx(
              'rounded-full border px-3 py-1.5 text-xs transition-colors duration-200',
              filter === item.key
                ? 'border-ink bg-ink text-paper'
                : 'border-line bg-surface text-muted hover:border-lineStrong hover:text-ink',
            )}
          >
            {item.label}
            <span className={clsx('ml-1.5 font-mono text-[10px]', filter === item.key ? 'text-paper/60' : 'text-faint')}>
              {counts[item.key] ?? 0}
            </span>
          </button>
        ))}
      </div>

      <div className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {visible.map((check) => (
          <CheckRow
            key={check.id}
            check={check}
            open={openId === check.id}
            onToggle={() => setOpenId((current) => (current === check.id ? null : check.id))}
          />
        ))}
        {visible.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted">No checks in this state.</p>
        ) : null}
      </div>
    </div>
  );
}

function CheckRow({ check, open, onToggle }: { check: Check; open: boolean; onToggle: () => void }) {
  return (
    <div className={clsx('transition-colors duration-200', open && 'bg-mist/40')}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-4 py-3.5 text-left"
      >
        <span className={clsx('mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full', STATUS_META[check.status].dot)} />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <span className="text-sm font-medium text-ink">{check.title}</span>
            <SeverityTag severity={check.severity} />
            <span className="font-mono text-[10px] text-faint">{check.weight} pts</span>
          </span>
          <span className="mt-1 block truncate text-xs text-muted">{check.evidence}</span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <StatusChip status={check.status} className="hidden sm:inline-flex" />
          <ChevronDown
            className={clsx('h-4 w-4 text-faint transition-transform duration-300', open && 'rotate-180')}
          />
        </span>
      </button>

      {open ? (
        <div className="animate-fadeIn px-4 pb-5 pl-[26px]">
          <div className="grid gap-5 lg:grid-cols-2">
            <Detail title="What we found" body={check.evidence} mono={false} />
            <Detail title="Why it matters" body={check.why} mono={false} />
            <Detail title="How to fix it" body={check.fix} mono={false} />
            <Detail title="Example implementation" body={check.example} mono />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line pt-3 text-[11px] text-faint">
            <span>
              Category: <span className="text-muted">{check.category}</span>
            </span>
            <span>
              Status: <span className="text-muted">{check.statusLabel}</span>
            </span>
            <span>
              Score impact:{' '}
              <span className="text-muted">
                {check.status === 'not_tested'
                  ? 'excluded'
                  : `${check.earned.toFixed(1)} / ${check.weight} pts`}
              </span>
            </span>
            <span>
              Fix priority: <span className="text-muted">P{check.priority}</span>
            </span>
            {check.pages.length > 0 ? (
              <span className="inline-flex flex-wrap items-center gap-1">
                Affects:
                {check.pages.slice(0, 3).map((page) => (
                  <a
                    key={page}
                    href={page}
                    target="_blank"
                    rel="noreferrer nofollow"
                    className="inline-flex items-center gap-1 text-muted underline decoration-lineStrong underline-offset-2 hover:text-ink"
                  >
                    {prettyUrl(page)}
                    <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                ))}
                {check.pages.length > 3 ? <span>+{check.pages.length - 3}</span> : null}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Detail({ title, body, mono }: { title: string; body: string; mono: boolean }) {
  return (
    <div>
      <p className="label mb-1.5">{title}</p>
      {mono ? (
        <pre className="scrollbar-thin overflow-x-auto rounded-lg border border-line bg-[#FBFAF6] p-3 font-mono text-[11.5px] leading-relaxed text-[#3F3C35]">
          <code>{body}</code>
        </pre>
      ) : (
        <p className="text-[13.5px] leading-relaxed text-muted">{body}</p>
      )}
    </div>
  );
}

export function SeverityLegend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-faint">
      {(['critical', 'high', 'medium', 'low', 'informational'] as const).map((severity) => (
        <span key={severity} className="inline-flex items-center gap-1.5">
          <span className={clsx('h-1.5 w-1.5 rounded-full', SEVERITY_META[severity].className.replace('text-', 'bg-'))} />
          <span className="capitalize">{severity}</span>
        </span>
      ))}
    </div>
  );
}
