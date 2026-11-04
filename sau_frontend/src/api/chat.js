import { http } from '@/utils/request'

const conversationUrl = (id) => `/api/chat/conversations/${id}`
export const chatApi = {
  list: () => http.get('/api/chat/conversations'),
  create: () => http.post('/api/chat/conversations'),
  messages: (id) => http.get(`${conversationUrl(id)}/messages`),
  send: (id, prompt) => http.post(`${conversationUrl(id)}/messages`, { prompt }),
  cancel: (id) => http.post(`${conversationUrl(id)}/cancel`),
  options: () => http.get('/api/chat/options'),
  upload: (id, file) => {
    const form = new FormData()
    form.append('file', file)
    return http.upload(`${conversationUrl(id)}/upload`, form)
  },
  publish: (id, data) => http.post(`${conversationUrl(id)}/publish`, data)
}
