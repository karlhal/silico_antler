const SURROGATE_CHAT_PATTERNS = [
  /\bcan we simulate (?:this|it)\b/i,
  /\bcould we simulate (?:this|it)\b/i,
  /\bsimulate (?:this|it|the current method|the current recommendation)\b/i,
  /\btest (?:this|it) in (?:the )?(?:ai )?surrogate\b/i,
  /\bopen (?:the )?(?:ai )?surrogate\b/i,
  /\btake (?:this|it) to (?:the )?(?:ai )?surrogate\b/i
] as const

const FOLLOW_UP_CHAT_PATTERNS = [
  /\?$/,
  /^(what|why|how|which|who|when|where)\b/i,
  /^(can you|could you|would you|do we|does it|is it|are there)\b/i,
  /^(give me|show me|tell me|summarize|compare|list|explain|walk me through)\b/i,
  /\bexperimental conditions\b/i,
  /\bbest one\b/i,
  /\bvery briefly\b/i,
  /\bbriefly\b/i
] as const

export function isSurrogateChatRequest(input: string): boolean {
  const trimmed = input.trim()
  if (!trimmed) {
    return false
  }

  return SURROGATE_CHAT_PATTERNS.some((pattern) => pattern.test(trimmed))
}

export function looksLikeFollowUpQuestion(input: string): boolean {
  const trimmed = input.trim()
  if (!trimmed) {
    return false
  }

  if (isSurrogateChatRequest(trimmed)) {
    return true
  }

  return FOLLOW_UP_CHAT_PATTERNS.some((pattern) => pattern.test(trimmed))
}
