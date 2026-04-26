import type {
  PromptRecognitionSummary,
  RecognitionState,
  RecognizedAnalyte,
  RecognizedField,
  SourceTextSpan
} from '../types'

interface AnalyteCatalogEntry {
  key: string
  name: string
  smiles: string
  aliases: string[]
}

interface AmbiguousAliasEntry {
  alias: string
  candidates: string[]
}

const ANALYTE_CATALOG: AnalyteCatalogEntry[] = [
  {
    key: 'metformin',
    name: 'Metformin',
    smiles: 'CN(C)C(=N)N=C(N)N',
    aliases: ['metformin', 'metformin hydrochloride']
  },
  {
    key: 'caffeine',
    name: 'Caffeine',
    smiles: 'Cn1cnc2n(C)c(=O)n(C)c(=O)c12',
    aliases: ['caffeine']
  },
  {
    key: 'ibuprofen',
    name: 'Ibuprofen',
    smiles: 'CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O',
    aliases: ['ibuprofen']
  },
  {
    key: 'acetaminophen',
    name: 'Acetaminophen',
    smiles: 'CC(=O)NC1=CC=C(O)C=C1O',
    aliases: ['acetaminophen', 'paracetamol']
  },
  {
    key: 'lidocaine',
    name: 'Lidocaine',
    smiles: 'CCN(CC)C(=O)C1=CN(C2=C1C=CC=C2)C',
    aliases: ['lidocaine']
  },
  {
    key: 'warfarin',
    name: 'Warfarin',
    smiles: 'CC(C)(O)C(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O',
    aliases: ['warfarin']
  },
  {
    key: 'atorvastatin',
    name: 'Atorvastatin',
    smiles: 'CC(C)c1n(CC[C@@H](O)C[C@@H](O)CC(O)=O)c(c2ccc(F)cc2)c(c3ccc(cc3)C(C)(C)C)c1C(=O)Nc4ccccc4',
    aliases: ['atorvastatin', 'atorvastatin calcium']
  },
  {
    key: 'amlodipine',
    name: 'Amlodipine',
    smiles: 'CCOC(=O)C1=C(C)NC(C(=O)OC)C(C1c1cccc(n1)Cl)N',
    aliases: ['amlodipine', 'amlodipine besylate']
  }
]

const AMBIGUOUS_ALIASES: AmbiguousAliasEntry[] = [
  {
    alias: 'cortisone',
    candidates: ['Hydrocortisone', 'Cortisone acetate']
  }
]

const MATRIX_PATTERNS = [
  { value: 'Human Plasma', pattern: /\bhuman plasma\b/i },
  { value: 'Bovine Serum', pattern: /\bbovine serum\b/i },
  { value: 'Water', pattern: /\bwater\b/i },
  { value: 'Solvent', pattern: /\bsolvent\b/i }
] as const

const DETECTOR_PATTERNS = [
  { value: 'MS-compatible method required', pattern: /\b(ms\/ms|msms|mass spec|mass spectrom(?:etry|etric)|lc-ms|hplc-ms)\b/i },
  { value: 'PDA', pattern: /\bpda\b/i },
  { value: 'ELSD', pattern: /\belsd\b/i },
  { value: 'UV-Vis', pattern: /\b(uv|uv-vis)\b/i }
] as const

const SOURCE_PATTERNS = [
  { value: 'Local corpus', pattern: /\b(local corpus|internal corpus|review-backed corpus)\b/i },
  { value: 'Open access', pattern: /\b(open access|literature|papers?|publications?)\b/i }
] as const

const RUNTIME_PATTERN = /(\d+(?:\.\d+)?)\s*(min|mins|minute|minutes)\b/i

const REQUEST_PATTERNS = [
  /\b(?:quantification|determination|analysis|assay|measurement|screening|profiling|separation|method(?: development)?)\s+of\s+([^.;,\n]+?)(?=\s+(?:in|from|using|by|with|on)\b|[.;,\n]|$)/i,
  /\b(?:for|against)\s+([^.;,\n]+?)(?=\s+(?:in|from|using|by|with|on)\b|[.;,\n]|$)/i
]

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function createSpan(start: number, end: number, text: string): SourceTextSpan {
  return { start, end, text }
}

function createField(
  field: RecognizedField['field'],
  value: string,
  span: SourceTextSpan | null
): RecognizedField {
  return {
    field,
    value,
    status: 'recognized',
    provenance: 'recognized',
    confidenceLabel: 'high confidence',
    sourceTextSpan: span
  }
}

function matchFirstPattern(
  input: string,
  patterns: ReadonlyArray<{ value: string; pattern: RegExp }>,
  field: RecognizedField['field']
): RecognizedField | null {
  for (const candidate of patterns) {
    const match = candidate.pattern.exec(input)
    if (match?.index != null) {
      return createField(
        field,
        candidate.value,
        createSpan(match.index, match.index + match[0].length, match[0])
      )
    }
  }

  return null
}

function detectAnalytes(input: string): RecognizedAnalyte[] {
  const matches: RecognizedAnalyte[] = []
  const seen = new Set<string>()

  ANALYTE_CATALOG.forEach((entry) => {
    entry.aliases.forEach((alias) => {
      const pattern = new RegExp(`\\b${escapeRegExp(alias)}\\b`, 'ig')
      let match: RegExpExecArray | null
      while ((match = pattern.exec(input)) !== null) {
        const span = createSpan(match.index, match.index + match[0].length, match[0])
        const dedupeKey = `${entry.key}:${span.start}`
        if (seen.has(dedupeKey)) {
          continue
        }
        seen.add(dedupeKey)
        matches.push({
          id: dedupeKey,
          field: 'analyte',
          value: entry.name,
          status: 'recognized',
          provenance: 'recognized',
          confidenceLabel: alias.toLowerCase() === entry.name.toLowerCase() ? 'high confidence' : 'medium confidence',
          sourceTextSpan: span,
          resolvedSmiles: entry.smiles,
          resolvedName: entry.name,
          structurePreviewState: 'ready',
          lookupSource: 'prompt_recognition',
          lookupError: null
        })
      }
    })
  })

  AMBIGUOUS_ALIASES.forEach((entry) => {
    const pattern = new RegExp(`\\b${escapeRegExp(entry.alias)}\\b`, 'ig')
    let match: RegExpExecArray | null
    while ((match = pattern.exec(input)) !== null) {
      const span = createSpan(match.index, match.index + match[0].length, match[0])
      const dedupeKey = `ambiguous:${entry.alias}:${span.start}`
      if (seen.has(dedupeKey)) {
        continue
      }
      seen.add(dedupeKey)
      matches.push({
        id: dedupeKey,
        field: 'analyte',
        value: match[0],
        status: 'ambiguous',
        provenance: 'recognized',
        confidenceLabel: 'needs confirmation',
        sourceTextSpan: span,
        resolvedSmiles: null,
        resolvedName: null,
        structurePreviewState: 'unavailable',
        lookupSource: null,
        lookupError: `I found "${match[0]}", but it maps to multiple possible compounds.`,
        ambiguityCandidates: entry.candidates
      })
    }
  })

  if (matches.length === 0) {
    for (const pattern of REQUEST_PATTERNS) {
      const match = pattern.exec(input)
      if (!match || match.index == null) {
        continue
      }

      const rawValue = match[1]?.trim().replace(/\s+/g, ' ')
      if (!rawValue || /\b(hplc|uplc|lc|ms|uv|method|plasma|serum|water|solvent)\b/i.test(rawValue)) {
        continue
      }

      matches.push({
        id: `unresolved:${match.index}`,
        field: 'analyte',
        value: rawValue,
        status: 'unresolved',
        provenance: 'recognized',
        confidenceLabel: 'low confidence',
        sourceTextSpan: createSpan(match.index, match.index + match[0].length, match[0]),
        resolvedSmiles: null,
        resolvedName: null,
        structurePreviewState: 'unavailable',
        lookupSource: null,
        lookupError: `I found a likely analyte phrase for "${rawValue}", but I could not resolve a structure yet.`
      })
      break
    }
  }

  return matches.sort((left, right) => (left.sourceTextSpan?.start || 0) - (right.sourceTextSpan?.start || 0))
}

export function buildEmptyPromptRecognition(): PromptRecognitionSummary {
  return {
    analytes: [],
    matrix: null,
    detector: null,
    runtime: null,
    sourceMode: null,
    unresolvedItems: []
  }
}

export function detectPromptRecognition(input: string): PromptRecognitionSummary {
  const trimmed = input.trim()
  if (!trimmed) {
    return buildEmptyPromptRecognition()
  }

  const analytes = detectAnalytes(trimmed)
  const matrix = matchFirstPattern(trimmed, MATRIX_PATTERNS, 'matrix')
  const detector = matchFirstPattern(trimmed, DETECTOR_PATTERNS, 'detector')
  const sourceMode = matchFirstPattern(trimmed, SOURCE_PATTERNS, 'source_mode')
  const runtimeMatch = RUNTIME_PATTERN.exec(trimmed)
  const runtime =
    runtimeMatch?.index != null
      ? createField(
          'runtime',
          `${runtimeMatch[1]} min`,
          createSpan(runtimeMatch.index, runtimeMatch.index + runtimeMatch[0].length, runtimeMatch[0])
        )
      : null

  return {
    analytes,
    matrix,
    detector,
    runtime,
    sourceMode,
    unresolvedItems: analytes
      .filter((analyte) => analyte.status === 'ambiguous' || analyte.status === 'unresolved' || analyte.status === 'error')
      .map((analyte) => analyte.lookupError || `Recognition needs attention for ${analyte.value}.`)
  }
}

export function updateRecognizedAnalyte(
  analyte: RecognizedAnalyte,
  updates: Partial<RecognizedAnalyte>
): RecognizedAnalyte {
  const nextStatus = (updates.status || analyte.status) as RecognitionState
  return {
    ...analyte,
    ...updates,
    status: nextStatus,
    structurePreviewState:
      updates.structurePreviewState ||
      (nextStatus === 'recognized'
        ? 'ready'
        : nextStatus === 'recognizing'
          ? 'loading'
          : nextStatus === 'error'
            ? 'error'
            : 'unavailable')
  }
}
