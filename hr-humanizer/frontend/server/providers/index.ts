import type { LlmProvider } from "./types"
import { GeminiProvider } from "./gemini"
import { OpenAiCompatibleProvider } from "./openai-compatible"

export * from "./types"
export * from "./gemini"
export * from "./openai-compatible"

export function getLlmProvider(): LlmProvider {
  const providerType = process.env.AI_PROVIDER?.toLowerCase()

  if (providerType === "openai_compatible" || providerType === "openai" || (!process.env.GEMINI_API_KEY && process.env.OPENAI_BASE_URL)) {
    return new OpenAiCompatibleProvider()
  }

  const geminiKey = process.env.GEMINI_API_KEY
  if (!geminiKey) {
    throw new Error(
      "The AI service is not configured yet. Add GEMINI_API_KEY (or OPENAI_BASE_URL / AI_PROVIDER) on the server to enable rewriting. Your text is safe here."
    )
  }

  return new GeminiProvider(geminiKey)
}
