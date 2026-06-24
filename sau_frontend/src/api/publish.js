import { http } from '@/utils/request'

export const publishApi = {
  getPublishRecords: () => {
    return http.get('/getPublishRecords')
  },
  // 手动更新单条数据的流量
  updateStats: (data) => {
    return http.post('/publish/updateStats', data)
  },
  // 批量更新流量
  batchUpdateStats: (records) => {
    return http.post('/publish/batchUpdateStats', { records })
  },
  // 获取账号粉丝数
  getAccountFollowers: () => {
    return http.get('/account/followers')
  },
  // 更新账号粉丝数
  updateAccountFollower: (id, follower_count) => {
    return http.post('/account/updateFollower', { id, follower_count })
  }
}
