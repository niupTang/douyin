import { http } from '@/utils/request'

export const browserSettingsApi = {
  getDownloadDirectory: () => http.get('/api/browser/download-directory'),
  saveDownloadDirectory: (path) => http.put('/api/browser/download-directory', { path }),
  saveMarkdown: (filename, content) => http.post('/api/browser/download-markdown', { filename, content })
}
