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

  getDouyinVideos: (id) => {
    return http.get(`/benchmark/douyin/accounts/${id}/videos`)
  },

  getDouyinVideoAnalysis: (videoId) => {
    return http.get(`/benchmark/douyin/videos/${videoId}/analysis`)
  },

  createDouyinVideoAnalysis: (videoId, force = false) => {
    return http.post(`/benchmark/douyin/videos/${videoId}/analysis`, { force })
  }
}
