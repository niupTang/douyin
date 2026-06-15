import { http } from '@/utils/request'

export const publishApi = {
  getPublishRecords: () => {
    return http.get('/getPublishRecords')
  }
}
