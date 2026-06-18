import { http } from '@/utils/request'

export const dashboardApi = {
  getStats: () => {
    return http.get('/dashboard/stats')
  }
}
