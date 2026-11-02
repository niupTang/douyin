import { http } from '@/utils/request'

export const benchmarkApi = {
  discoverCandidates: (data) => http.post('/benchmark/douyin/discovery-tasks', data),
  getCandidateDiscovery: (taskId) => http.get(`/benchmark/douyin/discovery-tasks/${taskId}`),
  importCandidate: (taskId, candidateId) => http.post(`/benchmark/douyin/discovery-tasks/${taskId}/candidates/${candidateId}/import`),
  openDouyinPreview: (url) => http.post('/benchmark/douyin/preview', { url }, { timeout: 75000 }),
  saveDouyinSession: () => http.post('/benchmark/douyin/session/save'),
  addDouyinAccount: (homepageUrl) => {
    return http.post('/benchmark/douyin/accounts', { homepageUrl })
  },

  getDouyinAccounts: () => {
    return http.get('/benchmark/douyin/accounts')
  },

  syncDouyinAccount: (id) => {
    return http.post(`/benchmark/douyin/accounts/${id}/sync`)
  },

  deleteDouyinAccount: (id) => {
    return http.delete(`/benchmark/douyin/accounts/${id}`)
  },

  getDouyinVideos: (id) => {
    return http.get(`/benchmark/douyin/accounts/${id}/videos`)
  },

  getDouyinVideoAnalysis: (videoId) => {
    return http.get(`/benchmark/douyin/videos/${videoId}/analysis`)
  },

  createDouyinVideoAnalysis: (videoId, force = false) => {
    return http.post(`/benchmark/douyin/videos/${videoId}/analysis`, { force })
  },

  autoDiscoverDouyinAccounts: ({ keywords, limit = 5, maxVideos = 10 }) => {
    return http.post('/benchmark/douyin/auto-discover', { keywords, limit, maxVideos })
  },

  createContentSearch: ({ keyword, targetCount = 50 }) => {
    return http.post('/benchmark/douyin/content-search', { keyword, targetCount })
  },

  openDouyinLogin: () => http.post('/benchmark/douyin/login'),

  getContentSearchTask: (taskId) => http.get(`/benchmark/douyin/content-search/${taskId}`),

  getContentSearchResults: (taskId) => http.get(`/benchmark/douyin/content-search/${taskId}/results`),

  getAllDouyinVideos: (params = {}) => http.get('/benchmark/douyin/videos', params),

  getIdeaRadarVideos: (limit = 80) => {
    return http.get('/idea-radar/douyin/videos', { limit })
  },

  analyzeIdeaRadarVideo: (videoId, targetDirection = 'AI 生产系统研究员', options = {}) => {
    return http.post(`/idea-radar/douyin/videos/${videoId}/analyze`, {
      targetDirection,
      force: Boolean(options.force),
      forceTranscription: Boolean(options.forceTranscription)
    })
  },

  getIdeaRadarStatus: (videoId) => {
    return http.get(`/idea-radar/douyin/videos/${videoId}/status`)
  }
}
