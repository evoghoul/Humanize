import { GoogleGenAI } from "@google/genai"
import type { LlmProvider } from "./types"

export class GeminiProvider implements LlmProvider {
  readonly name = "Google Gemini"
  private ai: GoogleGenAI
  private model: string

  constructor(apiKey: string, modelName?: string) {
    this.ai = new GoogleGenAI({ apiKey, httpOptions: { timeout: 45000 } })
    this.model = modelName || process.env.GEMINI_MODEL || "gemini-3.7-flash"
  }

  async generateJson<T>(prompt: string, systemInstruction?: string): Promise<T> {
    const contents = systemInstruction ? `${systemInstruction}\n\n${prompt}` : prompt
    const modelsToTry = [this.model, "gemini-3.7-flash", "gemini-2.5-flash"]
    const uniqueModels = Array.from(new Set(modelsToTry))
    let lastError: unknown

    for (const model of uniqueModels) {
      try {
        const response = await this.ai.models.generateContent({
          model,
          contents,
          config: { responseMimeType: "application/json", temperature: 0.2 },
        })
        const text = response.text || "{}"
        return JSON.parse(text) as T
      } catch (err) {
        lastError = err
        continue
      }
    }
    throw lastError
  }
}

