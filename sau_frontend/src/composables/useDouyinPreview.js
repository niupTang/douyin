import { ElMessage } from 'element-plus'
import { benchmarkApi } from '@/api/benchmark'

export function useDouyinPreview() {
  const pending = new Set()
  const openDouyinPreview = async (url) => {
    if (!url || pending.has(url)) return
    pending.add(url)
    try {
      await benchmarkApi.openDouyinPreview(url)
    } catch (error) {
      ElMessage.error(error.response?.data?.msg || error.message || '打开作品失败')
    } finally {
      pending.delete(url)
    }
  }
  return { openDouyinPreview }
}
