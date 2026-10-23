import type { Plugin } from "vite"
import { ApiError, refine } from "./refine"

const FASTAPI_URL = process.env.FASTAPI_URL || process.env.BACKEND_URL || "http://127.0.0.1:8000"

async function forwardToFastApi(input: unknown) {
  const response = await fetch(`${FASTAPI_URL}/api/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    signal: AbortSignal.timeout(45000),
  })
  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as { detail?: string; error?: string }
    throw new ApiError(response.status, errorData.detail || errorData.error || "FastAPI backend error.")
  }
  return await response.json()
}

export default function verbaApi(): Plugin {
  return {
    name: "verba-api",
    configureServer(server) {
      server.middlewares.use("/api/refine", async (req, res) => {
        res.setHeader("Content-Type", "application/json")
        if (req.method !== "POST") {
          res.statusCode = 405
          res.end(JSON.stringify({ error: "Use POST." }))
          return
        }
        try {
          let body = ""
          for await (const chunk of req) {
            body += chunk
            if (Buffer.byteLength(body) > 64000)
              throw new ApiError(413, "Request is too large.")
          }
          let input: unknown
          try {
            input = JSON.parse(body)
          } catch {
            throw new ApiError(400, "Invalid JSON request.")
          }

          if (process.env.AI_PROVIDER?.toLowerCase() === "fastapi") {
            try {
              const result = await forwardToFastApi(input)
              res.end(JSON.stringify(result))
              return
            } catch (err) {
              if (err instanceof ApiError) throw err
              throw new ApiError(503, `FastAPI backend at ${FASTAPI_URL} is unreachable: ${err instanceof Error ? err.message : String(err)}`)
            }
          }

          try {
            res.end(JSON.stringify(await refine(input)))
          } catch (refineErr) {
            const isConfigError = refineErr instanceof Error && (
              refineErr.message.includes("GEMINI_API_KEY") ||
              refineErr.message.includes("not configured yet")
            )
            if (isConfigError) {
              try {
                const fastApiResult = await forwardToFastApi(input)
                res.end(JSON.stringify(fastApiResult))
                return
              } catch {
                throw new ApiError(503, `No Gemini API key set and FastAPI backend at ${FASTAPI_URL} is offline. Please start the backend or configure GEMINI_API_KEY.`)
              }
            }
            throw refineErr
          }
        } catch (e) {
          res.statusCode = e instanceof ApiError ? e.status : 500
          res.end(
            JSON.stringify({
              error:
                e instanceof ApiError
                  ? e.message
                  : "Unable to process this request.",
            }),
          )
        }
      })
    },
  }
}
