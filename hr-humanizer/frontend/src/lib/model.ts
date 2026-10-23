export const writingModes = [
  "Clarity Improvement",
  "Grammar Correction",
  "Academic Writing",
  "Professional Writing",
  "Conversational Writing",
  "Technical Writing",
  "Concise Writing",
  "Expanded Explanation",
] as const
export type WritingMode = typeof writingModes[number]

export const verificationStatuses = [
  "CONTENT INTEGRITY PASSED",
  "REVIEW RECOMMENDED",
  "CONTENT INTEGRITY FAILED",
  "VERIFICATION UNAVAILABLE",
] as const
export type VerificationStatus = typeof verificationStatuses[number]

export const contexts = [
  "Candidate Communication",
  "Recruiter Feedback",
  "Interview Questions",
  "Recruiter Notes",
  "Summaries & Reports",
  "General Communication",
] as const
export const tones = ["Professional", "Polished", "Conversational"] as const
export const intensities = ["Light", "Balanced", "Strong"] as const

export type Options = {
  writingMode?: WritingMode
  context: typeof contexts[number]
  tone: typeof tones[number]
  intensity: typeof intensities[number]
  contextAnchor?: string
}

export type Finding = {
  category: string
  phrase: string
  explanation: string
}

export type Change = {
  original: string
  revised: string
  reason: string
}

export type StructuralCheck = {
  paragraphsPreserved: boolean
  listsPreserved: boolean
  negationsPreserved: boolean
  numbersPreserved: boolean
  details: string[]
}

export type Verification = {
  status: VerificationStatus | string
  preserved: string[]
  missing: string[]
  added: string[]
  warnings: string[]
  claims: string[]
  structural?: StructuralCheck
}

export type PipelineStages = {
  stage_1_input?: {
    step_name?: string
    description?: string
    word_count?: number
    character_count?: number
    preview?: string
    status?: string
  }
  stage_2_intent_facts?: {
    step_name?: string
    description?: string
    intent?: string
    metrics_locked?: string[]
    dates_locked?: string[]
    entities_locked?: string[]
    negations_detected?: string[]
    status?: string
  }
  stage_3_style_analysis?: {
    step_name?: string
    description?: string
    cliches_detected?: string[]
    cliches_count?: number
    burstiness_before?: number
    burstiness_after?: number
    formality_assessment?: string
    is_already_natural?: boolean
    status?: string
  }
  stage_4_contextual_rewrite?: {
    step_name?: string
    description?: string
    target_context?: string
    target_tone?: string
    intensity_level?: string
    context_anchor?: string
    status?: string
  }
  stage_5_meaning_check?: {
    step_name?: string
    description?: string
    passed?: boolean
    confidence_score?: number
    missing_numbers_count?: number
    unsupported_judgments_count?: number
    negation_preserved?: boolean
    speech_act_preserved?: boolean
    warnings?: string[]
    status?: string
  }
  stage_6_humanized_text?: {
    step_name?: string
    description?: string
    word_count?: number
    verdict?: string
    certification_badge?: string
    status?: string
  }
}

export type EvaluationScorecard = {
  naturalness_score: number
  meaning_preservation_score: number
  factuality_score: number
  contextual_tone_score: number
  terminology_preservation_score: number
  consistency_score: number
  resistance_score: number
  overall_grade: string
  summary: string
}

export type Result = {
  id: string
  timestamp: string
  original: string
  revised: string
  options: Options
  findings: Finding[]
  changes: Change[]
  verification: Verification
  model?: string
  provider?: "gemini" | "rule_engine" | string
  fallbackUsed?: boolean
  fallbackReason?: string
  roboticAnalysis?: {
    clichesDetected: string[]
    clichesEliminated: string[]
    burstinessBefore: number
    burstinessAfter: number
    naturalnessVerdict: string
    isAlreadyNatural?: boolean
    resistanceNote?: string
  }
  pipelineStages?: PipelineStages
  evaluationScorecard?: EvaluationScorecard
}


export const defaults: Options = {
  writingMode: "Clarity Improvement",
  context: "General Communication",
  tone: "Professional",
  intensity: "Balanced",
  contextAnchor: "",
}

export interface SamplePreset {
  id: string
  name: string
  category: typeof contexts[number]
  description: string
  text: string
  suggestedTone: typeof tones[number]
  suggestedMode: WritingMode
  contextAnchor?: string
}

export const samplePresets: SamplePreset[] = [
  {
    id: "candidate-comm",
    name: "Candidate Communication",
    category: "Candidate Communication",
    description: "De-robotizes stiff interview confirmation while preserving exact time, panel members, and date.",
    text: "Dear applicant, I am writing to inform you that your technical interview with our platform engineering panel (Alex Chen and Maya Patel) has been scheduled for Friday, October 24 at 2:30 PM EST. Please do not hesitate to contact me if you require any additional information or have scheduling constraints.",
    suggestedTone: "Conversational",
    suggestedMode: "Clarity Improvement",
    contextAnchor: "Candidate: Jordan Rivera | Role: Staff Engineer",
  },
  {
    id: "interview-question",
    name: "Interview Questions",
    category: "Interview Questions",
    description: "Refines a rigid, machine-generated interview prompt into a conversational, human dialogue question.",
    text: "Could you please elaborate on your experience with distributed systems and describe how you handle race conditions in high-concurrency microservices environments? Furthermore, please detail a situation where you had to delve into performance bottlenecks under a 45,000 req/sec load.",
    suggestedTone: "Conversational",
    suggestedMode: "Conversational Writing",
    contextAnchor: "Panel Interview: Systems Architecture",
  },
  {
    id: "recruiter-notes",
    name: "Recruiter Notes & Debrief",
    category: "Recruiter Notes",
    description: "Synthesizes raw debrief notes with scores (78/100), dates, and Kubernetes experience without hallucinating subjective red flags.",
    text: "The candidate scored 78/100 on the live assessment. They may be suitable for the junior developer role, but they have not worked with Kubernetes. Next step: Final committee debrief on August 15.",
    suggestedTone: "Professional",
    suggestedMode: "Clarity Improvement",
    contextAnchor: "Candidate Assessment: Junior Dev",
  },
  {
    id: "recruiter-feedback",
    name: "Recruiter Feedback",
    category: "Recruiter Feedback",
    description: "Balanced, constructive assessment preserving scores (four of six) and uncertain system design experience.",
    text: "The candidate answered four of six technical questions correctly and demonstrated proficiency in React. Their system design experience remains unclear. It is important to note that the team will not be proceeding with an offer at this juncture.",
    suggestedTone: "Polished",
    suggestedMode: "Professional Writing",
    contextAnchor: "Candidate Feedback: Technical Round",
  },
  {
    id: "summaries-reports",
    name: "Summaries & Reports",
    category: "Summaries & Reports",
    description: "Executive HR talent report locking candidate counts (14), offers (3), and annual salary allocations (₹32,00,000).",
    text: "This report serves as a testament to the department's Q3 hiring drive. It is crucial to note that 14 candidates were interviewed across 4 regions, with 3 offers extended. Proposed salary allocations total ₹32,00,000 annually, subject to final board approval.",
    suggestedTone: "Polished",
    suggestedMode: "Professional Writing",
    contextAnchor: "Q3 Engineering Talent Report",
  },
  {
    id: "resistance-sample",
    name: "Already Natural (Test Key Principle)",
    category: "General Communication",
    description: "Tests 'Resistance to Unnecessary Rewriting' — authentic human text with 0 unnecessary churn.",
    text: "Hi Alex, thanks for speaking with us today! The team really enjoyed discussing your React projects. We're reviewing all notes with the hiring manager and will get back to you by Friday afternoon.",
    suggestedTone: "Conversational",
    suggestedMode: "Clarity Improvement",
    contextAnchor: "Direct Recruiter Check-in",
  },
]

export const example = samplePresets[0].text

export const words = (text: string) =>
  text.trim() ? text.trim().split(/\s+/).length : 0

export function readLocal<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key)
    return value ? JSON.parse(value) : fallback
  } catch {
    return fallback
  }
}

export function writeLocal(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}

export function entities(text: string): string[] {
  const caseInsensitiveMatches =
    text.match(
      /[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\/\d{1,2}\/\d{2,4}\b|(?:\$|€|£|¥)?\b\d+(?:[.,:/-]\d+)*(?:%|°[CF]|\s*(?:AM|PM|daily|weekly|monthly|kg|lbs|mph|km\/h|ms|px|GB|MB|KB|GHz|MHz|USD|EUR|GBP|INR)\b)?|\b(?:two|three|four|five|six|seven|eight|nine|ten|\d+)[-\s]+(?:weeks?|days?|hours?|months?|years?)\b|\[\d+\]|\([A-Z][a-z]+(?:\s+et\s+al\.)?,\s*\d{4}\)/gi,
    ) || []
  const properNameMatches =
    text.match(/\b(?:Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/g) || []
  const combined = [...caseInsensitiveMatches, ...properNameMatches]
  return [...new Set(combined.map((v) => v.replace(/\s+/g, " ").trim()))]
}

export function extractNegations(text: string): string[] {
  const matches = text.match(/\b(?:not|never|neither|nor|no|cannot|can't|won't|didn't|doesn't|isn't|aren't|wasn't|weren't)\b/gi) || []
  return [...new Set(matches.map((v) => v.toLowerCase().trim()))]
}

export function extractListItems(text: string): string[] {
  const lines = text.split(/\r?\n/)
  return lines
    .map((l) => l.trim())
    .filter((l) => /^[-*•]\s+|^\d+[.)]\s+/.test(l))
}

export const BANNED_AI_CLICHES = [
  "rich tapestry", "dynamic synergies", "dynamic synergy", "paradigm shift", "delve into", "delving into",
  "delve", "multifaceted", "digital landscape", "navigating the landscape",
  "tapestry", "testament to", "beacon of", "beacon", "foster", "fostering", "spearhead",
  "spearheading", "game-changer", "pivotal role", "pivotal", "cornerstone", "seamlessly",
  "crucial to note", "it is crucial to"
] as const

export function checkStructuralIntegrity(original: string, revised: string): StructuralCheck {
  const origParagraphs = original.split(/\n\s*\n/).filter((p) => p.trim().length > 0)
  const revParagraphs = revised.split(/\n\s*\n/).filter((p) => p.trim().length > 0)
  const origLists = extractListItems(original)
  const revLists = extractListItems(revised)
  const origNeg = extractNegations(original)
  const revNeg = extractNegations(revised)

  const entityDiff = compareEntities(original, revised)
  const numbersPreserved = !entityDiff.missing.some((v) => /\d/.test(v))
  const negationsPreserved = origNeg.every((neg) => revNeg.includes(neg)) || origNeg.length === 0
  const listsPreserved = origLists.length === 0 || revLists.length >= origLists.length
  // Allow slight paragraph flexibility if length is single paragraph, but flag collapse if multiple paragraphs
  const paragraphsPreserved = origParagraphs.length <= 1 || revParagraphs.length >= Math.floor(origParagraphs.length * 0.8)

  const detectedCliches = BANNED_AI_CLICHES.filter((c) =>
    new RegExp(`\\b${c}\\b`, "i").test(revised)
  )

  const details: string[] = []
  if (entityDiff.missing.length > 0) {
    const missingNamed = entityDiff.missing.filter((v) => !/\d/.test(v))
    if (missingNamed.length > 0) {
      details.push(`Named entity retention issue: '${missingNamed.join(", ")}' was omitted or modified.`)
    }
  }
  if (!numbersPreserved) details.push("One or more numerical values, currencies (£/$/€), or units appear altered or omitted.")
  if (!negationsPreserved) details.push("A negative qualification (e.g. 'not', 'never', 'cannot') may have been inverted.")
  if (!listsPreserved) details.push("List items or bulleted points from the original text may have been compressed.")
  if (!paragraphsPreserved) details.push("Paragraph structure was condensed compared to the original.")
  if (detectedCliches.length > 0) {
    details.push(`Banned robotic AI cliché detected: ${detectedCliches.join(", ")}.`)
  }

  // Intent preservation check (e.g. interview question converted to declarative advice)
  const isQuestion = original.trim().endsWith("?") || /\b(?:how would you|can you explain|what strategies|describe how|how do you)\b/i.test(original.trim())
  if (isQuestion && !revised.includes("?")) {
    details.push("Intent drift: Source interview question was converted into declarative advice or statements.")
  }

  // Timeline boundary date check
  const closedRangeMatch = original.match(/\b(?:(?:from|between)\s+)?([A-Z][a-z]+\s+\d{1,2}(?:,\s*\d{4})?)\s+(?:to|until|and|-)\s+([A-Z][a-z]+\s+\d{1,2}(?:,\s*\d{4})?)\b/i)
  if (closedRangeMatch) {
    const startD = closedRangeMatch[1]
    const endD = closedRangeMatch[2]
    if (!revised.toLowerCase().includes(startD.toLowerCase()) || !revised.toLowerCase().includes(endD.toLowerCase())) {
      details.push(`Timeline distortion: Closed date range ('${startD} to ${endD}') was summarized or boundary omitted.`)
    }
  }

  // Strict hour deadline check
  const hourMatches = original.match(/\b\d+\s+hours?\b/gi) || []
  for (const hm of hourMatches) {
    if (!revised.toLowerCase().includes(hm.toLowerCase()) && !revised.toLowerCase().includes(hm.toLowerCase().replace(" ", "-"))) {
      details.push(`Deadline alteration: Strict deadline '${hm}' was altered or converted to a flexible timeframe.`)
    }
  }

  return {
    paragraphsPreserved,
    listsPreserved,
    negationsPreserved,
    numbersPreserved,
    details,
  }
}

export function compareEntities(original: string, revised: string) {
  const a = entities(original),
    b = entities(revised)
  const normalized = (s: string) => s.toLowerCase().replace(/\s+/g, " ")
  return {
    preserved: a.filter((x) => b.some((y) => normalized(y) === normalized(x))),
    missing: a.filter((x) => !b.some((y) => normalized(y) === normalized(x))),
    added: b.filter((x) => !a.some((y) => normalized(y) === normalized(x))),
  }
}
export function diffWords(original: string, revised: string) {
  const a = original.split(/(\s+)/),
    b = revised.split(/(\s+)/)
  // Bounded LCS, avoiding quadratic work for the maximum input size.
  if (a.length * b.length > 1_000_000)
    return b.map((text) => ({ text, added: !a.includes(text) }))
  const table = Array.from(
    { length: a.length + 1 },
    () => new Uint16Array(b.length + 1),
  )
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      table[i][j] =
        a[i] === b[j]
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1])
  let i = 0,
    j = 0
  const output: {
    text: string
    added: boolean
  }[] = []
  while (j < b.length) {
    if (i < a.length && a[i] === b[j]) {
      output.push({ text: b[j++], added: false })
      i++
    } else if (i < a.length && table[i + 1][j] >= table[i][j + 1]) i++
    else output.push({ text: b[j++], added: true })
  }
  return output
}
