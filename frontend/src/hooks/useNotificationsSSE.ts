import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { tokenService } from '../services/tokenService'
import { API_URL } from '../services/api'

/**
 * Connexion au flux SSE `/notifications/stream` : invalide la liste des notifications
 * lorsque le serveur pousse un événement (processus API uniquement).
 */
export function useNotificationsSSE(enabled: boolean): boolean {
  const qc = useQueryClient()
  const [connected, setConnected] = useState(false)
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null)

  useEffect(() => {
    if (!enabled) {
      setConnected(false)
      return
    }

    let cancelled = false
    let attempt = 0

    const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

    const invalidate = () => {
      void qc.invalidateQueries({ queryKey: ['in-app-notifications'] })
    }

    const run = async () => {
      while (!cancelled) {
        const token = tokenService.getAccessToken()
        if (!token) {
          setConnected(false)
          await sleep(2000)
          continue
        }

        try {
          const res = await fetch(`${API_URL}/notifications/stream`, {
            headers: {
              Authorization: `Bearer ${token}`,
              Accept: 'text/event-stream',
            },
          })
          if (!res.ok || !res.body) {
            throw new Error(`sse ${res.status}`)
          }

          setConnected(true)
          attempt = 0
          invalidate()

          const reader = res.body.getReader()
          readerRef.current = reader
          const decoder = new TextDecoder()
          let buffer = ''

          while (!cancelled) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })

            const blocks = buffer.split('\n\n')
            buffer = blocks.pop() || ''

            for (const block of blocks) {
              for (const rawLine of block.split('\n')) {
                const line = rawLine.trimEnd()
                if (line.startsWith('data: ')) {
                  invalidate()
                }
              }
            }
          }
        } catch {
          if (cancelled) break
          setConnected(false)
          attempt += 1
          const delay = Math.min(3000 * attempt, 30000)
          await sleep(delay)
        } finally {
          void readerRef.current?.cancel()
          readerRef.current = null
        }
      }
      setConnected(false)
    }

    void run()
    return () => {
      cancelled = true
      void readerRef.current?.cancel()
      readerRef.current = null
    }
  }, [enabled, qc])

  return connected
}
