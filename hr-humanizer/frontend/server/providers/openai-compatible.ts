import type { LlmProvider } from "./types"

export class OpenAiCompatibleProvider implements LlmProvider {
  readonly name: string
  private baseUrl: string
  private apiKey: string
  private model: string

  constructor(options?: { baseUrl?: string; apiKey?: string; model?: string; name?: string }) {
    this.baseUrl = (options?.baseUrl || process.env.OPENAI_BASE_URL || "https://api.openai.com/v1").replace(/\/+$/, "")
    this.apiKey = options?.apiKey || process.env.OPENAI_API_KEY || "dummy-key"
    this.model = options?.model || process.env.OPENAI_MODEL || "gpt-4o-mini"
    this.name = options?.name || `OpenAI-Compatible (${this.model})`
  }

  async generateJson<T>(prompt: string, systemInstruction?: string): Promise<T> {
    const messages: { role: string; content: string }[] = []
    if (systemInstruction) {
      messages.push({ role: "system", content: systemInstruction })
    }
    messages.push({ role: "user", content: prompt })

    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        temperature: 0.2,
        response_format: { type: "json_object" },
      }),
      signal: AbortSignal.timeout(45000),
    })

    if (!res.ok) {
      const errText = await res.text().catch(() => "")
      const err: Error & { status?: number } = new Error(`External model API error: ${res.status} ${errText}`)
      err.status = res.status
      throw err
    }

    const json = (await res.json()) as { choices?: { message?: { content?: string } }[] }
    const content = json.choices?.[0]?.message?.content || "{}"
    return JSON.parse(content) as T
  }
}
