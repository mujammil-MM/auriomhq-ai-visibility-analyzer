import clsx from 'clsx';
import { Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Eyebrow, SectionHeading } from '../components/Primitives';
import { api } from '../lib/api';
import { PILLAR_META, SEVERITY_META } from '../lib/utils';
import type { Methodology, Pillar } from '../lib/types';

export function MethodologyPage() {
  const [data, setData] = useState<Methodology | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.methodology().then(setData).catch(() => setError('Could not load the methodology.'));
  }, []);

  if (error) {
    return <p className="mx-auto max-w-xl px-5 py-24 text-center text-sm text-fail">{error}</p>;
  }
  if (!data) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-faint" />
      </div>
    );
  }

  const groups = (['seo', 'aeo', 'geo'] as Pillar[]).map((pillar) => ({
    pillar,
    checks: data.checks.filter((check) => check.pillar === pillar),
  }));

  return (
    <div className="mx-auto w-full max-w-[1000px] px-5 py-14 sm:px-8 sm:py-20">
      <Eyebrow>Methodology</Eyebrow>
      <h1 className="mt-3 max-w-2xl text-[32px] font-semibold leading-[1.1] tracking-[-0.035em] sm:text-[42px]">
        How the AI Visibility Score is calculated
      </h1>
      <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted">
        This page documents the scoring model exactly as the analyser applies it. It is published so that any
        score in a report can be reproduced from the underlying checks.
      </p>

      <div className="mt-10 grid gap-4 sm:grid-cols-3">
        {groups.map(({ pillar, checks }) => (
          <div key={pillar} className="rounded-2xl border border-line bg-surface p-5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-2xs uppercase tracking-[0.16em] text-faint">
                {PILLAR_META[pillar].label}
              </span>
              <span className="font-mono text-xs text-ink">
                {Math.round(data.pillars[pillar].weight * 100)}%
              </span>
            </div>
            <p className="mt-2 text-sm font-medium">{PILLAR_META[pillar].name}</p>
            <p className="mt-1 text-[12px] leading-relaxed text-muted">{data.pillars[pillar].description}</p>
            <p className="mt-3 border-t border-line pt-3 text-[11px] text-faint">{checks.length} checks</p>
          </div>
        ))}
      </div>

      <section className="mt-14">
        <SectionHeading eyebrow="Scoring" title="The formula" />
        <div className="mt-6 space-y-3">
          {[
            { label: 'Pillar score', value: data.scoring.formula },
            { label: 'Overall score', value: data.scoring.overall },
            { label: 'Pass', value: data.scoring.credits.pass },
            { label: 'Warning', value: data.scoring.credits.warning },
            { label: 'Fail', value: data.scoring.credits.fail },
            { label: 'Not tested', value: data.scoring.credits.not_tested },
          ].map((row) => (
            <div key={row.label} className="grid gap-1 rounded-xl border border-line bg-surface px-4 py-3 sm:grid-cols-[160px_1fr] sm:gap-4">
              <span className="label sm:pt-0.5">{row.label}</span>
              <span className="font-mono text-[12px] leading-relaxed text-muted">{row.value}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {data.scoring.bands.map((band) => (
            <span key={band.label} className="chip border-line bg-surface text-muted">
              {band.label} · {band.min}+
            </span>
          ))}
        </div>
      </section>

      <section className="mt-14">
        <SectionHeading
          eyebrow="Check catalogue"
          title="Every check, weight and severity"
          description="Checks are grouped by pillar and category. Weights are fixed, so the same crawl always produces the same score."
        />
        <div className="mt-8 space-y-8">
          {groups.map(({ pillar, checks }) => (
            <div key={pillar}>
              <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-ink">
                {PILLAR_META[pillar].label} · {checks.length} checks
              </h3>
              <div className="mt-3 overflow-hidden rounded-xl border border-line bg-surface">
                <div className="hidden grid-cols-[2.4fr_0.8fr_0.6fr_0.5fr] gap-3 border-b border-line bg-mist/60 px-4 py-2 sm:grid">
                  {['Check', 'Category', 'Severity', 'Weight'].map((label) => (
                    <span key={label} className="label">{label}</span>
                  ))}
                </div>
                {checks.map((check) => (
                  <div key={check.id} className="grid gap-1 border-b border-line px-4 py-2.5 last:border-b-0 sm:grid-cols-[2.4fr_0.8fr_0.6fr_0.5fr] sm:items-center sm:gap-3">
                    <div>
                      <p className="text-[13px] font-medium text-ink">{check.title}</p>
                      <p className="text-[11.5px] leading-relaxed text-muted">{check.description}</p>
                    </div>
                    <span className="text-[11.5px] text-muted">{check.category}</span>
                    <span className={clsx('font-mono text-[10px] uppercase tracking-[0.12em]', SEVERITY_META[check.severity].className)}>
                      {check.severity}
                    </span>
                    <span className="font-mono text-[11px] text-muted">{check.weight}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-14">
        <SectionHeading eyebrow="Scope" title="What this audit cannot tell you" />
        <ul className="mt-5 space-y-2">
          {data.limitations.map((item) => (
            <li key={item} className="flex gap-2 text-[13.5px] leading-relaxed text-muted">
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-lineStrong" />
              {item}
            </li>
          ))}
        </ul>
        <div className="mt-8 flex flex-wrap gap-2">
          <Link to="/" className="btn-primary">
            Run an audit
          </Link>
          <a href="https://auriomhq.work/contact" target="_blank" rel="noreferrer" className="btn-secondary">
            Talk to AuriomHQ
          </a>
        </div>
      </section>
    </div>
  );
}
