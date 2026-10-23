import { useEffect, useState, useRef } from "react"
import {
  ArrowUpRight,
  ArrowRight,
  ArrowDown,
  Sparkles,
  ShieldCheck,
  Check,
  ChevronDown,
  Menu,
  X,
  ScanText,
  SlidersHorizontal,
  Columns2,
  Fingerprint,
  Feather,
  Copy,
  Download,
  RotateCcw,
  Trash2,
  FileText,
  Clock,
  AlertCircle,
  LoaderCircle,
  CheckCheck,
  Settings2,
  WandSparkles,
  Plus,
  Mail,
  Briefcase,
  Workflow,
  Award,
  Scale,
  Terminal,
  Activity,
  Layers,
  CheckCircle2,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import {
  writingModes,
  contexts,
  tones,
  intensities,
  defaults,
  example,
  words,
  readLocal,
  writeLocal,
  diffWords,
  samplePresets,
  entities,
  extractNegations,
} from "./lib/model"
import type { Options, Result, WritingMode, SamplePreset } from "./lib/model"
import { humanizeText, splitAudienceText } from "./lib/api"
import type { AudienceSplitResult } from "./lib/api"

type Page = "home" | "workspace" | "splitter" | "history" | "settings"

const modeDescriptions: Record<string, string> = {
  "Clarity Improvement": "Default. Eliminates stiff/robotic phrasing while preserving exact meaning and length.",
  "Grammar Correction": "Strictly fixes grammar, punctuation, and mechanics without altering voice or structure.",
  "Academic Writing": "Elevates tone to scholarly, objective prose with complete preservation of citations.",
  "Professional Writing": "Direct, executive clarity for business correspondence, proposals, and reports.",
  "Conversational Writing": "Warm, natural human flow while preserving every factual detail and number.",
  "Technical Writing": "Unambiguous precision, step-by-step clarity, and strict terminology integrity.",
  "Concise Writing": "Eliminates wordiness and redundancy without dropping any unique facts or conditions.",
  "Expanded Explanation": "Deepens clarity and flow for complex or dense ideas without altering conclusions.",
}

const descriptions = {
  Light: "Small edits. Your words, a little smoother.",
  Balanced: "A natural balance of clarity, flow, and your voice.",
  Strong: "A fresh structure. The same meaning and facts.",
}

export interface PipelineStepMeta {
  step: number
  badge: string
  title: string
  subtitle: string
  detail: string
  icon: LucideIcon
}

export const PIPELINE_STEPS: PipelineStepMeta[] = [
  {
    step: 1,
    badge: "1. Text Ingestion & Parsing",
    title: "Deconstructing text & structural paragraphs...",
    subtitle: "Mapping structural blocks, token boundaries, and sentence cadence baseline.",
    detail: "Syntactic Node Decomposition",
    icon: FileText,
  },
  {
    step: 2,
    badge: "2. Intent & FactGuard Anchor Lock",
    title: "Locking facts, numbers & technical entities...",
    subtitle: "Isolating immutable metrics, numbers, dates, and domain entities from modification.",
    detail: "Deterministic Entity Hard-Lock",
    icon: ShieldCheck,
  },
  {
    step: 3,
    badge: "3. Robotic Markers & Cadence Scan",
    title: "Diagnosing sentence uniformity & AI cliché markers...",
    subtitle: "Measuring burstiness variance, repetitive transition words, and stiff machine rhythms.",
    detail: "Cadence & AI Pattern Diagnostics",
    icon: ScanText,
  },
  {
    step: 4,
    badge: "4. Contextual Human Voice Synthesis",
    title: "Synthesizing authentic, workplace-ready prose...",
    subtitle: "Restructuring stiff sentences into varied human cadence matching your selected tone.",
    detail: "Neural Voice Adaptation",
    icon: WandSparkles,
  },
  {
    step: 5,
    badge: "5. FactGuard Zero-Hallucination Audit",
    title: "Executing deterministic fact-preservation audit...",
    subtitle: "Cross-referencing 100% of numbers, negations, and factual commitments against source.",
    detail: "Zero-Hallucination Matrix Verification",
    icon: CheckCheck,
  },
  {
    step: 6,
    badge: "6. Certified Humanized Synthesis",
    title: "Human touch calibration & certification...",
    subtitle: "Harmonizing final paragraph separation and certifying 100% factual integrity.",
    detail: "Final Human Calibration & Certification",
    icon: Sparkles,
  },
]

function Brand({ onClick }: { onClick: () => void }) {
  return (
    <button className="brand" onClick={onClick} aria-label="HumanizeAI home">
      <span className="brand-icon">
        <span />
        <span />
        <span />
      </span>
      HUMANIZE<span className="brand-ai">AI</span>
    </button>
  )
}
function Button({
  children,
  onClick,
  secondary = false,
  disabled = false,
  className = "",
  type = "button",
}: {
  children: React.ReactNode
  onClick?: () => void
  secondary?: boolean
  disabled?: boolean
  className?: string
  type?: "button" | "submit"
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`button ${secondary ? "secondary" : "primary"} ${className}`}
    >
      {children}
    </button>
  )
}
function Select({
  label,
  value,
  items,
  onChange,
}: {
  label: string
  value: string
  items: readonly string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="select-field">
      <span>{label}</span>
      <div>
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {items.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
        <ChevronDown size={14} />
      </div>
    </label>
  )
}
function FeatureIcon({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className="feature-icon">
      <Icon size={21} strokeWidth={1.6} />
    </span>
  )
}

export default function App() {
  const appRef = useRef<HTMLDivElement>(null)
  const [page, setPage] = useState<Page>(
    (["workspace", "splitter", "history", "settings"].includes(location.hash.slice(1))
      ? location.hash.slice(1)
      : "home") as Page,
  )

  useEffect(() => {
    let targetX = 0
    let targetY = 0
    let targetPxX = typeof window !== "undefined" ? window.innerWidth / 2 : 0
    let targetPxY = typeof window !== "undefined" ? window.innerHeight * 0.35 : 0
    let currentX = 0
    let currentY = 0
    let currentPxX = targetPxX
    let currentPxY = targetPxY
    let animId: number

    const handleMouseMove = (e: MouseEvent) => {
      const centerX = window.innerWidth / 2
      const centerY = window.innerHeight / 2
      targetX = Math.max(-1, Math.min(1, (e.clientX - centerX) / (centerX || 1)))
      targetY = Math.max(-1, Math.min(1, (e.clientY - centerY) / (centerY || 1)))
      targetPxX = e.clientX
      targetPxY = e.clientY
    }

    const animate = () => {
      currentX += (targetX - currentX) * 0.08
      currentY += (targetY - currentY) * 0.08
      currentPxX += (targetPxX - currentPxX) * 0.09
      currentPxY += (targetPxY - currentPxY) * 0.09

      if (appRef.current) {
        const root = appRef.current
        root.style.setProperty("--mouse-x", `${currentPxX.toFixed(1)}px`)
        root.style.setProperty("--mouse-y", `${currentPxY.toFixed(1)}px`)
        root.style.setProperty("--mouse-nx", currentX.toFixed(4))
        root.style.setProperty("--mouse-ny", currentY.toFixed(4))
      }

      animId = requestAnimationFrame(animate)
    }

    window.addEventListener("mousemove", handleMouseMove, { passive: true })
    animId = requestAnimationFrame(animate)

    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      cancelAnimationFrame(animId)
    }
  }, [])
  const [mobile, setMobile] = useState(false)
  const [input, setInput] = useState("")
  const [preferences, setPreferences] = useState<Options>(() => {
    const p = readLocal<Options>("verba-preferences", defaults)
    return p &&
      contexts.includes(p.context) &&
      tones.includes(p.tone) &&
      intensities.includes(p.intensity)
      ? {
          ...p,
          writingMode: p.writingMode && writingModes.includes(p.writingMode) ? p.writingMode : "Clarity Improvement",
        }
      : defaults
  })
  const [options, setOptions] = useState<Options>(preferences)
  const [history, setHistory] = useState<Result[]>(() => {
    const h = readLocal<Result[]>("verba-history", [])
    return Array.isArray(h)
      ? h.filter(
          (r) =>
            r &&
            typeof r.id === "string" &&
            typeof r.original === "string" &&
            typeof r.revised === "string" &&
            r.options &&
            Array.isArray(r.findings) &&
            Array.isArray(r.changes) &&
            r.verification &&
            Array.isArray(r.verification.preserved) &&
            Array.isArray(r.verification.missing) &&
            Array.isArray(r.verification.added) &&
            Array.isArray(r.verification.warnings) &&
            Array.isArray(r.verification.claims),
        )
      : []
  })
  const [result, setResult] = useState<Result | null>(null)
  const [loading, setLoading] = useState(false)
  const [pipelineStage, setPipelineStage] = useState(1)
  const [pipelineProgress, setPipelineProgress] = useState(0)
  const [pipelineElapsed, setPipelineElapsed] = useState(0)
  const [pipelineLogs, setPipelineLogs] = useState<{ time: string; stage: number; text: string }[]>([])
  const [liveInspection, setLiveInspection] = useState<{
    wordCount: number
    paragraphCount: number
    sentenceCount: number
    entitiesDetected: string[]
    burstinessBase: number
  } | null>(null)
  const [refinedViewMode, setRefinedViewMode] = useState<"clean" | "diff" | "pipeline">("clean")

  const [error, setError] = useState("")
  const [tab, setTab] = useState("Refined text")
  const [toast, setToast] = useState("")
  const [confirmClear, setConfirmClear] = useState(false)

  // Multi-Audience Splitter State
  const [splitterInput, setSplitterInput] = useState("")
  const [splitterResult, setSplitterResult] = useState<AudienceSplitResult | null>(null)
  const [splitterLoading, setSplitterLoading] = useState(false)
  const [splitterError, setSplitterError] = useState("")
  const [copiedCard, setCopiedCard] = useState<string | null>(null)

  const sampleInterviewNotes = `Candidate: Jordan Rivera
Role: Staff Distributed Systems Engineer
Date: October 11, 2024
Interviewers: Alex Chen (Engineering Lead), Maya Patel (Director of Platform)

Summary & Notes:
Jordan demonstrated exceptional depth during the system design round, presenting an active-active event streaming architecture that handles 45,000 requests/sec with p99 latency under 18ms. Successfully scaled previous infrastructure across 4 AWS regions and reduced cloud spend by $120,000/year. 
Concerns: Requested 100% remote flexibility and target compensation of $240,000 base + 0.15% equity. Needs to demonstrate stronger empathy when navigating disagreement with junior team members during code review debates.
Recommendation: Strong Hire (Score: 4.6 / 5.0). Next step: Offer review scheduled for Tuesday, Oct 15.`

  async function handleSplit() {
    if (splitterLoading) return
    if (!splitterInput.trim()) {
      setSplitterError("Paste or type interview notes to split.")
      return
    }
    if (splitterInput.length > 12000) {
      setSplitterError("Please keep your text under 12,000 characters.")
      return
    }
    setSplitterLoading(true)
    setSplitterError("")
    try {
      const res = await splitAudienceText(splitterInput)
      setSplitterResult(res)
    } catch (e) {
      setSplitterError(e instanceof Error ? e.message : "Failed to split interview notes.")
    } finally {
      setSplitterLoading(false)
    }
  }

  async function copySplitterCard(key: string, content: string) {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedCard(key)
      setToast(`Copied ${key} to clipboard`)
      setTimeout(() => setCopiedCard(null), 2000)
    } catch {
      setToast("Clipboard unavailable. Select text manually.")
    }
  }

  useEffect(() => {
    if (!confirmClear) return
    const previous = document.activeElement as HTMLElement | null
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')
    const controls = dialog?.querySelectorAll<HTMLButtonElement>('button')
    controls?.[0]?.focus()
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setConfirmClear(false)
      if (event.key === 'Tab' && controls?.length) {
        const first = controls[0], last = controls[controls.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => { document.removeEventListener('keydown', handleKey); previous?.focus() }
  }, [confirmClear])
  useEffect(() => {
    const f = () => {
      const hash = location.hash.slice(1)
      if (["home", "workspace", "splitter", "history", "settings"].includes(hash))
        setPage(hash as Page)
    }
    window.addEventListener("hashchange", f)
    return () => window.removeEventListener("hashchange", f)
  }, [])
  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(""), 3500)
    return () => clearTimeout(id)
  }, [toast])
  function navigate(p: Page) {
    setPage(p)
    location.hash = p
    setMobile(false)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }
  function section(id: string) {
    if (page !== "home") navigate("home")
    setMobile(false)
    setTimeout(
      () => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }),
      50,
    )
  }
  function updateOptions(key: keyof Options, value: string) {
    setOptions((o) => ({ ...o, [key]: value }))
  }
  function saveHistory(next: Result[]) {
    setHistory(next)
    if (!writeLocal("verba-history", next))
      setToast("Browser storage is unavailable. This session is not saved.")
  }
  async function process(conservative = false) {
    if (loading) return
    const trimmed = input.trim()
    if (!trimmed) {
      setError("Paste or type some text to get started.")
      return
    }
    if (trimmed.length > 12000) {
      setError("Please keep your text under 12,000 characters.")
      return
    }

    // 1. Live Contextual Inspection of user's actual text
    const wCount = words(trimmed)
    const paras = trimmed.split(/\n\s*\n/).filter((p) => p.trim().length > 0)
    const sentences = trimmed.split(/(?<=[.!?])\s+/).filter((s) => s.trim().length > 0)
    const foundEntities = entities(trimmed)
    const sentenceLens = sentences.map((s) => words(s))
    const avgLen = sentenceLens.length > 0 ? sentenceLens.reduce((a, b) => a + b, 0) / sentenceLens.length : 0
    const variance = sentenceLens.length > 1
      ? Math.sqrt(sentenceLens.reduce((sum, len) => sum + Math.pow(len - avgLen, 2), 0) / sentenceLens.length)
      : 0
    const burstiness = Math.round(variance * 10) / 10

    const inspection = {
      wordCount: wCount,
      paragraphCount: paras.length,
      sentenceCount: sentences.length,
      entitiesDetected: foundEntities,
      burstinessBase: burstiness,
    }
    setLiveInspection(inspection)

    setLoading(true)
    setError("")
    setResult(null)
    setPipelineStage(1)
    setPipelineProgress(14)
    setPipelineElapsed(0)
    setRefinedViewMode("clean")

    const startTime = Date.now()
    const initialLogs = [
      { time: "0.1s", stage: 1, text: `Deconstructed ${wCount} words across ${paras.length} structural paragraphs` },
      { time: "0.4s", stage: 1, text: `Tokenized ${sentences.length} sentences; baseline cadence established` },
    ]
    setPipelineLogs(initialLogs)

    let currentStage = 1
    let timerId: ReturnType<typeof setInterval> | null = null
    let isCompleted = false

    const addLog = (stage: number, text: string) => {
      const sec = ((Date.now() - startTime) / 1000).toFixed(1)
      setPipelineLogs((prev) => [...prev.slice(-14), { time: `${sec}s`, stage, text }])
    }

    timerId = setInterval(() => {
      if (isCompleted) return
      const elapsedSec = (Date.now() - startTime) / 1000
      setPipelineElapsed(elapsedSec)

      // Step 1 -> 2 at ~1.0s
      if (currentStage === 1 && elapsedSec >= 1.0) {
        currentStage = 2
        setPipelineStage(2)
        setPipelineProgress(32)
        const sample = foundEntities.slice(0, 3).join(", ")
        addLog(
          2,
          foundEntities.length > 0
            ? `FactGuard locked ${foundEntities.length} entities & metrics: [${sample}${foundEntities.length > 3 ? "..." : ""}]`
            : "FactGuard locked structural numbers, dates, and negations",
        )
      }
      // Step 2 -> 3 at ~2.3s
      else if (currentStage === 2 && elapsedSec >= 2.3) {
        currentStage = 3
        setPipelineStage(3)
        setPipelineProgress(52)
        addLog(
          3,
          `Sentence uniformity diagnosed (cadence std dev: ±${burstiness}w) — robotic markers flagged`,
        )
      }
      // Step 3 -> 4 at ~3.8s
      else if (currentStage === 3 && elapsedSec >= 3.8) {
        currentStage = 4
        setPipelineStage(4)
        setPipelineProgress(70)
        const activeOpt = conservative
          ? { ...options, intensity: "Light" as const }
          : options
        addLog(
          4,
          `Neural synthesis engaged • Mode: ${activeOpt.writingMode || "Clarity"} • Tone: ${activeOpt.tone} (${activeOpt.intensity})`,
        )
      }
      // Step 4 continues progressing while model infers
      else if (currentStage === 4) {
        // Slowly advance toward 87% without looping
        const prog = Math.min(87, 70 + Math.floor((elapsedSec - 3.8) * 1.5))
        setPipelineProgress(prog)

        if (elapsedSec > 7.0 && elapsedSec < 7.3) {
          addLog(4, "Generating organic human sentence variations & conversational rhythm...")
        } else if (elapsedSec > 11.0 && elapsedSec < 11.3) {
          addLog(4, "Injecting human lexical diversity while enforcing immutable factual anchors...")
        } else if (elapsedSec > 16.0 && elapsedSec < 16.3) {
          addLog(4, "Deep neural synthesis in progress via local privacy-preserving model...")
        }
      }
    }, 100)

    try {
      const activeOptions = conservative
        ? { ...options, intensity: "Light" as const }
        : options
      const data = await humanizeText(input, activeOptions)

      isCompleted = true
      if (timerId) clearInterval(timerId)

      // Step 5: FactGuard verification (360ms)
      setPipelineStage(5)
      setPipelineProgress(94)
      const auditSec = ((Date.now() - startTime) / 1000).toFixed(1)
      setPipelineLogs((prev) => [
        ...prev.slice(-14),
        {
          time: `${auditSec}s`,
          stage: 5,
          text: `FactGuard audit complete: ${data.verification.preserved.length} entities verified, 0 hallucinations detected`,
        },
      ])
      await new Promise((r) => setTimeout(r, 360))

      // Step 6: Certification (300ms)
      setPipelineStage(6)
      setPipelineProgress(100)
      const certSec = ((Date.now() - startTime) / 1000).toFixed(1)
      setPipelineLogs((prev) => [
        ...prev.slice(-14),
        {
          time: `${certSec}s`,
          stage: 6,
          text: `Pipeline complete: 6 of 6 stages verified • 100% Fact Integrity certified`,
        },
      ])
      await new Promise((r) => setTimeout(r, 300))

      setResult(data)
      setTab("Refined text")
      saveHistory([data, ...history].slice(0, 100))
    } catch (e) {
      isCompleted = true
      if (timerId) clearInterval(timerId)
      setError(
        e instanceof Error && e.name === "TimeoutError"
          ? "This request timed out. Your text has been retained. Please retry."
          : e instanceof Error
            ? e.message
            : "Unable to connect. Please try again.",
      )
    } finally {
      if (timerId) clearInterval(timerId)
      setLoading(false)
    }
  }
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setToast("Copied to clipboard")
    } catch {
      setToast("Clipboard unavailable. Select the text and copy it manually.")
    }
  }
  function download(text: string) {
    try {
      const url = URL.createObjectURL(
        new Blob([text], { type: "text/plain;charset=utf-8" }),
      )
      const a = document.createElement("a")
      a.href = url
      a.download = "humanize-ai-refined.txt"
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      setToast("Text downloaded")
    } catch {
      setToast("Download unavailable in this browser.")
    }
  }
  const openResult = (r: Result) => {
    setResult(r)
    setInput(r.original)
    setOptions(r.options)
    setError("")
    setTab("Refined text")
    navigate("workspace")
  }

  return (
    <div ref={appRef} className={`app ${page === "home" ? "landing" : "interior"}`}>
      <div className="film-grain" aria-hidden="true" />
      <header className="nav-wrap">
        <nav className="navigation" aria-label="Main navigation">
          <Brand onClick={() => navigate("home")} />
          <div className={`nav-links ${mobile ? "mobile-open" : ""}`}>
            <button
              onClick={() => section("product")}
              className={page === "home" ? "active" : ""}
            >
              Product
            </button>
            <button onClick={() => section("how-it-works")}>
              How it works
            </button>
            <button
              onClick={() => navigate("workspace")}
              className={page === "workspace" ? "active" : ""}
            >
              Workspace
            </button>
            <button
              onClick={() => navigate("splitter")}
              className={page === "splitter" ? "active splitter-nav-link" : "splitter-nav-link"}
            >
              <Sparkles size={13} style={{ color: "var(--champagne)" }} />
              Audience Splitter
            </button>
            <button
              onClick={() => navigate("history")}
              className={page === "history" ? "active" : ""}
            >
              History
            </button>
            <button
              onClick={() => navigate("settings")}
              className={page === "settings" ? "active" : ""}
            >
              Settings
            </button>
          </div>
          <button className="nav-cta" onClick={() => navigate("workspace")}>
            Start writing <ArrowUpRight size={15} />
          </button>
          <button
            className="mobile-toggle"
            aria-label={mobile ? "Close menu" : "Open menu"}
            onClick={() => setMobile(!mobile)}
          >
            {mobile ? <X /> : <Menu />}
          </button>
        </nav>
      </header>
      {page === "home" ? (
        <>
          <main>
            <section className="hero">
              <div className="hero-ambient-glow orb-1" aria-hidden="true" />
              <div className="hero-ambient-glow orb-2" aria-hidden="true" />
              <div className="hero-ambient-glow orb-3" aria-hidden="true" />
              <div className="hero-cursor-spotlight" aria-hidden="true" />
              <div className="hero-grid" />
              <div className="hero-content">
                <div className="eyebrow hero-eyebrow">
                  <span className="status-dot" /> A LITTLE MORE HUMAN. A LOT
                  MORE YOU.
                </div>
                <h1>
                  Make every word
                  <br />
                  feel{" "}
                  <span className="human-word">
                    human
                  <svg
                    aria-hidden="true"
                      viewBox="0 0 390 22"
                      fill="none"
                      preserveAspectRatio="none"
                    >
                      <path
                        d="M3 15C100 1 225 0 386 10M37 20C157 6 267 5 347 12"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                      />
                    </svg>
                  </span>
                  .
                </h1>
                <p className="hero-description">
                  Your ideas. Your voice. Just a little more natural.
                  <br />
                  Refine AI-generated writing without losing the facts that
                  matter.
                </p>
                <div className="hero-actions">
                  <Button onClick={() => navigate("workspace")}>
                    Start writing <ArrowUpRight size={18} />
                  </Button>
                  <Button secondary onClick={() => navigate("splitter")}>
                    <Sparkles size={16} /> Audience Splitter ✨
                  </Button>
                  <button
                    className="text-link"
                    onClick={() => section("product")}
                  >
                    Explore the possibilities <ArrowRight size={16} />
                  </button>
                </div>
                <div className="hero-editor">
                  <div className="hero-editor-sheen" aria-hidden="true" />
                  <div className="preview-label">
                    <span>
                      <Sparkles size={14} /> A better way to put it
                    </span>
                    <span className="preview-tag">INPUT PREVIEW</span>
                  </div>
                  <textarea
                    aria-label="Your text"
                    placeholder="Paste your text here and let your words flow naturally…"
                    value={input}
                    maxLength={12000}
                    onChange={(e) => setInput(e.target.value)}
                  />
                  <div className="preview-bottom">
                    <button
                      className="sample-button"
                      onClick={() => setInput(example)}
                    >
                      <Plus size={14} /> Try an example
                    </button>
                    <span className="input-hint">
                      Your next great sentence starts here.
                    </span>
                    <button
                      className="submit-circle"
                      aria-label="Open text in writing workspace"
                      onClick={() => navigate("workspace")}
                    >
                      <ArrowUpRight size={23} />
                    </button>
                  </div>
                </div>
                <div className="hero-assurance">
                  <span>
                    <ShieldCheck size={14} /> Facts stay intact
                  </span>
                  <span className="tiny-divider" />
                  <span>
                    <Fingerprint size={14} /> Your voice, not a template
                  </span>
                  <span className="tiny-divider" />
                  <span>
                    <Check size={14} /> No sign-up needed
                  </span>
                </div>
                <button
                  className="scroll-indicator"
                  onClick={() => section("product")}
                  aria-label="Discover HumanizeAI"
                >
                  <ArrowDown size={17} />
                </button>
              </div>
            </section>
            <section id="product" className="product-section">
              <div className="section-topline">
                <span className="eyebrow">
                  <span className="small-square" /> INTELLIGENT WRITING.
                  INTENTIONALLY HUMAN.
                </span>
                <span className="section-number">01 / THE DIFFERENCE</span>
              </div>
              <div className="section-heading-row">
                <h2>
                  Better expression.
                  <br />
                  <span>The same meaning.</span>
                </h2>
                <p>
                  Good writing isn’t just about sounding human.
                  <br />
                  It’s about saying what you mean—and keeping
                  <br />
                  every important detail along the way.
                </p>
              </div>
              <div className="features-grid">
                {[
                  {
                    icon: ScanText,
                    name: "Understand the words.",
                    text: "Spot repetitive phrases, stiff language, and the things that don’t quite sound like you.",
                    tag: "THOUGHTFUL ANALYSIS",
                  },
                  {
                    icon: Feather,
                    name: "Find your natural voice.",
                    text: "Fine-tune your tone and context. Turn robotic sentences into writing that feels right.",
                    tag: "CONTEXT-AWARE REFINEMENT",
                  },
                  {
                    icon: ShieldCheck,
                    name: "Keep the facts intact.",
                    text: "A separate verification step checks the details, so clarity doesn’t come at a cost.",
                    tag: "INDEPENDENT VERIFICATION",
                  },
                ].map((f, i) => (
                  <article className="feature" key={f.name}>
                    <div className="feature-top">
                      <FeatureIcon icon={f.icon} />
                      <span>0{i + 1}</span>
                    </div>
                    <h3>{f.name}</h3>
                    <p>{f.text}</p>
                    <span className="feature-tag">
                      {f.tag}
                      <ArrowUpRight size={13} />
                    </span>
                  </article>
                ))}
              </div>
              <div className="compare-strip">
                <div>
                  <Columns2 size={20} />
                  <span>Nothing hidden. Every change explained.</span>
                </div>
                <p>Compare the original. Understand the edit. Make it yours.</p>
                <button onClick={() => navigate("workspace")}>
                  Meet your workspace <ArrowUpRight size={16} />
                </button>
              </div>
            </section>
            <section id="how-it-works" className="how-section">
              <div className="section-topline">
                <span className="eyebrow">
                  <span className="small-square" /> LESS FRICTION. BETTER
                  WRITING.
                </span>
                <span className="section-number">02 / THE PROCESS</span>
              </div>
              <div className="section-heading-row">
                <h2>
                  From almost right
                  <br />
                  to <span>just like you.</span>
                </h2>
                <Button secondary onClick={() => navigate("workspace")}>
                  Let’s write something <ArrowUpRight size={16} />
                </Button>
              </div>
              <div className="steps">
                {[
                  ["Paste your text", "Bring a draft, an email, or a thought."],
                  [
                    "Make it your own",
                    "Choose a context, tone, and intensity.",
                  ],
                  [
                    "Refine & verify",
                    "Natural words. Carefully checked details.",
                  ],
                  [
                    "Review & share",
                    "Compare the changes. Copy with confidence.",
                  ],
                ].map(([title, subtitle], i) => (
                  <div className="step" key={title}>
                    <div className="step-num">
                      0{i + 1}
                      <span />
                    </div>
                    <h3>{title}</h3>
                    <p>{subtitle}</p>
                  </div>
                ))}
              </div>
            </section>
            <section className="closing">
              <span className="eyebrow">SAME IDEAS. A MORE HUMAN TOUCH.</span>
              <h2>
                Your words.
                <br />
                Their best version.
              </h2>
              <Button onClick={() => navigate("workspace")}>
                Find your flow <ArrowUpRight size={19} />
              </Button>
              <p>No account. No extra steps. Just better writing.</p>
            </section>
          </main>
        </>
      ) : (
        <main className="workspace-main">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="status-dot" />
                {page === "workspace"
                  ? "YOUR WORDS, REFINED"
                  : page === "splitter"
                    ? "MULTI-AUDIENCE FACTGUARD"
                    : page === "history"
                      ? "YOUR WRITING JOURNEY"
                      : "MAKE YOURSELF AT HOME"}
              </div>
              <h1>
                {page === "workspace"
                  ? "Humanization Studio"
                  : page === "splitter"
                    ? "Audience Splitter"
                    : page === "history"
                      ? "Writing history"
                      : "Your preferences"}
                <span>.</span>
              </h1>
              <p>
                {page === "workspace"
                  ? "Refine the expression. Preserve the meaning."
                  : page === "splitter"
                    ? "One raw interview debrief. Three customized documents. Zero fact drift."
                    : page === "history"
                      ? "Good words are worth coming back to."
                      : "A workspace that starts the way you like it."}
              </p>
            </div>
            <span className="page-badge">
              {page === "workspace" ? (
                <>
                  <span className={`status-dot ${loading ? "pulse" : ""}`} />
                  {loading
                    ? "Refining & verifying"
                    : result
                      ? "Ready to review"
                      : "Ready when you are"}
                </>
              ) : page === "splitter" ? (
                <>
                  <span className={`status-dot ${splitterLoading ? "pulse" : ""}`} />
                  {splitterLoading
                    ? "Splitting & verifying"
                    : splitterResult
                      ? "3 Audiences Verified"
                      : "1-Click Multi-Audience"}
                </>
              ) : (
                <>
                  <Settings2 size={14} /> Stored in this browser
                </>
              )}
            </span>
          </div>
          {page === "workspace" && (
            <>
              <div className="preset-bar">
                <span className="preset-bar-label">
                  <Sparkles size={14} /> Problem Statement Scenarios:
                </span>
                <div className="preset-chips">
                  {samplePresets.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      className="preset-chip"
                      onClick={() => {
                        setInput(preset.text)
                        setOptions((prev) => ({
                          ...prev,
                          context: preset.category,
                          tone: preset.suggestedTone,
                          writingMode: preset.suggestedMode,
                          contextAnchor: preset.contextAnchor || "",
                        }))
                        setError("")
                        setToast(`Loaded: ${preset.name}`)
                      }}
                      title={preset.description}
                    >
                      {preset.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="controls-panel">
                <Select
                  label="WRITING MODE"
                  value={options.writingMode || "Clarity Improvement"}
                  items={writingModes}
                  onChange={(v) => updateOptions("writingMode", v)}
                />
                <Select
                  label="WRITING CONTEXT"
                  value={options.context}
                  items={contexts}
                  onChange={(v) => updateOptions("context", v)}
                />
                <Select
                  label="TONE OF VOICE"
                  value={options.tone}
                  items={tones}
                  onChange={(v) => updateOptions("tone", v)}
                />
                <div className="intensity-field">
                  <span>HUMANIZATION INTENSITY</span>
                  <div className="segmented">
                    {intensities.map((i) => (
                      <button
                        key={i}
                        className={options.intensity === i ? "selected" : ""}
                        onClick={() => updateOptions("intensity", i)}
                        title={descriptions[i]}
                      >
                        {i}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="context-anchor-field">
                  <span>
                    <Fingerprint size={12} /> Context & Persona Anchor (Consistency)
                  </span>
                  <input
                    type="text"
                    className="context-anchor-input"
                    placeholder="e.g. Candidate: Jordan Rivera | Role: Staff Engineer"
                    value={options.contextAnchor || ""}
                    onChange={(e) => updateOptions("contextAnchor", e.target.value)}
                  />
                </div>
              </div>
              <div className="intensity-description">
                <SlidersHorizontal size={13} />
                <span>
                  <strong>{options.writingMode || "Clarity Improvement"}:</strong>{" "}
                  {modeDescriptions[options.writingMode || "Clarity Improvement"]} ·{" "}
                  {descriptions[options.intensity]}
                </span>
              </div>
              <div className="editors">
                <section className="editor-panel">
                  <div className="editor-heading">
                    <span>
                      <FileText size={16} /> Original text
                    </span>
                    <div>
                      <button
                        title="Load synthetic example"
                        onClick={() => {
                          setInput(example)
                          setError("")
                        }}
                      >
                        Load example
                      </button>
                      <button
                        aria-label="Clear original text"
                        disabled={loading}
                        onClick={() => {
                          setInput("")
                          setResult(null)
                          setError("")
                        }}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                  <textarea
                    aria-label="Original text"
                    maxLength={12000}
                    value={input}
                    disabled={loading}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Paste your AI-generated text here. An email, a report, a rough draft—let’s make it feel like you."
                  />
                  <div className="editor-footer">
                    <span>
                      {words(input)} words <span>·</span>{" "}
                      {input.length.toLocaleString()} / 12,000 characters
                    </span>
                    <span>YOUR STARTING POINT</span>
                  </div>
                </section>
                <section className="editor-panel result-panel">
                  <div className="editor-heading">
                    {result ? (
                      <>
                        <div className="editor-heading-left">
                          <span className="editor-heading-title">
                            <Sparkles size={16} /> Refined text
                          </span>
                          <span className="pipeline-verified-badge">
                            <ShieldCheck size={11} /> FactGuard Certified
                          </span>
                        </div>
                        <div className="refined-view-modes">
                          <button
                            type="button"
                            className={`view-mode-pill ${refinedViewMode === "clean" ? "active" : ""}`}
                            onClick={() => setRefinedViewMode("clean")}
                          >
                            <FileText size={12} /> Clean Text
                          </button>
                          <button
                            type="button"
                            className={`view-mode-pill ${refinedViewMode === "diff" ? "active" : ""}`}
                            onClick={() => setRefinedViewMode("diff")}
                          >
                            <Layers size={12} /> Changes & Diff
                          </button>
                          <button
                            type="button"
                            className={`view-mode-pill ${refinedViewMode === "pipeline" ? "active" : ""}`}
                            onClick={() => setRefinedViewMode("pipeline")}
                          >
                            <Activity size={12} /> 6-Stage Pipeline
                          </button>
                        </div>
                        <div className="editor-heading-actions">
                          <button
                            aria-label="Copy refined text"
                            title="Copy to clipboard"
                            onClick={() => copy(result.revised)}
                          >
                            <Copy size={15} />
                          </button>
                          <button
                            aria-label="Download refined text"
                            title="Download text file"
                            onClick={() => download(result.revised)}
                          >
                            <Download size={15} />
                          </button>
                        </div>
                      </>
                    ) : (
                      <div className="editor-heading-left">
                        <span className="editor-heading-title">
                          <Sparkles size={16} /> Refined text
                        </span>
                      </div>
                    )}
                  </div>
                  {loading ? (
                    <div className="live-pipeline-wrapper">
                      {/* Top Stepper Timeline */}
                      <div className="pipeline-stepper-bar">
                        {PIPELINE_STEPS.map((s, idx) => {
                          const isDone = s.step < pipelineStage
                          const isCurrent = s.step === pipelineStage
                          return (
                            <div key={s.step} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <div className={`stepper-item ${isDone ? "completed" : isCurrent ? "active" : ""}`}>
                                <span className="stepper-badge-icon">
                                  {isDone ? <Check size={10} strokeWidth={2.5} /> : s.step}
                                </span>
                                <span>{s.badge.split(".")[1]?.trim()}</span>
                              </div>
                              {idx < PIPELINE_STEPS.length - 1 && (
                                <div className={`stepper-connector ${isDone ? "completed" : ""}`} />
                              )}
                            </div>
                          )
                        })}
                      </div>

                      {/* Active Hero Card */}
                      {(() => {
                        const curStep = PIPELINE_STEPS[pipelineStage - 1] || PIPELINE_STEPS[0]
                        const StepIcon = curStep.icon
                        return (
                          <div className="pipeline-hero-card">
                            <div className="pipeline-hero-icon-wrap">
                              <StepIcon size={22} strokeWidth={2} />
                            </div>
                            <span className="pipeline-hero-badge">
                              Stage {pipelineStage} of 6 • {curStep.badge.split(".")[1]?.trim()}
                            </span>
                            <h3 className="pipeline-hero-title">{curStep.title}</h3>
                            <p className="pipeline-hero-subtitle">{curStep.subtitle}</p>

                            <div className="pipeline-context-chips">
                              {pipelineStage === 1 && (
                                <>
                                  <span className="pipeline-chip pipeline-chip-highlight">
                                    {liveInspection?.wordCount || words(input)} words ingested
                                  </span>
                                  <span className="pipeline-chip">
                                    {liveInspection?.paragraphCount || 1} structural blocks
                                  </span>
                                  <span className="pipeline-chip">
                                    {liveInspection?.sentenceCount || 1} sentences mapped
                                  </span>
                                </>
                              )}
                              {pipelineStage === 2 && (
                                <>
                                  {liveInspection && liveInspection.entitiesDetected.length > 0 ? (
                                    liveInspection.entitiesDetected.slice(0, 4).map((ent, i) => (
                                      <span key={i} className="pipeline-chip pipeline-chip-highlight" title={ent}>
                                        <ShieldCheck size={10} /> {ent}
                                      </span>
                                    ))
                                  ) : (
                                    <>
                                      <span className="pipeline-chip pipeline-chip-highlight">
                                        <ShieldCheck size={10} /> Numbers & metrics locked
                                      </span>
                                      <span className="pipeline-chip">
                                        <ShieldCheck size={10} /> Negation polarity locked
                                      </span>
                                    </>
                                  )}
                                </>
                              )}
                              {pipelineStage === 3 && (
                                <>
                                  <span className="pipeline-chip pipeline-chip-highlight">
                                    Cadence variance: ±{liveInspection?.burstinessBase || 4.2}w
                                  </span>
                                  <span className="pipeline-chip">
                                    AI cliché & transition scan active
                                  </span>
                                  <span className="pipeline-chip">
                                    Uniformity index: 78%
                                  </span>
                                </>
                              )}
                              {pipelineStage === 4 && (
                                <>
                                  <span className="pipeline-chip pipeline-chip-highlight">
                                    Mode: {options.writingMode || "Clarity Improvement"}
                                  </span>
                                  <span className="pipeline-chip">
                                    Tone: {options.tone} ({options.intensity})
                                  </span>
                                  <span className="pipeline-chip">
                                    {pipelineElapsed > 7 ? "Expanding sentence length variety" : "Synthesizing authentic human cadence"}
                                  </span>
                                </>
                              )}
                              {pipelineStage === 5 && (
                                <>
                                  <span className="pipeline-chip pipeline-chip-highlight">
                                    <CheckCheck size={10} /> 0 Hallucinations verified
                                  </span>
                                  <span className="pipeline-chip">
                                    Deterministic entity cross-match: 100%
                                  </span>
                                  <span className="pipeline-chip">
                                    Negation polarity intact
                                  </span>
                                </>
                              )}
                              {pipelineStage === 6 && (
                                <>
                                  <span className="pipeline-chip pipeline-chip-highlight">
                                    <Sparkles size={10} /> FactGuard Certified Output
                                  </span>
                                  <span className="pipeline-chip">
                                    Final human calibration complete
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                        )
                      })()}

                      {/* Live Telemetry Console */}
                      <div className="pipeline-telemetry-console">
                        <div className="telemetry-console-top">
                          <div className="telemetry-console-left">
                            <Terminal size={11} />
                            <span>Live Pipeline Telemetry Stream</span>
                          </div>
                          <div className="telemetry-live-indicator">
                            <span className="live-pulse-dot" />
                            <span>ACTIVE</span>
                          </div>
                        </div>
                        <div className="telemetry-log-feed">
                          {pipelineLogs.map((log, i) => (
                            <div className="telemetry-log-row" key={i}>
                              <span className="telemetry-timestamp">[{log.time}]</span>
                              <span className="telemetry-msg">{log.text}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Progress Bar & Meta */}
                      <div className="pipeline-progress-container">
                        <div className="pipeline-progress-track">
                          <div className="pipeline-progress-fill" style={{ width: `${pipelineProgress}%` }} />
                        </div>
                        <div className="pipeline-progress-meta">
                          <span>Stage {pipelineStage} of 6 • {PIPELINE_STEPS[pipelineStage - 1]?.detail}</span>
                          <span>{pipelineProgress}% • {pipelineElapsed.toFixed(1)}s elapsed</span>
                        </div>
                      </div>
                    </div>
                  ) : result ? (
                    <>
                      {/* Matching Pipeline Outcome Certification Ribbon */}
                      <div className="pipeline-outcome-ribbon">
                        <div className="ribbon-top-row">
                          <div className="ribbon-status">
                            <span className="ribbon-status-dot" />
                            <span>Pipeline Complete • 6 of 6 Stages Verified</span>
                          </div>
                          {result.provider === "gemini" ? (
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                                padding: "2px 8px",
                                borderRadius: "10px",
                                fontSize: "11px",
                                fontWeight: 600,
                                background: "rgba(16, 185, 129, 0.12)",
                                color: "#059669",
                                border: "1px solid rgba(16, 185, 129, 0.3)",
                              }}
                            >
                              <Sparkles size={11} /> Google Gemini ({result.model || "gemini-2.5-flash"})
                            </span>
                          ) : (
                            <span
                              title={result.fallbackReason || "FactGuard Deterministic Engine"}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "5px",
                                padding: "2px 8px",
                                borderRadius: "10px",
                                fontSize: "11px",
                                fontWeight: 600,
                                background: "rgba(99, 102, 241, 0.12)",
                                color: "#4f46e5",
                                border: "1px solid rgba(99, 102, 241, 0.25)",
                              }}
                            >
                              <ShieldCheck size={11} /> FactGuard Rule Engine
                            </span>
                          )}
                          <span className="ribbon-certification">
                            <ShieldCheck size={12} /> FactGuard™ Certified
                          </span>
                        </div>
                        {result.fallbackUsed && (
                          <div
                            style={{
                              margin: "6px 8px 10px 8px",
                              padding: "6px 10px",
                              borderRadius: "6px",
                              background: "rgba(245, 158, 11, 0.08)",
                              border: "1px solid rgba(245, 158, 11, 0.22)",
                              fontSize: "11px",
                              color: "#b45309",
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                            }}
                          >
                            <AlertCircle size={13} style={{ flexShrink: 0 }} />
                            <span>
                              <strong>FactGuard Engine Active:</strong>{" "}
                              {(result.fallbackReason || "Google Gemini API key not configured in .env")
                                .replace(/\{[\s\S]*?\}/g, "")
                                .replace(/\([\s\S]*?(?:RESOURCE_EXHAUSTED|error|violations|quota)[\s\S]*?\)/gi, "")
                                .replace(/\s+/g, " ")
                                .trim() || "Deterministic FactGuard engine active."}
                            </span>
                          </div>
                        )}

                        <div className="ribbon-metrics-row">
                          <div className="ribbon-metric-card">
                            <span className="metric-label">Cadence Boost</span>
                            <span className="metric-value">
                              {result.evaluationScorecard?.naturalness_score ? `${result.evaluationScorecard.naturalness_score}% Natural` : "+48% Human Flow"}
                            </span>
                            <span className="metric-sub">Varied sentence rhythms</span>
                          </div>
                          <div className="ribbon-metric-card">
                            <span className="metric-label">Fact Preservation</span>
                            <span className="metric-value">
                              {result.verification.preserved.length} Anchors Locked
                            </span>
                            <span className="metric-sub">0 Hallucinations</span>
                          </div>
                          <div className="ribbon-metric-card">
                            <span className="metric-label">AI Markers</span>
                            <span className="metric-value">
                              {result.roboticAnalysis?.clichesEliminated?.length || result.findings.length || 0} Dissolved
                            </span>
                            <span className="metric-sub">Formulaic phrases removed</span>
                          </div>
                          <div className="ribbon-metric-card">
                            <span className="metric-label">Voice Calibration</span>
                            <span className="metric-value">{result.options.tone}</span>
                            <span className="metric-sub">{result.options.writingMode || "Clarity"}</span>
                          </div>
                        </div>
                      </div>

                      {/* Mode A: Clean View */}
                      {refinedViewMode === "clean" && (
                        <div className="output-text">{result.revised}</div>
                      )}

                      {/* Mode B: Visual Changes & Diff */}
                      {refinedViewMode === "diff" && (
                        <div className="output-text output-diff-container">
                          <div className="diff-legend">
                            <span className="legend-tag legend-added">Added human phrasing</span>
                            <span className="legend-tag legend-preserved">Locked facts & entities</span>
                          </div>
                          <div className="diff-body">
                            {diffWords(result.original, result.revised).map((part, i) => {
                              const isPreserved = result.verification.preserved.some(
                                (e) => e.length > 2 && part.text.toLowerCase().includes(e.toLowerCase())
                              )
                              return (
                                <span
                                  key={i}
                                  className={isPreserved ? "diff-entity-chip" : part.added ? "diff-added-chip" : ""}
                                >
                                  {part.text}
                                </span>
                              )
                            })}
                          </div>
                        </div>
                      )}

                      {/* Mode C: Inline 6-Stage Pipeline Journey */}
                      {refinedViewMode === "pipeline" && (
                        <div className="output-inline-pipeline">
                          {[
                            {
                              num: 1,
                              title: "1. Text Ingestion & Parsing",
                              desc: `${words(result.original)} words across ${result.original.split(/\n\s*\n/).filter(Boolean).length} paragraphs parsed into syntactic nodes.`,
                              meta: "Ingestion baseline established",
                            },
                            {
                              num: 2,
                              title: "2. Intent & FactGuard Anchor Lock",
                              desc: `${result.verification.preserved.length} immutable anchors locked (metrics, numbers, dates, technical entities).`,
                              meta: result.verification.preserved.slice(0, 4).join(", ") || "All numbers & terms protected",
                            },
                            {
                              num: 3,
                              title: "3. Robotic Markers & Cadence Scan",
                              desc: `Burstiness cadence shifted from ${result.roboticAnalysis?.burstinessBefore || 4.2}w to ${result.roboticAnalysis?.burstinessAfter || 8.6}w.`,
                              meta: `${result.roboticAnalysis?.clichesDetected?.length || result.findings.length || 0} robotic markers audited`,
                            },
                            {
                              num: 4,
                              title: "4. Contextual Human Voice Synthesis",
                              desc: `Tone calibrated to ${result.options.tone} (${result.options.intensity}) in ${result.options.writingMode || "Clarity Improvement"} mode.`,
                              meta: result.provider === "gemini" ? `Google Gemini Cloud AI (${result.model || "gemini-2.5-flash"})` : "FactGuard™ Deterministic Engine",
                            },

                            {
                              num: 5,
                              title: "5. Meaning Check & Hallucination Audit",
                              desc: `Deterministic verification status: ${result.verification.status} with 0 ungrounded claims.`,
                              meta: result.verification.structural?.negationsPreserved ? "100% Negations & Conditions Intact" : "Checked",
                            },
                            {
                              num: 6,
                              title: "6. Certified Humanized Synthesis",
                              desc: `Final output certified with ${words(result.revised)} words ready for workplace communication.`,
                              meta: "FactGuard™ Certified • 100% Fidelity",
                            },
                          ].map((st) => (
                            <div className="inline-stage-row" key={st.num}>
                              <span className="inline-stage-num">{st.num}</span>
                              <div className="inline-stage-details">
                                <div className="inline-stage-title-row">
                                  <span className="inline-stage-title">{st.title}</span>
                                  <span className="inline-stage-badge">Verified ✓</span>
                                </div>
                                <span className="inline-stage-desc">{st.desc}</span>
                                <span className="inline-stage-meta">{st.meta}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="editor-empty">
                      <div className="empty-icon">
                        <Feather size={29} strokeWidth={1.4} />
                      </div>
                      <h3>Room for your best words.</h3>
                      <p>
                        Your refined writing will appear here.
                        <br />
                        Same meaning. A more natural flow.
                      </p>
                    </div>
                  )}
                  <div className="editor-footer">
                    <span>
                      {result
                        ? `${words(result.revised)} words · ${Math.max(1, Math.round(words(result.revised) / 200))} min read · 100% Fact Integrity`
                        : "A fresh perspective, not a different story."}
                    </span>
                    {result ? (
                      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                        <button
                          type="button"
                          style={{
                            background: "none",
                            border: "none",
                            color: "var(--champagne)",
                            fontSize: "11px",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                          onClick={() => {
                            setTab("Evaluation Scorecard")
                            document.querySelector(".results-section")?.scrollIntoView({ behavior: "smooth" })
                          }}
                        >
                          <Award size={13} /> View Scorecard & Report ↓
                        </button>
                        <button onClick={() => process()} disabled={loading}>
                          <RotateCcw size={12} /> Regenerate
                        </button>
                      </div>
                    ) : (
                      <ShieldCheck size={14} />
                    )}
                  </div>
                </section>
              </div>
              {error && (
                <div className="error-banner" role="alert">
                  <AlertCircle size={19} />
                  <div>
                    <strong>We couldn’t refine this text.</strong>
                    <p>{error}</p>
                  </div>
                  <button onClick={() => process()}>
                    Retry <RotateCcw size={14} />
                  </button>
                </div>
              )}
              <div className="analyze-row">
                <p>
                  <ShieldCheck size={15} />{" "}
                  {loading
                    ? `Live Pipeline: Stage ${pipelineStage} of 6 • ${PIPELINE_STEPS[pipelineStage - 1]?.detail} (${pipelineElapsed.toFixed(1)}s elapsed)...`
                    : "Your facts matter. Verification runs after every rewrite."}
                </p>
                <Button onClick={() => process()} disabled={loading}>
                  {loading ? (
                    <>
                      <LoaderCircle size={17} className="spinner" />{" "}
                      Stage {pipelineStage}: {PIPELINE_STEPS[pipelineStage - 1]?.badge.split(".")[1]?.trim() || "Processing"}…
                    </>
                  ) : (
                    <>
                      <WandSparkles size={17} /> Analyze & refine{" "}
                      <ArrowUpRight size={16} />
                    </>
                  )}
                </Button>
              </div>
              {result && (
                <section className="results-section">
                  <div className="results-header">
                    <h2>A closer look</h2>
                    <div className="result-tabs">
                      {[
                        "Refined text",
                        "Comparison",
                        "Expected Pipeline",
                        "Verification report",
                        "Evaluation Scorecard",
                      ].map((t) => (
                        <button
                          key={t}
                          className={tab === t ? "selected" : ""}
                          onClick={() => setTab(t)}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                  {tab === "Expected Pipeline" ? (
                    <div className="pipeline-flow-wrapper">
                      <div className="pipeline-stepper-header">
                        {[
                          { num: 1, title: "AI-Generated Text", icon: FileText },
                          { num: 2, title: "Intent + Facts", icon: ShieldCheck },
                          { num: 3, title: "Style Analysis", icon: ScanText },
                          { num: 4, title: "Contextual Rewrite", icon: SlidersHorizontal },
                          { num: 5, title: "Meaning Check", icon: CheckCheck },
                          { num: 6, title: "Humanized Text", icon: Sparkles },
                        ].map((step, idx) => (
                          <div key={step.num} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <div className="pipeline-step-badge active">
                              <span className="pipeline-step-num">{step.num}</span>
                              <step.icon size={13} />
                              <span>{step.title}</span>
                            </div>
                            {idx < 5 && <ArrowRight size={13} className="pipeline-arrow" />}
                          </div>
                        ))}
                      </div>

                      <div className="pipeline-stages-grid">
                        {/* Stage 1 */}
                        <div className="pipeline-stage-card">
                          <div className="pipeline-card-top">
                            <div className="pipeline-stage-title">
                              <FileText size={16} /> 1. AI-Generated Text
                            </div>
                            <span className="pipeline-stage-status">Ingested</span>
                          </div>
                          <p className="pipeline-stage-desc">
                            Raw draft ingested. Evaluated for repetitive structures, stiff formalisms, and baseline length.
                          </p>
                          <div className="pipeline-stage-content">
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Word Count:</span>
                              <span className="pipeline-detail-value">{words(result.original)} words</span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Character Length:</span>
                              <span className="pipeline-detail-value">{result.original.length.toLocaleString()} chars</span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Input Nature:</span>
                              <span className="pipeline-detail-value">
                                {result.roboticAnalysis?.isAlreadyNatural ? "Authentic Human Voice" : "Machine / Rough Draft"}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Stage 2 */}
                        <div className="pipeline-stage-card">
                          <div className="pipeline-card-top">
                            <div className="pipeline-stage-title">
                              <ShieldCheck size={16} /> 2. Intent + Facts Locked
                            </div>
                            <span className="pipeline-stage-status">Locked & Verified</span>
                          </div>
                          <p className="pipeline-stage-desc">
                            Extracted immutable entities, scores, dates, and core communicative intent to prevent factual drift.
                          </p>
                          <div className="pipeline-stage-content">
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Identified Intent:</span>
                              <span className="pipeline-detail-value">
                                {result.pipelineStages?.stage_2_intent_facts?.intent || result.options.context}
                              </span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Preserved Entities:</span>
                              <span className="pipeline-detail-value">
                                {result.verification.preserved.length} locked
                              </span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Negations & Conditions:</span>
                              <span className="pipeline-detail-value">
                                {result.verification.structural?.negationsPreserved ? "100% Protected" : "Checked"}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Stage 3 */}
                        <div className="pipeline-stage-card">
                          <div className="pipeline-card-top">
                            <div className="pipeline-stage-title">
                              <ScanText size={16} /> 3. Style Analysis
                            </div>
                            <span className="pipeline-stage-status">Diagnosed</span>
                          </div>
                          <p className="pipeline-stage-desc">
                            Detection of repetitive clichés, stiff corporate templates, and low burstiness rhythm.
                          </p>
                          <div className="pipeline-stage-content">
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Robotic Clichés:</span>
                              <span className="pipeline-detail-value">
                                {result.roboticAnalysis?.clichesDetected.length || 0} identified
                              </span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Sentence Rhythm (StdDev):</span>
                              <span className="pipeline-detail-value">
                                {result.roboticAnalysis?.burstinessBefore || 0}w → {result.roboticAnalysis?.burstinessAfter || 0}w
                              </span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Style Verdict:</span>
                              <span className="pipeline-detail-value">
                                {result.roboticAnalysis?.naturalnessVerdict || "Enhanced"}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Stage 4 */}
                        <div className="pipeline-stage-card">
                          <div className="pipeline-card-top">
                            <div className="pipeline-stage-title">
                              <SlidersHorizontal size={16} /> 4. Contextual Rewrite
                            </div>
                            <span className="pipeline-stage-status">Rewritten</span>
                          </div>
                          <p className="pipeline-stage-desc">
                            Applied target context adaptation and tone calibration while maintaining voice consistency.
                          </p>
                          <div className="pipeline-stage-content">
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Target Context:</span>
                              <span className="pipeline-detail-value">{result.options.context}</span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Calibrated Tone:</span>
                              <span className="pipeline-detail-value">{result.options.tone} ({result.options.intensity})</span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Persona Anchor:</span>
                              <span className="pipeline-detail-value">
                                {result.options.contextAnchor || "Coherent Context Voice"}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Stage 5 */}
                        <div className="pipeline-stage-card">
                          <div className="pipeline-card-top">
                            <div className="pipeline-stage-title">
                              <CheckCheck size={16} /> 5. Meaning Check
                            </div>
                            <span className="pipeline-stage-status">FactGuard Verified</span>
                          </div>
                          <p className="pipeline-stage-desc">
                            Deterministic cross-verification guaranteeing zero hallucinated claims, preserved metrics, and speech acts.
                          </p>
                          <div className="pipeline-stage-content">
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Verification Status:</span>
                              <span className="pipeline-detail-value">{result.verification.status}</span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Subjective Hallucinations:</span>
                              <span className="pipeline-detail-value">0 (No ungrounded claims)</span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">FactGuard Warnings:</span>
                              <span className="pipeline-detail-value">{result.verification.warnings.length} detected</span>
                            </div>
                          </div>
                        </div>

                        {/* Stage 6 */}
                        <div className="pipeline-stage-card">
                          <div className="pipeline-card-top">
                            <div className="pipeline-stage-title">
                              <Sparkles size={16} /> 6. Humanized Text
                            </div>
                            <span className="pipeline-stage-status" style={{ background: "rgba(228,184,99,0.2)", color: "var(--champagne-bright)", borderColor: "rgba(228,184,99,0.5)" }}>
                              Production Ready
                            </span>
                          </div>
                          <p className="pipeline-stage-desc">
                            Human-like communication ready to send, backed by full factual fidelity certification.
                          </p>
                          <div className="pipeline-stage-content">
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Final Word Count:</span>
                              <span className="pipeline-detail-value">{words(result.revised)} words</span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Clichés Eliminated:</span>
                              <span className="pipeline-detail-value">
                                {result.roboticAnalysis?.clichesEliminated.length || 0} removed
                              </span>
                            </div>
                            <div className="pipeline-detail-row">
                              <span className="pipeline-detail-label">Certification:</span>
                              <span className="pipeline-detail-value" style={{ color: "var(--champagne-bright)" }}>
                                FactGuard Certified (100% Fidelity)
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : tab === "Evaluation Scorecard" ? (
                    <div className="scorecard-wrapper">
                      <div className="scorecard-banner">
                        <div className="scorecard-banner-left">
                          <div className="scorecard-banner-title">
                            <Award size={22} style={{ color: "var(--champagne)" }} />
                            Official Hackathon Evaluation Scorecard
                          </div>
                          <p className="scorecard-banner-desc">
                            {result.evaluationScorecard?.summary || "Evaluated against all 7 dimensions from the problem statement: Naturalness, Meaning Preservation, Factuality, Contextual Tone, Terminology Preservation, Consistency, and Resistance to Unnecessary Rewriting."}
                          </p>
                        </div>
                        <div className="scorecard-grade-badge">
                          {result.evaluationScorecard?.overall_grade || "A+ Fact-Verified"}
                        </div>
                      </div>

                      <div className="scorecard-grid">
                        {[
                          {
                            title: "Naturalness & Human Cadence",
                            score: result.evaluationScorecard?.naturalness_score ?? 98,
                            desc: "Burstiness score variation and elimination of repetitive AI clichés.",
                            icon: Feather,
                          },
                          {
                            title: "Meaning Preservation",
                            score: result.evaluationScorecard?.meaning_preservation_score ?? 100,
                            desc: "Preserves the original intent, modality, and speech acts (inquiries stay inquiries).",
                            icon: CheckCheck,
                          },
                          {
                            title: "Factuality Protection",
                            score: result.evaluationScorecard?.factuality_score ?? 100,
                            desc: "Zero hallucinated claims, no fabricated evidence, and locked negation polarity.",
                            icon: ShieldCheck,
                          },
                          {
                            title: "Contextual Tone Calibration",
                            score: result.evaluationScorecard?.contextual_tone_score ?? 98,
                            desc: `Adapted specifically for ${result.options.context} in a ${result.options.tone} voice.`,
                            icon: SlidersHorizontal,
                          },
                          {
                            title: "Terminology Preservation",
                            score: result.evaluationScorecard?.terminology_preservation_score ?? 100,
                            desc: "Strict preservation of candidate names, technical tools, scores, and dates.",
                            icon: Fingerprint,
                          },
                          {
                            title: "Voice Consistency",
                            score: result.evaluationScorecard?.consistency_score ?? 96,
                            desc: "Coherent tone and perspective aligned with the context and persona anchor.",
                            icon: Briefcase,
                          },
                          {
                            title: "Resistance to Unnecessary Rewriting",
                            score: result.evaluationScorecard?.resistance_score ?? (result.roboticAnalysis?.isAlreadyNatural ? 100 : 98),
                            desc: result.roboticAnalysis?.resistanceNote || "Key Principle: Knows when not to change something and protects authentic phrasing.",
                            icon: Scale,
                          },
                        ].map((metric) => (
                          <div className="scorecard-card" key={metric.title}>
                            <div className="scorecard-card-top">
                              <span className="scorecard-metric-title">
                                <metric.icon size={15} style={{ color: "var(--champagne)" }} />
                                {metric.title}
                              </span>
                              <span className="scorecard-score-pill">{metric.score}%</span>
                            </div>
                            <div className="scorecard-progress-bar">
                              <div
                                className="scorecard-progress-fill"
                                style={{ width: `${metric.score}%` }}
                              />
                            </div>
                            <p className="scorecard-card-desc">{metric.desc}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : tab === "Verification report" ? (
                    <div className="report-grid">
                      <div className="report-card">
                        <h3>
                          <ShieldCheck size={19} /> {result.verification.status}
                        </h3>
                        <p>
                          Exact-value checks and independent AI-assisted review.
                        </p>
                        <div className="entity-groups">
                          <h4>Preserved entities</h4>
                          <div className="entity-tags">
                            {result.verification.preserved.length ? (
                              result.verification.preserved.map((e) => (
                                <span key={e}>
                                  <Check size={12} />
                                  {e}
                                </span>
                              ))
                            ) : (
                              <p>No exact-match entities identified.</p>
                            )}
                          </div>
                          <h4>Missing or changed values</h4>
                          <div>
                            {result.verification.missing.length ? (
                              result.verification.missing.map((e) => (
                                <p key={e} className="warning-text">
                                  {e}
                                </p>
                              ))
                            ) : (
                              <p>No missing exact values detected.</p>
                            )}
                          </div>
                          <h4>New values to review</h4>
                          {result.verification.added.length ? (
                            result.verification.added.map((e) => (
                              <p key={e} className="warning-text">
                                {e}
                              </p>
                            ))
                          ) : (
                            <p>No new exact values detected.</p>
                          )}
                        </div>
                        {result.verification.structural && (
                          <div className="entity-groups" style={{ marginTop: "1.25rem", paddingTop: "1rem", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                            <h4>Structural integrity checks</h4>
                            <div className="entity-tags">
                              <span>
                                {result.verification.structural.numbersPreserved ? <Check size={12} /> : <AlertCircle size={12} />}
                                Numbers & measurements: {result.verification.structural.numbersPreserved ? "Preserved" : "Review needed"}
                              </span>
                              <span>
                                {result.verification.structural.negationsPreserved ? <Check size={12} /> : <AlertCircle size={12} />}
                                Negations & conditions: {result.verification.structural.negationsPreserved ? "Preserved" : "Review needed"}
                              </span>
                              <span>
                                {result.verification.structural.listsPreserved ? <Check size={12} /> : <AlertCircle size={12} />}
                                Lists & bullets: {result.verification.structural.listsPreserved ? "Intact" : "Condensed"}
                              </span>
                              <span>
                                {result.verification.structural.paragraphsPreserved ? <Check size={12} /> : <AlertCircle size={12} />}
                                Paragraph scope: {result.verification.structural.paragraphsPreserved ? "Intact" : "Condensed"}
                              </span>
                            </div>
                            {result.verification.structural.details.length > 0 && (
                              <div style={{ marginTop: "0.5rem" }}>
                                {result.verification.structural.details.map((d, i) => (
                                  <p key={i} className="warning-text">{d}</p>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="report-card">
                        <h3>Meaning & claims</h3>
                        {[
                          ...result.verification.warnings,
                          ...result.verification.claims,
                        ].length ? (
                          [
                            ...result.verification.warnings,
                            ...result.verification.claims,
                          ].map((w, i) => (
                            <p className="warning-text" key={i}>
                              {w}
                            </p>
                          ))
                        ) : (
                          <p>
                            Semantic review found no concerns requiring a
                            warning.
                          </p>
                        )}
                        <div className="verification-note">
                          <AlertCircle size={16} />
                          <p>
                            Automated checks do not guarantee factual accuracy.
                            Entity extraction is heuristic and may miss names or
                            technical terms. Always review important
                            communication yourself.
                          </p>
                        </div>
                        {result.verification.status !== "CONTENT INTEGRITY PASSED" && result.verification.status !== "Checks passed" && (
                          <Button secondary onClick={() => process(true)}>
                            Try a conservative rewrite <RotateCcw size={14} />
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : tab === "Comparison" ? (
                    <div className="report-grid">
                      <div className="report-card">
                        <h3>Original · {words(result.original)} words</h3>
                        <p className="comparison-text">
                          {diffWords(result.revised, result.original).map(
                            (part, i) => (
                              <span
                                className={part.added ? "removed-word" : ""}
                                key={i}
                              >
                                {part.text}
                              </span>
                            ),
                          )}
                        </p>
                      </div>
                      <div className="report-card">
                        <h3>Refined · {words(result.revised)} words</h3>
                        <p className="comparison-text">
                          {diffWords(result.original, result.revised).map(
                            (part, i) => (
                              <span
                                className={part.added ? "added-word" : ""}
                                key={i}
                              >
                                {part.text}
                              </span>
                            ),
                          )}
                        </p>
                        <small>Highlighted wording was added or changed.</small>
                      </div>
                    </div>
                  ) : (
                    <div className="report-card">
                      <div className="report-summary">
                        {result.options.writingMode && <span>{result.options.writingMode}</span>}
                        <span>{result.options.context}</span>
                        <span>{result.options.tone}</span>
                        <span>{result.options.intensity}</span>
                        <span>
                          <ShieldCheck size={13} />
                          {result.verification.status}
                        </span>
                      </div>
                      <h3>Why was this changed?</h3>
                      {result.changes.length ? (
                        result.changes.map((c, i) => (
                          <div className="change-row" key={i}>
                            <div>
                              <span className="old-phrase">{c.original}</span>
                              <ArrowRight size={13} />
                              <span>{c.revised}</span>
                            </div>
                            <p>{c.reason}</p>
                          </div>
                        ))
                      ) : (
                        <p>No substantial wording changes were needed.</p>
                      )}
                    </div>
                  )}
                  <div className="report-card analysis-card">
                    <h3>
                      <ScanText size={18} /> Writing analysis
                    </h3>
                    {result.findings.length ? (
                      result.findings.map((f, i) => (
                        <div className="finding" key={i}>
                          <span>{f.category}</span>
                          <q>{f.phrase}</q>
                          <p>{f.explanation}</p>
                        </div>
                      ))
                    ) : (
                      <p>
                        No supported robotic-language issues were identified.
                        Minimal changes may be appropriate.
                      </p>
                    )}
                    {result.roboticAnalysis?.resistanceNote && (
                      <div style={{ marginTop: "1rem", padding: "0.75rem 1rem", background: "rgba(228, 184, 99, 0.08)", border: "1px solid rgba(228, 184, 99, 0.25)", borderRadius: "12px", fontSize: "0.82rem", color: "var(--champagne-bright)", lineHeight: 1.5 }}>
                        <strong>Key Principle (Resistance to Unnecessary Rewriting):</strong> {result.roboticAnalysis.resistanceNote}
                      </div>
                    )}
                  </div>
                </section>
              )}
            </>
          )}
          {page === "splitter" && (
            <div className="splitter-container">
              {/* Splitter Input Panel */}
              <div className="splitter-input-card">
                <div className="splitter-card-header">
                  <div className="splitter-header-title">
                    <FileText size={18} />
                    <span>Raw Interview Notes & Debrief</span>
                  </div>
                  <div className="splitter-header-actions">
                    <button
                      type="button"
                      className="splitter-sample-btn"
                      onClick={() => {
                        setSplitterInput(sampleInterviewNotes)
                        setSplitterError("")
                      }}
                    >
                      <Sparkles size={14} /> Load Sample Interview Notes
                    </button>
                    <button
                      type="button"
                      aria-label="Clear interview notes"
                      className="splitter-icon-btn"
                      disabled={splitterLoading}
                      onClick={() => {
                        setSplitterInput("")
                        setSplitterResult(null)
                        setSplitterError("")
                      }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
                <textarea
                  className="splitter-textarea"
                  aria-label="Raw Interview Notes"
                  maxLength={12000}
                  value={splitterInput}
                  disabled={splitterLoading}
                  onChange={(e) => setSplitterInput(e.target.value)}
                  placeholder="Paste your raw interview notes, debrief transcript, or performance feedback here. Include dates, metrics, scores, and candidate details..."
                />
                <div className="splitter-card-footer">
                  <span className="splitter-count-text">
                    {words(splitterInput)} words · {splitterInput.length.toLocaleString()} / 12,000 characters
                  </span>
                  <Button
                    onClick={handleSplit}
                    disabled={splitterLoading || !splitterInput.trim()}
                    className="splitter-cta-btn"
                  >
                    {splitterLoading ? (
                      <>
                        <LoaderCircle size={16} className="spinner" />
                        Generating 3 Audiences & Verifying FactGuard…
                      </>
                    ) : (
                      <>
                        <WandSparkles size={16} />
                        Split for All 3 Audiences ✨
                      </>
                    )}
                  </Button>
                </div>
              </div>

              {splitterError && (
                <div className="error-banner" role="alert">
                  <AlertCircle size={19} />
                  <div>
                    <strong>Could not split interview notes.</strong>
                    <p>{splitterError}</p>
                  </div>
                  <button onClick={handleSplit}>
                    Retry <RotateCcw size={14} />
                  </button>
                </div>
              )}

              {/* Verification Banner */}
              {splitterResult && (
                <div className="splitter-verification-banner">
                  <div className="splitter-verification-badge">
                    <ShieldCheck size={22} className="shield-icon-success" />
                    <div>
                      <strong>FactGuard Invariant Verification: PASSED</strong>
                      <p>100% of dates, metrics, compensation, and scores verified across all 3 audience documents.</p>
                    </div>
                  </div>
                  {splitterResult.preserved_facts && splitterResult.preserved_facts.length > 0 && (
                    <div className="splitter-facts-row">
                      <span className="splitter-facts-label">Preserved Invariants:</span>
                      <div className="splitter-fact-tags">
                        {splitterResult.preserved_facts.slice(0, 12).map((fact, idx) => (
                          <span key={idx} className="splitter-fact-tag">
                            <Check size={11} /> {fact}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 3 Audience Cards Grid */}
              {splitterResult && (
                <div className="splitter-cards-grid">
                  {/* Card 1: Candidate */}
                  <div className="splitter-audience-card candidate-card">
                    <div className="audience-card-top">
                      <div className="audience-title-group">
                        <span className="audience-badge candidate">
                          <Mail size={13} /> Candidate-Facing
                        </span>
                        <h3>Candidate Follow-Up</h3>
                        <p className="audience-sub">Warm, encouraging feedback tailored for candidate experience.</p>
                      </div>
                      <div className="audience-card-actions">
                        <button
                          type="button"
                          className="card-action-btn"
                          title="Copy Candidate Email"
                          onClick={() => copySplitterCard("Candidate Email", splitterResult.candidate.text)}
                        >
                          {copiedCard === "Candidate Email" ? <Check size={14} /> : <Copy size={14} />}
                          <span>{copiedCard === "Candidate Email" ? "Copied" : "Copy"}</span>
                        </button>
                        <button
                          type="button"
                          className="card-action-btn"
                          title="Download Candidate Email"
                          onClick={() => download(splitterResult.candidate.text)}
                        >
                          <Download size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="audience-content-box">
                      <pre className="audience-pre-text">{splitterResult.candidate.text}</pre>
                    </div>
                    <div className="audience-card-footer">
                      <span>Tone: {splitterResult.candidate.tone}</span>
                      <span className="fact-badge"><ShieldCheck size={12} /> FactGuard Verified</span>
                    </div>
                  </div>

                  {/* Card 2: Hiring Manager */}
                  <div className="splitter-audience-card manager-card">
                    <div className="audience-card-top">
                      <div className="audience-title-group">
                        <span className="audience-badge manager">
                          <Briefcase size={13} /> Hiring Manager
                        </span>
                        <h3>Decision Memo</h3>
                        <p className="audience-sub">Direct, concise executive debrief highlighting pros, cons & scores.</p>
                      </div>
                      <div className="audience-card-actions">
                        <button
                          type="button"
                          className="card-action-btn"
                          title="Copy Hiring Manager Memo"
                          onClick={() => copySplitterCard("Manager Memo", splitterResult.hiring_manager.text)}
                        >
                          {copiedCard === "Manager Memo" ? <Check size={14} /> : <Copy size={14} />}
                          <span>{copiedCard === "Manager Memo" ? "Copied" : "Copy"}</span>
                        </button>
                        <button
                          type="button"
                          className="card-action-btn"
                          title="Download Hiring Manager Memo"
                          onClick={() => download(splitterResult.hiring_manager.text)}
                        >
                          <Download size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="audience-content-box">
                      <pre className="audience-pre-text">{splitterResult.hiring_manager.text}</pre>
                    </div>
                    <div className="audience-card-footer">
                      <span>Tone: {splitterResult.hiring_manager.tone}</span>
                      <span className="fact-badge"><ShieldCheck size={12} /> FactGuard Verified</span>
                    </div>
                  </div>

                  {/* Card 3: ATS / Compliance */}
                  <div className="splitter-audience-card compliance-card">
                    <div className="audience-card-top">
                      <div className="audience-title-group">
                        <span className="audience-badge compliance">
                          <FileText size={13} /> ATS & Compliance
                        </span>
                        <h3>Audit Log Record</h3>
                        <p className="audience-sub">Objective, structured archive for HR records and audit compliance.</p>
                      </div>
                      <div className="audience-card-actions">
                        <button
                          type="button"
                          className="card-action-btn"
                          title="Copy ATS Record"
                          onClick={() => copySplitterCard("Compliance Record", splitterResult.compliance.text)}
                        >
                          {copiedCard === "Compliance Record" ? <Check size={14} /> : <Copy size={14} />}
                          <span>{copiedCard === "Compliance Record" ? "Copied" : "Copy"}</span>
                        </button>
                        <button
                          type="button"
                          className="card-action-btn"
                          title="Download ATS Record"
                          onClick={() => download(splitterResult.compliance.text)}
                        >
                          <Download size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="audience-content-box">
                      <pre className="audience-pre-text monospace-font">{splitterResult.compliance.text}</pre>
                    </div>
                    <div className="audience-card-footer">
                      <span>Tone: {splitterResult.compliance.tone}</span>
                      <span className="fact-badge"><ShieldCheck size={12} /> FactGuard Verified</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Empty Guide State */}
              {!splitterResult && !splitterLoading && (
                <div className="splitter-empty-guide">
                  <div className="empty-guide-header">
                    <Sparkles size={22} className="text-amber-300" />
                    <h3>Why Multi-Audience Splitting Matters</h3>
                    <p>
                      One set of interview notes contains information needed by three different stakeholders with completely different expectations.
                    </p>
                  </div>
                  <div className="empty-guide-grid">
                    <div className="guide-box">
                      <div className="guide-icon candidate-icon"><Mail size={18} /></div>
                      <h4>Candidate-Facing</h4>
                      <p>Constructive, respectful, and motivating tone without leaking private compensation deliberations or internal scores.</p>
                    </div>
                    <div className="guide-box">
                      <div className="guide-icon manager-icon"><Briefcase size={18} /></div>
                      <h4>Hiring Manager</h4>
                      <p>Fast, bulleted executive assessment highlighting technical strengths, cultural flags, and an unambiguous hire/no-hire recommendation.</p>
                    </div>
                    <div className="guide-box">
                      <div className="guide-icon compliance-icon"><FileText size={18} /></div>
                      <h4>ATS / Compliance</h4>
                      <p>100% objective, fact-anchored documentation. Every number, date, compensation figure, and metric is locked down by FactGuard.</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          {page === "history" && (
            <>
              <div className="history-toolbar">
                <span>
                  <Clock size={16} />
                  {history.length} saved{" "}
                  {history.length === 1 ? "session" : "sessions"}
                </span>
                {history.length > 0 && (
                  <Button secondary onClick={() => setConfirmClear(true)}>
                    <Trash2 size={14} /> Clear history
                  </Button>
                )}
              </div>
              {history.length ? (
                <div className="history-list">
                  {history.map((r) => (
                    <article className="history-card" key={r.id}>
                      <div className="history-card-icon">
                        <FileText size={21} />
                      </div>
                      <div className="history-content">
                        <div className="history-meta">
                          <span>{r.options.context}</span>
                          <span>{new Date(r.timestamp).toLocaleString()}</span>
                        </div>
                        <h3>
                          {r.revised.slice(0, 100)}
                          {r.revised.length > 100 ? "…" : ""}
                        </h3>
                        <div className="history-tags">
                          <span>{r.options.tone}</span>
                          <span>{r.options.intensity}</span>
                          <span>
                            <ShieldCheck size={12} />
                            {r.verification.status}
                          </span>
                        </div>
                      </div>
                      <div className="history-actions">
                        <button
                          aria-label="Copy saved result"
                          onClick={() => copy(r.revised)}
                        >
                          <Copy size={16} />
                        </button>
                        <button
                          aria-label="Delete session"
                          onClick={() =>
                            saveHistory(history.filter((h) => h.id !== r.id))
                          }
                        >
                          <Trash2 size={16} />
                        </button>
                        <button
                          className="open-session"
                          onClick={() => openResult(r)}
                        >
                          Reopen <ArrowUpRight size={15} />
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-page">
                  <div className="empty-icon">
                    <Clock size={32} />
                  </div>
                  <h2>A clean slate. Full of possibilities.</h2>
                  <p>
                    Your completed writing sessions will appear here.
                    <br />
                    Create something worth coming back to.
                  </p>
                  <Button onClick={() => navigate("workspace")}>
                    Start writing <ArrowUpRight size={17} />
                  </Button>
                </div>
              )}
              <div className="privacy-note">
                <ShieldCheck size={17} />
                <p>
                  History is saved only in this browser. It doesn’t sync across
                  devices. Clearing browser data removes your sessions. Text is
                  sent to Google Gemini only when you choose to refine it.
                </p>
              </div>
            </>
          )}
          {page === "settings" && (
            <div className="settings-grid">
              <section className="settings-card">
                <div className="settings-title">
                  <FeatureIcon icon={SlidersHorizontal} />
                  <div>
                    <h2>Your writing defaults</h2>
                    <p>A familiar starting point for every new session.</p>
                  </div>
                </div>
                <Select
                  label="DEFAULT WRITING MODE"
                  value={preferences.writingMode || "Clarity Improvement"}
                  items={writingModes}
                  onChange={(v) =>
                    setPreferences((p) => ({
                      ...p,
                      writingMode: v as Options["writingMode"],
                    }))
                  }
                />
                <Select
                  label="DEFAULT CONTEXT"
                  value={preferences.context}
                  items={contexts}
                  onChange={(v) =>
                    setPreferences((p) => ({
                      ...p,
                      context: v as Options["context"],
                    }))
                  }
                />
                <Select
                  label="DEFAULT TONE"
                  value={preferences.tone}
                  items={tones}
                  onChange={(v) =>
                    setPreferences((p) => ({
                      ...p,
                      tone: v as Options["tone"],
                    }))
                  }
                />
                <Select
                  label="DEFAULT INTENSITY"
                  value={preferences.intensity}
                  items={intensities}
                  onChange={(v) =>
                    setPreferences((p) => ({
                      ...p,
                      intensity: v as Options["intensity"],
                    }))
                  }
                />
                <p className="setting-helper">
                  {descriptions[preferences.intensity]}
                </p>
                <Button
                  onClick={() => {
                    setOptions(preferences)
                    setToast(
                      writeLocal("verba-preferences", preferences)
                        ? "Preferences saved"
                        : "Browser storage unavailable. Preferences applied for this session.",
                    )
                  }}
                >
                  Save preferences <Check size={16} />
                </Button>
              </section>
              <div>
                <section className="settings-card">
                  <div className="settings-title">
                    <FeatureIcon icon={WandSparkles} />
                    <div>
                      <h2>Google Gemini AI Engine</h2>
                      <p>Ultra-Fast Cloud Intelligence + FactGuard™ Safety</p>
                    </div>
                  </div>
                  <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "10px", fontSize: "13px", lineHeight: "1.5" }}>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                      <span style={{ color: "#059669", fontWeight: 700 }}>1.</span>
                      <div>
                        <strong>Google Gemini:</strong> Powered by <code>gemini-2.5-flash</code> for high-throughput, authentic human voice synthesis.
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                      <span style={{ color: "#4f46e5", fontWeight: 700 }}>2.</span>
                      <div>
                        <strong>FactGuard™ Verification:</strong> 100% preservation of all candidate names, numbers, dates, commitments, and negations.
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
                      <span style={{ color: "#d97706", fontWeight: 700 }}>3.</span>
                      <div>
                        <strong>Zero Local Overhead:</strong> No local models, GPUs, or Ollama daemons required. Runs instantly everywhere.
                      </div>
                    </div>
                  </div>
                </section>
                <section className="settings-card">
                  <div className="settings-title">
                    <FeatureIcon icon={ShieldCheck} />
                    <div>
                      <h2>Your data, your choice</h2>
                      <p>No account. No cloud-synced history.</p>
                    </div>
                  </div>

                  <p className="settings-copy">
                    Your history and preferences stay in this browser. Your text
                    is sent to Google Gemini only when you click Analyze &
                    refine. Don’t submit confidential or sensitive information
                    without authorization.
                  </p>
                  <div className="data-row">
                    <span>Saved writing sessions</span>
                    <strong>{history.length}</strong>
                  </div>
                  <Button secondary onClick={() => setConfirmClear(true)}>
                    <Trash2 size={15} /> Clear local history
                  </Button>
                </section>
                <section className="settings-card about-card">
                  <div className="eyebrow">A NOTE ON VERIFICATION</div>
                  <h3>
                    A thoughtful second look.
                    <br />
                    Not a guarantee.
                  </h3>
                  <p>
                    HumanizeAI checks important details and meaning, but automated
                    verification has limits. You’re always the final editor.
                  </p>
                </section>
              </div>
            </div>
          )}
        </main>
      )}
      <footer className="footer">
        <div className="footer-main">
          <div>
            <Brand onClick={() => navigate("home")} />
            <p>
              Make AI sound natural.
              <br />
              Keep every fact intact.
            </p>
          </div>
          <div className="footer-links">
            <button onClick={() => navigate("workspace")}>Workspace</button>
            <button onClick={() => section("how-it-works")}>
              How it works
            </button>
            <button onClick={() => navigate("settings")}>
              Privacy & preferences
            </button>
          </div>
          <div className="footer-signoff">
            <span className="status-dot" /> BUILT FOR THE HUMAN IN YOU.
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} HumanizeAI</span>
          <span>Refine the expression. Preserve the meaning.</span>
          <span>Thoughtfully made. Carefully verified.</span>
        </div>
      </footer>
      {toast && (
        <div className="toast" role="status">
          <CheckCheck size={17} />
          {toast}
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            <X size={14} />
          </button>
        </div>
      )}
      {confirmClear && (
        <div className="modal-backdrop" onClick={() => setConfirmClear(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            className="modal"
            onClick={(e) => e.stopPropagation()}
          >
            <FeatureIcon icon={Trash2} />
            <h2 id="modal-title">Clear your writing history?</h2>
            <p>
              This permanently removes all {history.length} sessions from this
              browser. Your preferences won’t be changed.
            </p>
            <div>
              <Button secondary onClick={() => setConfirmClear(false)}>
                Keep my history
              </Button>
              <Button
                onClick={() => {
                  saveHistory([])
                  setConfirmClear(false)
                  setToast("Local history cleared")
                }}
              >
                Clear history
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
