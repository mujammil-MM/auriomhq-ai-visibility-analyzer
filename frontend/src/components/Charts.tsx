import clsx from 'clsx';
import { ScoreBar } from './ScoreRing';
import { PILLAR_META, scoreColor } from '../lib/utils';
import type { CategoryScore, Check, Scores } from '../lib/types';

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#B91C1C',
  high: '#C2410C',
  medium: '#B45309',
  low: '#9A968C',
  informational: '#C9C5BA',
};

export function SeverityDistribution({ checks }: { checks: Check[] }) {
  const severities = ['critical', 'high', 'medium', 'low', 'informational'] as const;
  const buckets = severities.map((severity) => ({
    severity,
    items: checks.filter((check) => check.severity === severity && check.status !== 'pass' && check.status !== 'not_tested'),
  }));
  const total = buckets.reduce((sum, bucket) => sum + bucket.items.length, 0);

  if (total === 0) {
    return (
      <p className="rounded-xl border border-pass/20 bg-passSoft px-4 py-3 text-sm text-pass">
        No open issues by severity — every tested check passed.
      </p>
    );
  }

  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-mist">
        {buckets.map((bucket) =>
          bucket.items.length ? (
            <div
              key={bucket.severity}
              className="h-full transition-all duration-700 ease-smooth first:rounded-l-full last:rounded-r-full"
              style={{
                width: `${(bucket.items.length / total) * 100}%`,
                background: SEVERITY_COLORS[bucket.severity],
              }}
              title={`${bucket.items.length} ${bucket.severity}`}
            />
          ) : null,
        )}
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
        {buckets.map((bucket) => (
          <li key={bucket.severity} className="flex items-center justify-between gap-2 text-xs">
            <span className="flex items-center gap-2 text-muted">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: SEVERITY_COLORS[bucket.severity] }}
                aria-hidden
              />
              <span className="capitalize">{bucket.severity}</span>
            </span>
            <span className="font-mono text-ink">{bucket.items.length}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CategoryBreakdown({
  categories,
  pillar,
}: {
  categories: CategoryScore[];
  pillar?: 'seo' | 'aeo' | 'geo';
}) {
  const filtered = pillar ? categories.filter((category) => category.pillar === pillar) : categories;
  return (
    <div className="divide-y divide-line">
      {filtered.map((category) => (
        <div key={`${category.pillar}-${category.category}`} className="flex items-center gap-4 py-3">
          <div className="w-full min-w-0">
            <div className="flex items-baseline justify-between gap-3">
              <p className="truncate text-sm text-ink">
                {pillar ? category.category : (
                  <>
                    <span className="font-mono text-2xs uppercase tracking-[0.14em] text-faint">
                      {PILLAR_META[category.pillar]?.label}
                    </span>{' '}
                    <span className="text-muted">·</span> {category.category}
                  </>
                )}
              </p>
              <span className="shrink-0 font-mono text-xs" style={{ color: scoreColor(category.score) }}>
                {category.score === null ? '—' : `${category.score}`}
              </span>
            </div>
            <ScoreBar score={category.score} className="mt-2" height={4} />
          </div>
          <div className="hidden w-32 shrink-0 items-center justify-end gap-2.5 text-[10px] text-faint sm:flex">
            <span className="inline-flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-pass" />
              {category.passed}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-warn" />
              {category.warning}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-fail" />
              {category.failed}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function PillarComparison({ scores }: { scores: Scores }) {
  const pillars = ['seo', 'aeo', 'geo'] as const;
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {pillars.map((pillar) => {
        const data = scores.pillars[pillar];
        return (
          <div key={pillar} className="rounded-xl border border-line bg-surface p-4">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-2xs uppercase tracking-[0.14em] text-faint">{data.label}</span>
              <span className="text-lg font-semibold" style={{ color: scoreColor(data.score) }}>
                {data.score ?? '—'}
              </span>
            </div>
            <ScoreBar score={data.score} className="mt-3" height={5} />
            <p className="mt-3 text-[11px] text-faint">
              {data.passed} pass · {data.warnings} warn · {data.failed} fail
              {data.notTested ? ` · ${data.notTested} n/a` : ''}
            </p>
          </div>
        );
      })}
    </div>
  );
}

export function CheckCounts({ scores }: { scores: Scores }) {
  const items = [
    { label: 'Critical issues', value: scores.severityCounts.critical ?? 0, tone: 'text-fail' },
    { label: 'High', value: scores.severityCounts.high ?? 0, tone: 'text-accent' },
    { label: 'Warnings', value: scores.counts.warning, tone: 'text-warn' },
    { label: 'Passed', value: scores.counts.pass, tone: 'text-pass' },
  ];
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="bg-surface px-4 py-3.5">
          <p className={clsx('text-xl font-semibold tracking-[-0.02em]', item.tone)}>{item.value}</p>
          <p className="mt-0.5 text-[11px] text-muted">{item.label}</p>
        </div>
      ))}
    </div>
  );
}
