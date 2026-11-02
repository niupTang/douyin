import { http } from '@/utils/request'

export const ownContentApi = {
  listDouyinAccounts: () => {
    return http.get('/own/douyin/accounts')
  },

  previewDouyinImport: (file, userInfoId) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('userInfoId', userInfoId)
    return http.upload('/own/douyin/import/preview', formData)
  },

  importDouyinWorks: (file, userInfoId) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('userInfoId', userInfoId)
    return http.upload('/own/douyin/import', formData)
  },

  getDouyinWorks: (userInfoId, limit = 100) => {
    return http.get('/own/douyin/videos', { userInfoId, limit })
  },

  getAllDouyinWorks: (limit = 100) => {
    return http.get('/own/douyin/videos/all', { limit })
  },

  getExportStatus: (userInfoId) => {
    return http.get('/own/douyin/export/status', { userInfoId })
  },

  runExport: (userInfoId) => {
    return http.post('/own/douyin/export/run', { userInfoId })
  },

  analyzeVideo: (videoId, force = false) => {
    return http.post(`/own/douyin/videos/${videoId}/analysis`, { force })
  }
}
