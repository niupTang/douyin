import { http } from '@/utils/request'

export const ownContentApi = {
  previewDouyinImport: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return http.upload('/own/douyin/import/preview', formData)
  },

  importDouyinWorks: (file, accountName = '太阳鸟') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('accountName', accountName)
    return http.upload('/own/douyin/import', formData)
  },

  getDouyinWorks: (limit = 100) => {
    return http.get('/own/douyin/videos', { limit })
  }
}
