export type Pillar = 'seo' | 'aeo' | 'geo';
export type Status = 'pass' | 'warning' | 'fail' | 'not_tested';
export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'informational';

export interface Check {
  id: string;
  pillar: Pillar;
  category: string;
  title: string;
  description: string;
  status: Status;
  statusLabel: string;
  severity: Severity;
  weight: number;
  credit: number;
  earned: number;
  evidence: string;
  why: string;
  fix: string;
  example: string;
  priority: 1 | 2 | 3;
  pages: string[];
  detail: string;
}

export interface PillarScore {
  pillar: Pillar;
  label: string;
  score: number | null;
  earned: number;
  available: number;
  checksTotal: number;
  tested: number;
  passed: number;
  warnings: number;
  failed: number;
  notTested: number;
  weight: number;
}

export interface CategoryScore {
  pillar: Pillar;
  category: string;
  score: number | null;
  earned: number;
  available: number;
  passed: number;
  warning: number;
  failed: number;
  notTested: number;
}

export interface Scores {
  overall: number | null;
  pillars: Record<Pillar, PillarScore>;
  counts: { pass: number; warning: number; fail: number; not_tested: number; total: number };
  severityCounts: Record<string, number>;
  categories: CategoryScore[];
  explanation: string[];
  methodology: {
    pillarWeights: Record<Pillar, number>;
    warningCredit: string;
    notTested: string;
    formula: string;
  };
}

export interface RecItem {
  id: string;
  checkId: string;
  title: string;
  pillar: Pillar;
  status: Status;
  severity: Severity;
  impact: 'High' | 'Medium' | 'Low';
  difficulty: 'Easy' | 'Moderate' | 'Hard';
  benefit: string;
  guidance: string;
  example: string;
  evidence: string;
  scoreImpact: number;
  pages: string[];
}

export interface RoadmapPhase {
  priority: 1 | 2 | 3;
  title: string;
  description: string;
  items: RecItem[];
  itemCount: number;
  potentialPoints: number;
}

export interface SchemaSuggestion {
  type: string;
  reason: string;
  draft: Record<string, unknown>;
}

export interface Drafts {
  titles: string[];
  currentTitle?: string;
  metaDescriptions: string[];
  currentMetaDescription?: string;
  headingOutline: { level: number; text: string; source: string }[];
  faqQuestions: string[];
  schemaSuggestions: SchemaSuggestion[];
  note?: string;
}

export interface Recommendations {
  roadmap: RoadmapPhase[];
  quickWins: RecItem[];
  drafts: Drafts;
  untested: string[];
  generatedFrom: { pages: number; brand: string; url: string };
}

export interface PageInfo {
  url: string;
  finalUrl: string;
  status: number | null;
  ok: boolean;
  error: string | null;
  title: string;
  metaDescription: string;
  canonical: string;
  robotsMeta: string[];
  xRobotsTag: string;
  lang: string;
  viewport: string;
  headings: { level: number; text: string }[];
  h1: string[];
  h2: string[];
  imagesTotal: number;
  imagesMissingAlt: number;
  internalLinks: number;
  externalLinks: number;
  schemaTypes: string[];
  schemaErrors: string[];
  wordCount: number;
  textHtmlRatio: number;
  questionHeadings: string[];
  listItems: number;
  author: string;
  published: string;
  modified: string;
  redirectChain: string[];
  excerpt: string;
}

export interface CrawlInfo {
  startUrl: string;
  finalUrl: string;
  host: string;
  durationMs: number;
  pagesAnalysed: number;
  pages: PageInfo[];
  robots: {
    available: boolean;
    url: string;
    status: number | null;
    error: string | null;
    crawlDelay: number;
    blockedPaths: string[];
    blocksAll: boolean;
    aiAccess: Record<string, { label: string; explicitly_listed: boolean; allowed: boolean; blocked_paths: { path: string; type: string }[] }>;
  };
  sitemap: { available: boolean; url: string; urlCount: number; sitemapCount: number; error: string | null; sample: string[] };
  llmsTxt: { available: boolean; url: string; status: number | null; snippet: string };
  brokenLinks: { url: string; status: number | null; error: string; found_on: string; anchor: string; type: string }[];
  inaccessiblePages: { url: string; status: number | null; error: string }[];
  discoveredInternalLinks: number;
  httpsAvailable: boolean | null;
  httpToHttpsRedirect: boolean | null;
  homepageStatus: number | null;
  notes: string[];
  errors: string[];
}

export interface Summary {
  executiveSummary?: string;
  keyFindings?: { title: string; detail: string }[];
  priorityActions?: { title: string; detail: string; effort?: string }[];
  aiEnhanced?: boolean;
  source?: string;
  disclaimer?: string;
}

export interface Report {
  schemaVersion: number;
  generatedAt: string;
  site: {
    url: string;
    requestedUrl: string;
    host: string;
    httpsAvailable: boolean | null;
    homepageStatus: number | null;
    pagesAnalysed: number;
    durationMs: number;
  };
  crawl: CrawlInfo;
  scores: Scores;
  band: { label: string; tone: string };
  checks: Check[];
  checksByPillar: Record<Pillar, Check[]>;
  criticalFindings: Check[];
  recommendations: Recommendations;
  summary: Summary;
  evidence: Record<string, unknown>;
  limitations: string[];
}

export interface ProgressEvent {
  stage: string;
  message: string;
  percent: number;
  at: string;
  detail?: string | null;
}

export interface AuditStatus {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  stage?: string | null;
  message?: string | null;
  events: ProgressEvent[];
  report: Report | null;
  error?: string | null;
  errorCode?: string;
  createdAt?: string | null;
  completedAt?: string | null;
  share?: { token: string; visibility: 'public' | 'private'; sharedAt?: string | null } | null;
  url?: string;
}

export interface ShareResult {
  token: string;
  visibility: 'public' | 'private';
  url: string;
  path: string;
}

export interface PublicConfig {
  brand: string;
  product: string;
  tagline: string;
  brandUrl: string;
  contactUrl: string;
  contactEmail: string;
  maxPages: number;
  aiEnabled: boolean;
  rateLimit: { auditsPerWindow: number; windowSeconds: number };
  features: { pdf: boolean; sharing: boolean; accounts: boolean; aiRecommendations: boolean; leadCapture: boolean };
  stats: { completedAudits: number; leads: number; lastAuditAt: string | null };
  pillarWeights: Record<Pillar, number>;
}

export interface Methodology {
  pillars: Record<Pillar, { label: string; weight: number; description: string }>;
  scoring: {
    formula: string;
    overall: string;
    credits: { pass: string; warning: string; fail: string; not_tested: string };
    bands: { min: number; label: string }[];
  };
  checks: {
    id: string;
    pillar: Pillar;
    category: string;
    title: string;
    description: string;
    why: string;
    severity: Severity;
    weight: number;
    priority: number;
  }[];
  limitations: string[];
}
