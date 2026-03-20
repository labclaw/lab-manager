import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import { auth, documents, search, alerts } from '@/lib/api'

describe('api client', () => {
  describe('auth', () => {
    it('login calls POST /auth/login', async () => {
      const result = await auth.login('test@example.com', 'password123')
      expect(result).toEqual({ status: 'ok', user: { id: 1, name: 'Dr. Aris Thorne' } })
    })

    it('me calls GET /auth/me', async () => {
      const result = await auth.me()
      expect(result).toEqual({ user: { id: 1, name: 'Dr. Aris Thorne' } })
    })
  })

  describe('documents', () => {
    it('list calls GET /documents with pagination params', async () => {
      const result = await documents.list(1, 20)
      expect(result.items).toHaveLength(2)
      expect(result.items![0].file_name).toBe('invoice_001.pdf')
      expect(result.total).toBe(2)
      expect(result.page).toBe(1)
    })

    it('list with status filter passes status param', async () => {
      const result = await documents.list(1, 20, 'needs_review')
      expect(result.items).toHaveLength(2)
      expect(result.items![0].file_name).toBe('review_doc_1.pdf')
    })

    it('review calls POST /documents/{id}/review with action body', async () => {
      const body = { action: 'approve' as const, reviewed_by: 'tester', review_notes: 'looks good' }
      const result = await documents.review(1, body)
      expect(result).toEqual({ status: 'ok' })
    })

    it('upload sends FormData to POST /documents/upload', async () => {
      const file = new File(['test content'], 'test.pdf', { type: 'application/pdf' })
      const result = await documents.upload(file)
      expect(result).toEqual({ id: 99, file_name: 'uploaded.pdf', status: 'pending' })
    })
  })

  describe('search', () => {
    it('query calls GET /search?q=...', async () => {
      const result = await search.query('sodium')
      expect(result.items).toHaveLength(1)
      expect(result.items![0]).toMatchObject({ name: 'Sodium Chloride' })
    })

    it('suggest calls GET /search/suggest?q=...', async () => {
      const result = await search.suggest('sod')
      expect(result.suggestions).toEqual([
        'Sodium Chloride',
        'Sodium Hydroxide',
        'Sodium Bicarbonate',
      ])
    })
  })

  describe('alerts', () => {
    it('list calls GET /alerts with no filters', async () => {
      const result = await alerts.list()
      expect(result.items).toHaveLength(2)
      expect(result.total).toBe(2)
    })

    it('list calls GET /alerts with optional filters', async () => {
      const result = await alerts.list({ severity: 'critical', acknowledged: false })
      // MSW default handler returns same data regardless of filters
      expect(result.items).toHaveLength(2)
    })

    it('summary calls GET /alerts/summary', async () => {
      const result = await alerts.summary()
      expect(result.total).toBe(15)
      expect(result.unacknowledged).toBe(10)
      expect(result.by_severity).toEqual({ critical: 2, warning: 8, info: 5 })
    })

    it('acknowledge calls POST /alerts/{id}/acknowledge', async () => {
      const result = await alerts.acknowledge(1)
      expect(result).toEqual({ status: 'ok' })
    })
  })

  describe('error handling', () => {
    it('401 throws "Unauthorized"', async () => {
      server.use(
        http.get('/api/auth/me', () => new HttpResponse(null, { status: 401 })),
      )
      await expect(auth.me()).rejects.toThrow('Unauthorized')
    })

    it('500 throws error message from response', async () => {
      server.use(
        http.get('/api/auth/me', () =>
          HttpResponse.json({ detail: 'Internal server error' }, { status: 500 }),
        ),
      )
      await expect(auth.me()).rejects.toThrow('Internal server error')
    })

    it('500 falls back to status text when no detail', async () => {
      server.use(
        http.get('/api/auth/me', () =>
          new HttpResponse('not json', { status: 500, statusText: 'Internal Server Error' }),
        ),
      )
      await expect(auth.me()).rejects.toThrow('Internal Server Error')
    })
  })
})
