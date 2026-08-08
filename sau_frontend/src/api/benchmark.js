import { http } from '@/utils/request'

export const benchmarkApi = {
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
