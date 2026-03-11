import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
})

export async function uploadCSV(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Streaming query — calls the SSE endpoint and calls callbacks as events arrive.
 *
 * @param {string} question
 * @param {number} datasetId
 * @param {object} callbacks
 *   - onToken(text)       — called for each streamed token
 *   - onChart(chartData)  — called once with the final chart JSON
 *   - onDone(contextUsed) — called when stream ends
 *   - onError(message)    — called on error
 */
export async function queryStream(question, datasetId, callbacks) {
  const { onToken, onChart, onDone, onError } = callbacks
  const url = `${API_BASE}/query/stream`

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, dataset_id: datasetId }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Stream request failed' }))
    onError?.(err.detail || 'Request failed')
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by double newlines
    const events = buffer.split('\n\n')
    buffer = events.pop() // keep incomplete last chunk

    for (const event of events) {
      const line = event.trim()
      if (!line.startsWith('data: ')) continue
      try {
        const payload = JSON.parse(line.slice(6))
        switch (payload.type) {
          case 'token':
            onToken?.(payload.text)
            break
          case 'chart':
            onChart?.(payload.data)
            break
          case 'done':
            onDone?.(payload.context_used)
            break
          case 'error':
            onError?.(payload.message)
            break
        }
      } catch (e) {
        // Malformed JSON in SSE — skip
      }
    }
  }
}

// Non-streaming fallback (kept for history replay)
export async function queryData(question, datasetId) {
  const { data } = await api.post('/query', { question, dataset_id: datasetId })
  return data
}

export async function getDashboard(datasetId, refresh = false) {
  const { data } = await api.get(`/dashboard/${datasetId}`, { params: { refresh } })
  return data
}

export async function getSchema(datasetId) {
  const { data } = await api.get('/schema', { params: { dataset_id: datasetId } })
  return data
}

export async function getHistory(datasetId) {
  const { data } = await api.get('/history', { params: { dataset_id: datasetId } })
  return data
}

export async function listDatasets() {
  const { data } = await api.get('/datasets')
  return data
}

export async function checkHealth() {
  const { data } = await api.get('/health')
  return data
}
