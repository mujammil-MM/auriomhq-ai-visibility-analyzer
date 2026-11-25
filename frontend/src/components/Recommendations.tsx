import clsx from 'clsx';
import { ArrowUpRight, Code2, Sparkles, Wand2 } from 'lucide-react';
import { useState } from 'react';
import { CopyButton, StatusChip } from './Primitives';
import { PILLAR_META, prettyUrl } from '../lib/utils';
import type { Recommendations as RecommendationsType, RecItem } from '../lib/types';

const IMPACT_STYLES: Record<string, string> = {
  High: 'border-fail/25 bg-failSoft text-fail',
  Medium: 'border-warn/25 bg-warnSoft text-warn',
  Low: 'border-line bg-mist text-muted',
};

const EFFORT_STYLES: Record<string, string> = {
  Easy: 'border-pass/25 bg-passSoft text-pass',
  Moderate: 'border-line bg-mist text-muted',
  Hard: 'border-lineStrong bg-mist text-muted',
};

export function Roadmap({ data }: { data: RecommendationsType }) {
  return (
    <div className="space-y-8">
      {data.quickWins.length > 0 ? (
        <div className="rounded-xl border border-accent/20 bg-accentSoft/60 p-5">
          <p className="label text-accent">Quick wins — high impact, low effort</p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {data.quickWins.map((item) => (
              <li key={item.id} className="flex items-start gap-2 text-sm text-ink">
                <ArrowUpRight className="mt-1 h-3.5 w-3.5 shrink-0 text-accent" />
                <span>{item.title}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {data.roadmap.map((phase) => (
        <section key={phase.priority}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h3 className="text-lg font-semibold tracking-[-0.02em]">{phase.title}</h3>
              <p className="mt-1 max-w-2xl text-sm text-muted">{phase.description}</p>
            </div>
            <div className="text-right">
              <p className="font-mono text-2xs uppercase tracking-[0.14em] text-faint">Potential uplift</p>
              <p className="font-mono text-sm text-ink">+{phase.potentialPoints.toFixed(0)} pts</p>
            </div>
          </div>

          {phase.items.length === 0 ? (
            <p className="mt-4 rounded-xl border border-dashed border-line bg-mist/40 px-4 py-5 text-sm text-muted">
              Nothing to do here — no issues in this band were detected.
            </p>
          ) : (
            <ul className="mt-4 space-y-3">
              {phase.items.map((item) => (
                <RecommendationCard key={item.id} item={item} />
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}

function RecommendationCard({ item }: { item: RecItem }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-xl border border-line bg-surface p-4 transition-shadow duration-300 hover:shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-medium text-ink">{item.title}</h4>
            <StatusChip status={item.status} />
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{item.benefit}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={clsx('chip', IMPACT_STYLES[item.impact])}>{item.impact} impact</span>
          <span className={clsx('chip', EFFORT_STYLES[item.difficulty])}>{item.difficulty}</span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-faint">
        <span className="font-mono uppercase tracking-[0.12em]">{PILLAR_META[item.pillar]?.label}</span>
        <span>Score impact +{item.scoreImpact.toFixed(1)} pts</span>
        {item.pages.length ? <span>{item.pages.length} page(s) affected</span> : null}
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="ml-auto text-ink underline decoration-lineStrong underline-offset-4 hover:decoration-ink"
        >
          {open ? 'Hide guidance' : 'How to implement'}
        </button>
      </div>

      {open ? (
        <div className="mt-4 animate-fadeIn space-y-3 border-t border-line pt-4">
          <div>
            <p className="label mb-1">Evidence from your site</p>
            <p className="text-[13px] leading-relaxed text-muted">{item.evidence}</p>
          </div>
          <div>
            <p className="label mb-1">How to fix it</p>
            <p className="text-[13px] leading-relaxed text-muted">{item.guidance}</p>
          </div>
          <div>
            <p className="label mb-1.5">Example</p>
            <pre className="scrollbar-thin overflow-x-auto rounded-lg border border-line bg-[#FBFAF6] p-3 font-mono text-[11.5px] leading-relaxed text-[#3F3C35]">
              <code>{item.example}</code>
            </pre>
          </div>
          {item.pages.length ? (
            <div>
              <p className="label mb-1">Pages affected</p>
              <ul className="space-y-1">
                {item.pages.map((page) => (
                  <li key={page}>
                    <a
                      href={page}
                      target="_blank"
                      rel="noreferrer nofollow"
                      className="font-mono text-[11px] text-muted underline decoration-lineStrong underline-offset-2 hover:text-ink"
                    >
                      {prettyUrl(page)}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export function Drafts({ data }: { data: RecommendationsType }) {
  const drafts = data.drafts;
  const hasContent =
    drafts.titles.length ||
    drafts.metaDescriptions.length ||
    drafts.faqQuestions.length ||
    drafts.schemaSuggestions.length;

  if (!hasContent) {
    return (
      <p className="rounded-xl border border-dashed border-line bg-mist/40 px-4 py-5 text-sm text-muted">
        No content drafts were generated for this site — the metadata and structured data already cover the
        basics measured by this audit.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3 rounded-xl border border-line bg-mist/50 p-4">
        <Wand2 className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
        <p className="text-[13px] leading-relaxed text-muted">{drafts.note}</p>
      </div>

      {drafts.titles.length > 0 ? (
        <DraftBlock title="Title tag options" subtitle={drafts.currentTitle ? `Current: “${drafts.currentTitle}”` : undefined}>
          {drafts.titles.map((title, index) => (
            <DraftRow key={index} value={title} meta={`${title.length} characters`} />
          ))}
        </DraftBlock>
      ) : null}

      {drafts.metaDescriptions.length > 0 ? (
        <DraftBlock
          title="Meta description options"
          subtitle={
            drafts.currentMetaDescription
              ? `Current (${drafts.currentMetaDescription.length} chars): “${drafts.currentMetaDescription}”`
              : 'No meta description currently set.'
          }
        >
          {drafts.metaDescriptions.map((meta, index) => (
            <DraftRow key={index} value={meta} meta={`${meta.length} characters`} />
          ))}
        </DraftBlock>
      ) : null}

      {drafts.faqQuestions.length > 0 ? (
        <DraftBlock
          title="FAQ questions to answer"
          subtitle="Derived from headings and recurring terms on your page. Write the answers yourself — the report does not invent claims."
        >
          <ul className="space-y-1.5">
            {drafts.faqQuestions.map((question) => (
              <li key={question} className="flex items-start gap-2 text-[13.5px] text-muted">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-lineStrong" />
                {question}
              </li>
            ))}
          </ul>
        </DraftBlock>
      ) : null}

      {drafts.headingOutline.length > 0 ? (
        <DraftBlock title="Suggested heading structure" subtitle="Existing headings are labelled; suggested additions fill gaps in the outline.">
          <ul className="space-y-1">
            {drafts.headingOutline.map((item, index) => (
              <li
                key={`${item.text}-${index}`}
                className={clsx('flex items-center gap-2 text-[13px]', item.level > 1 && 'pl-4')}
              >
                <span className="font-mono text-[10px] text-faint">H{item.level}</span>
                <span className={item.source === 'suggested' ? 'text-accent' : 'text-muted'}>{item.text}</span>
                {item.source === 'suggested' ? (
                  <span className="chip border-accent/20 bg-accentSoft text-accent">suggested</span>
                ) : null}
              </li>
            ))}
          </ul>
        </DraftBlock>
      ) : null}

      {drafts.schemaSuggestions.length > 0 ? (
        <DraftBlock title="Structured data to add" subtitle="Copy these JSON-LD blocks and replace the bracketed placeholders.">
          <div className="space-y-3">
            {drafts.schemaSuggestions.map((suggestion) => (
              <div key={suggestion.type} className="rounded-lg border border-line bg-[#FBFAF6]">
                <div className="flex items-center justify-between gap-3 border-b border-line px-3 py-2">
                  <div className="flex items-center gap-2">
                    <Code2 className="h-3.5 w-3.5 text-muted" />
                    <span className="text-xs font-medium text-ink">{suggestion.type}</span>
                    <span className="text-[11px] text-muted">{suggestion.reason}</span>
                  </div>
                  <CopyButton value={JSON.stringify(suggestion.draft, null, 2)} label="Copy" />
                </div>
                <pre className="scrollbar-thin overflow-x-auto p-3 font-mono text-[11px] leading-relaxed text-[#3F3C35]">
                  <code>{JSON.stringify(suggestion.draft, null, 2)}</code>
                </pre>
              </div>
            ))}
          </div>
        </DraftBlock>
      ) : null}
    </div>
  );
}

function DraftBlock({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="text-sm font-medium text-ink">{title}</h4>
      {subtitle ? <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{subtitle}</p> : null}
      <div className="mt-3 space-y-2">{children}</div>
    </div>
  );
}

function DraftRow({ value, meta }: { value: string; meta: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-line bg-surface px-3 py-2.5">
      <p className="text-[13.5px] leading-relaxed text-ink">{value}</p>
      <div className="flex shrink-0 items-center gap-2">
        <span className="hidden font-mono text-[10px] text-faint sm:block">{meta}</span>
        <CopyButton value={value} label="Copy" />
      </div>
    </div>
  );
}

export function AiBadge({ enhanced }: { enhanced: boolean }) {
  return (
    <span
      className={clsx(
        'chip',
        enhanced ? 'border-accent/25 bg-accentSoft text-accent' : 'border-line bg-mist text-muted',
      )}
    >
      <Sparkles className="h-3 w-3" />
      {enhanced ? 'AI-enhanced wording' : 'Rule-based engine'}
    </span>
  );
}
