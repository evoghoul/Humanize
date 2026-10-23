export interface LlmProvider {
  readonly name: string
  generateJson<T>(prompt: string, systemInstruction?: string): Promise<T>
}
