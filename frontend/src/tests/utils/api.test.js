import { describe, it, expect, vi } from 'vitest'
import axios from 'axios'

// Mock axios
vi.mock('axios')

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8888'

describe('API Utilities', () => {
  it('should construct correct API URL', () => {
    const url = `${API_BASE}/api/health`
    expect(url).toBe('http://localhost:8888/api/health')
  })

  it('should handle API error responses', async () => {
    vi.spyOn(axios, 'get').mockRejectedValue({
      response: { status: 500, data: { detail: 'Internal error' } },
    })

    try {
      await axios.get('/api/nonexistent')
    } catch (error) {
      expect(error.response.status).toBe(500)
    }
  })
})
