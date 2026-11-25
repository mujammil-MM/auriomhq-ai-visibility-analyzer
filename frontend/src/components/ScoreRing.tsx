import clsx from 'clsx';
import { useEffect, useState } from 'react';
import { scoreColor } from '../lib/utils';

interface ScoreRingProps {
  score: number | null | undefined;
  size?: number;
  thickness?: number;
  label?: string;
  sublabel?: string;
  className?: string;
  animate?: boolean;
}

export function ScoreRing({
  score,
  size = 132,
  thickness = 9,
  label,
  sublabel,
  className,
  animate = true,
}: ScoreRingProps) {
  const [display, setDisplay] = useState(animate ? 0 : score ?? 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const target = score ?? 0;

  useEffect(() => {
    if (!animate) {
      setDisplay(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const duration = 900;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(target * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, animate]);

  const color = scoreColor(score);
  const dash = (Math.max(0, Math.min(100, display)) / 100) * circumference;

  return (
    <div className={clsx('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={`Score ${score ?? 'not scored'} out of 100`}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#ECE9E1" strokeWidth={thickness} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          style={{ transition: 'stroke-dasharray 120ms linear' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="font-semibold tracking-[-0.04em] text-ink"
          style={{ fontSize: size * 0.28, lineHeight: 1 }}
        >
          {score === null || score === undefined ? '—' : Math.round(display)}
        </span>
        {label ? (
          <span className="mt-1 font-mono text-2xs uppercase tracking-[0.14em] text-faint">{label}</span>
        ) : null}
        {sublabel ? <span className="mt-0.5 text-2xs text-muted">{sublabel}</span> : null}
      </div>
    </div>
  );
}

export function ScoreBar({
  score,
  height = 6,
  className,
  showValue = false,
}: {
  score: number | null | undefined;
  height?: number;
  className?: string;
  showValue?: boolean;
}) {
  const value = score ?? 0;
  return (
    <div className={clsx('flex items-center gap-3', className)}>
      <div className="relative w-full overflow-hidden rounded-full bg-[#ECE9E1]" style={{ height }}>
        <div
          className="h-full rounded-full transition-all duration-700 ease-smooth"
          style={{ width: `${Math.max(2, Math.min(100, value))}%`, background: scoreColor(score) }}
        />
      </div>
      {showValue ? (
        <span className="w-8 shrink-0 text-right font-mono text-xs text-muted">
          {score === null || score === undefined ? '—' : Math.round(score)}
        </span>
      ) : null}
    </div>
  );
}
