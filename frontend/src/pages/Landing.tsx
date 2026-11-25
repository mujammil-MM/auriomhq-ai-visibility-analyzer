import {
  ArrowRight, Bot, CheckCircle2, FileText, Gauge, Layers, Radar, ScanSearch, Share2, ShieldCheck,
  Sparkles, Terminal, Waypoints,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Clock3 } from 'lucide-react';
import { Eyebrow, SectionHeading } from '../components/Primitives';
import { UrlForm } from '../components/UrlForm';
import { api } from '../lib/api';
import { PILLAR_META } from '../lib/utils';
import type { PublicConfig } from '../lib/types';

const PILLAR_CARDS = [
  {
    pillar: 'seo' as const,
    icon: ScanSearch,
    bullets: [
      'Status codes, HTTPS and redirect chains',
      'Titles, descriptions, canonicals, robots directives',
      'Heading hierarchy, alt text, internal linking',
      'robot.txt, sitemap.xml and indexability',
    ],
  },
  {
    pillar: 'aeo' as const,
    icon: Layers,
    bullets: [
      'FAQ blocks and question-style headings',
      'Direct answer paragraphs and definitions',
      'Lists, steps and answer-friendly structure',
      'Article, FAQPage and HowTo schema',
    ],
  },
  {
    pillar: 'geo' as const,
    icon: Radar,
    bullets: [
      'Organisation and author entity clarity',
      'AI crawler access in robots.txt',
      'llms.txt, structured data depth, sameAs',
      'Citations, freshness and HTML availability',
    ],
  },
];

const STEPS = [
  { title: 'Enter your URL', text: 'We validate the address and resolve DNS before anything else runs.' },
  { title: 'We crawl your site', text: 'Up to 10 pages, respecting robots.txt, with every redirect and IP checked.' },
  { title: '60+ checks run', text: 'Independent SEO, AEO and GEO engines score each signal with evidence.' },
  { title: 'Get the report', text: 'Dashboard, prioritised roadmap, PDF export and a shareable link.' },
];

const FAQ = [
  {
    q: 'Is this a real audit or a demo?',
    a: 'Every score comes from an actual crawl of your website performed when you click Analyse. Nothing is pre-filled, estimated from templates or randomly generated.',
  },
  {
    q: 'Does it measure my rankings or AI citations?',
    a: 'No. Rankings, search volume, backlinks and observed AI citations require external data providers. This audit measures on-page readiness — the part you can control — and says so throughout the report.',
  },
  {
    q: 'What changes with an AI key configured?',
    a: 'The analysis engine works fully without one. When an AI provider is configured server-side, the executive summary and recommendation wording are regenerated from the same crawl evidence. The model is never allowed to invent findings.',
  },
  {
    q: 'How is the overall score calculated?',
    a: 'Each check carries a fixed weight. Passes earn full weight, warnings earn partial credit, failures earn none, and checks that could not be tested are excluded. SEO is weighted 40%, AEO 30% and GEO 30%.',
  },
];

interface RecentAudit {
  id: string;
  url?: string;
  at: string;
  score?: number;
}

function readRecent(): RecentAudit[] {
  try {
    const raw = window.localStorage.getItem('auriomhq.recent-audits');
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, 4) : [];
  } catch {
    return [];
  }
}

export function Landing() {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const [recent, setRecent] = useState<RecentAudit[]>([]);

  useEffect(() => {
    api.config().then(setConfig).catch(() => setConfig(null));
    setRecent(readRecent());
  }, []);

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-line">
        <div className="pointer-events-none absolute inset-0 grid-lines opacity-[0.55] mask-fade-b" aria-hidden />
        <div className="relative mx-auto w-full max-w-[1180px] px-5 pb-16 pt-16 sm:px-8 sm:pb-24 sm:pt-24">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="chip border-line bg-surface text-muted">AuriomHQ</span>
              <span className="chip border-line bg-surface text-muted">
                <Sparkles className="h-3 w-3 text-accent" /> AI Visibility Analyzer
              </span>
            </div>
            <h1 className="mt-6 text-balance text-[38px] font-semibold leading-[1.05] tracking-[-0.04em] sm:text-[58px]">
              Make your website visible everywhere people search.
            </h1>
            <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-muted sm:text-[17px]">
              Run a real audit of your SEO, AEO and GEO readiness. See exactly what search engines and AI
              assistants can — and cannot — understand about your site, with evidence from your own HTML.
            </p>

            <div id="audit" className="mt-8 max-w-2xl scroll-mt-24">
              <UrlForm />
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-[12px] text-muted">
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-pass" /> SSRF-protected crawler
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Gauge className="h-3.5 w-3.5 text-muted" /> 60+ weighted checks
              </span>
              <span className="inline-flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5 text-muted" /> PDF report
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Share2 className="h-3.5 w-3.5 text-muted" /> Shareable results
              </span>
              {config && config.stats.completedAudits > 0 ? (
                <span className="inline-flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-pass" />
                  {config.stats.completedAudits} audit{config.stats.completedAudits === 1 ? '' : 's'} completed
                </span>
              ) : null}
            </div>
          </div>

          {/* sample evidence strip */}
          <div className="mt-14 grid gap-3 sm:grid-cols-3">
            {(['seo', 'aeo', 'geo'] as const).map((pillar) => (
              <div key={pillar} className="rounded-xl border border-line bg-surface/80 p-4 backdrop-blur-sm">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-2xs uppercase tracking-[0.16em] text-faint">
                    {PILLAR_META[pillar].label}
                  </span>
                  <span className="h-1.5 w-1.5 rounded-full bg-lineStrong" />
                </div>
                <p className="mt-2 text-[13px] leading-snug text-ink">{PILLAR_META[pillar].blurb}</p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-faint">
            Scores shown after an audit are computed from your crawl. No sample or placeholder results are displayed.
          </p>

          {recent.length ? (
            <div className="mt-8 rounded-xl border border-line bg-surface/70 p-4">
              <div className="flex items-center gap-2">
                <Clock3 className="h-3.5 w-3.5 text-faint" />
                <p className="label">Your recent audits on this device</p>
              </div>
              <ul className="mt-3 divide-y divide-line">
                {recent.map((item) => (
                  <li key={item.id}>
                    <Link
                      to={`/audit/${item.id}`}
                      className="flex items-center justify-between gap-3 py-2 text-[12.5px] text-muted transition-colors hover:text-ink"
                    >
                      <span className="truncate font-mono">{item.url ? item.url.replace(/^https?:\/\//, '') : item.id}</span>
                      <span className="flex shrink-0 items-center gap-2 text-[11px] text-faint">
                        {new Date(item.at).toLocaleDateString()}
                        <ChevronRight className="h-3 w-3" />
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[10.5px] text-faint">
                Stored in this browser only — no account required.
              </p>
            </div>
          ) : null}
        </div>
      </section>

      {/* Pillars */}
      <section className="mx-auto w-full max-w-[1180px] px-5 py-16 sm:px-8 sm:py-24">
        <SectionHeading
          eyebrow="What we measure"
          title="Three independent engines, one visibility score"
          description="SEO, AEO and GEO are scored separately so you can see whether your problem is discoverability, answerability or AI readability — they have very different fixes."
        />
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {PILLAR_CARDS.map(({ pillar, icon: Icon, bullets }) => (
            <div
              key={pillar}
              className="group flex flex-col rounded-2xl border border-line bg-surface p-6 transition-all duration-300 ease-smooth hover:-translate-y-0.5 hover:border-lineStrong hover:shadow-card"
            >
              <div className="flex items-center justify-between">
                <Icon className="h-5 w-5 text-ink" />
                <span className="font-mono text-2xs uppercase tracking-[0.16em] text-faint">
                  {PILLAR_META[pillar].label}
                </span>
              </div>
              <h3 className="mt-5 text-[17px] font-semibold tracking-[-0.02em]">{PILLAR_META[pillar].name}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{PILLAR_META[pillar].blurb}</p>
              <ul className="mt-5 space-y-2 border-t border-line pt-5">
                {bullets.map((bullet) => (
                  <li key={bullet} className="flex items-start gap-2 text-[12.5px] leading-snug text-muted">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-lineStrong" />
                    {bullet}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-line bg-[#F6F4EE]">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-16 sm:px-8 sm:py-20">
          <SectionHeading eyebrow="How it works" title="From URL to action plan in under a minute" />
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
              <div key={step.title} className="relative">
                <span className="font-mono text-2xs uppercase tracking-[0.16em] text-faint">
                  0{index + 1}
                </span>
                <h3 className="mt-3 text-[15px] font-medium">{step.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{step.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What you get */}
      <section className="mx-auto w-full max-w-[1180px] px-5 py-16 sm:px-8 sm:py-24">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <SectionHeading
              eyebrow="Deliverables"
              title="Evidence, not a vague grade"
              description="Every issue answers four questions: what is wrong, why it matters, what we found on your site, and how to fix it."
            />
            <div className="mt-8 space-y-3">
              {[
                { icon: Terminal, title: 'Crawl evidence', text: 'Raw HTML signals — titles, headings, schema blocks, status codes, robots rules.' },
                { icon: Waypoints, title: 'Prioritised roadmap', text: 'Three phases: fix immediately, improve discoverability, then AI readiness.' },
                { icon: Bot, title: 'Drafts you can use', text: 'Title and description options, FAQ questions and JSON-LD templates derived from your content.' },
                { icon: FileText, title: 'PDF report', text: 'A branded, shareable document with methodology and limitations stated explicitly.' },
              ].map((item) => (
                <div key={item.title} className="flex gap-3 rounded-xl border border-line bg-surface p-4">
                  <item.icon className="mt-0.5 h-4 w-4 shrink-0 text-ink" />
                  <div>
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted">{item.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-line bg-surface p-6 sm:p-8">
            <Eyebrow>Scoring model</Eyebrow>
            <h3 className="mt-2 text-lg font-semibold tracking-[-0.02em]">Transparent by default</h3>
            <p className="mt-2 text-[13px] leading-relaxed text-muted">
              Each of the {config ? '60+' : '60+'} checks has a documented weight, severity and pass criteria. The
              report explains exactly where the points came from.
            </p>
            <div className="mt-6 space-y-4">
              {(['seo', 'aeo', 'geo'] as const).map((pillar) => (
                <div key={pillar}>
                  <div className="flex items-center justify-between text-[12px]">
                    <span className="font-mono uppercase tracking-[0.14em] text-faint">
                      {PILLAR_META[pillar].label}
                    </span>
                    <span className="text-ink">{config ? Math.round(config.pillarWeights[pillar] * 100) : '—'}% weight</span>
                  </div>
                  <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-mist">
                    <div
                      className="h-full rounded-full bg-ink"
                      style={{ width: `${(config?.pillarWeights[pillar] ?? 0.33) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 rounded-xl border border-line bg-mist/50 p-4 text-[12px] leading-relaxed text-muted">
              Pass earns full weight, warning earns partial credit, fail earns none, and checks that cannot be
              tested are excluded from the denominator — never counted as passes.
            </div>
            <Link
              to="/methodology"
              className="mt-5 inline-flex items-center gap-1 text-[13px] text-ink underline decoration-lineStrong underline-offset-4 hover:decoration-ink"
            >
              Read the full methodology <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-line bg-[#F6F4EE]">
        <div className="mx-auto w-full max-w-[900px] px-5 py-16 sm:px-8 sm:py-20">
          <SectionHeading eyebrow="Questions" title="Straight answers" />
          <div className="mt-8 divide-y divide-line border-y border-line">
            {FAQ.map((item, index) => (
              <div key={item.q}>
                <button
                  type="button"
                  onClick={() => setOpenFaq((current) => (current === index ? null : index))}
                  className="flex w-full items-center justify-between gap-4 py-4 text-left"
                  aria-expanded={openFaq === index}
                >
                  <span className="text-[14.5px] font-medium text-ink">{item.q}</span>
                  <span className="font-mono text-sm text-faint">{openFaq === index ? '−' : '+'}</span>
                </button>
                {openFaq === index ? (
                  <p className="animate-fadeIn pb-4 pr-8 text-[13.5px] leading-relaxed text-muted">{item.a}</p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto w-full max-w-[1180px] px-5 py-16 sm:px-8 sm:py-24">
        <div className="rounded-2xl border border-line bg-ink px-6 py-12 text-paper sm:px-12 sm:py-16">
          <div className="max-w-2xl">
            <Eyebrow className="text-paper/50">Start now</Eyebrow>
            <h2 className="mt-3 text-[28px] font-semibold leading-[1.1] tracking-[-0.03em] sm:text-[38px]">
              See what AI search can actually read about your business.
            </h2>
            <p className="mt-3 text-[14px] leading-relaxed text-paper/70">
              Free audit. Real crawl. No account, no credit card, no fabricated scores.
            </p>
            <div className="mt-7 max-w-xl [&_.btn-primary]:bg-paper [&_.btn-primary]:text-ink [&_.btn-primary:hover]:bg-mist">
              <UrlForm />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
