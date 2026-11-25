import clsx from 'clsx';
import { Check, Loader2 } from 'lucide-react';
import type { ProgressEvent } from '../lib/types';

const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued',
  validating: 'Validating URL',
  connecting: 'Connecting',
  robots: 'robots.txt',
  sitemap: 'Sitemap',
  discover: 'Discovery',
  crawl: 'Crawling pages',
  links: 'Link checks',
  analyse: 'Analysis',
  summary: 'Summary',
  done: 'Report ready',
  failed: 'Failed',
};

const ORDERED_STAGES = ['validating', 'connecting', 'robots', 'sitemap', 'discover', 'crawl', 'links', 'analyse', 'summary', 'done'];

export function ProgressTimeline({
  events,
  progress,
  currentStage,
  error,
}: {
  events: ProgressEvent[];
  progress: number;
  currentStage?: string | null;
  error?: string | null;
}) {
  const reached = new Set(events.map((event) => event.stage));
  const currentIndex = currentStage ? ORDERED_STAGES.indexOf(currentStage) : -1;

  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-baseline justify-between">
          <span className="font-mono text-2xs uppercase tracking-[0.16em] text-faint">Progress</span>
          <span className="font-mono text-sm text-ink">{Math.min(100, Math.round(progress))}%</span>
        </div>
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-mist">
          <div
            className={clsx('h-full rounded-full transition-all duration-700 ease-smooth', error ? 'bg-fail' : 'bg-ink')}
            style={{ width: `${Math.max(3, Math.min(100, progress))}%` }}
          />
        </div>
      </div>

      <ol className="space-y-0">
        {ORDERED_STAGES.map((stage, index) => {
          const done = reached.has(stage) && (index < currentIndex || currentStage === 'done');
          const active = currentStage === stage && currentStage !== 'done';
          if (stage === 'done' && !reached.has('done')) return null;
          return (
            <li key={stage} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={clsx(
                    'flex h-6 w-6 items-center justify-center rounded-full border text-[10px] transition-colors duration-300',
                    done && 'border-ink bg-ink text-paper',
                    active && 'border-ink bg-surface text-ink',
                    !done && !active && 'border-line bg-surface text-faint',
                  )}
                >
                  {done ? <Check className="h-3 w-3" /> : active ? <Loader2 className="h-3 w-3 animate-spin" /> : index + 1}
                </span>
                {index < ORDERED_STAGES.length - 1 && reached.has(ORDERED_STAGES[index + 1]) ? (
                  <span className="my-1 h-5 w-px bg-line" />
                ) : (
                  <span className="my-1 h-5 w-px bg-transparent" />
                )}
              </div>
              <div className="pb-1">
                <p
                  className={clsx(
                    'text-sm transition-colors',
                    done ? 'text-muted' : active ? 'font-medium text-ink' : 'text-faint',
                  )}
                >
                  {STAGE_LABELS[stage] ?? stage}
                </p>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="rounded-xl border border-line bg-mist/60 p-4">
        <p className="font-mono text-2xs uppercase tracking-[0.14em] text-faint">Live log</p>
        <ul className="mt-3 space-y-2">
          {events.slice(-5).map((event, index) => (
            <li key={`${event.at}-${index}`} className="flex gap-2 text-xs text-muted">
              <span className="font-mono text-[10px] text-faint">
                {new Date(event.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span className="flex-1 truncate">
                {event.message}
                {event.detail ? <span className="ml-1 font-mono text-[10px] text-faint">· {event.detail}</span> : null}
              </span>
            </li>
          ))}
          {events.length === 0 ? <li className="text-xs text-faint">Waiting for the crawler…</li> : null}
        </ul>
      </div>
    </div>
  );
}
