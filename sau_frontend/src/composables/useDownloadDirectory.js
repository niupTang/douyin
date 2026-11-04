import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { browserSettingsApi } from '@/api/browserSettings'


export function useDownloadDirectory() {
  const downloadDirectory = ref('')
  const downloadDirectoryValid = ref(false)

  const loadDownloadDirectory = async () => {
    const response = await browserSettingsApi.getDownloadDirectory()
    downloadDirectory.value = response.data?.path || ''
    downloadDirectoryValid.value = Boolean(response.data?.valid)
    return downloadDirectoryValid.value
  }

  const chooseDownloadDirectory = async () => {
    try {
      let path
      if (window.sunbirdDesktop?.chooseDownloadDirectory) {
        path = await window.sunbirdDesktop.chooseDownloadDirectory()
      } else {
        const result = await ElMessageBox.prompt('输入本机下载目录的绝对路径', '选择下载目录', {
          inputValue: downloadDirectory.value,
          confirmButtonText: '保存',
          cancelButtonText: '取消'
        })
        path = result.value
      }
      if (!path) return false
      const response = await browserSettingsApi.saveDownloadDirectory(path)
      downloadDirectory.value = response.data.path
      downloadDirectoryValid.value = true
      ElMessage.success('下载目录已保存')
      return true
    } catch {
      return false
    }
  }

  const ensureDownloadDirectory = async () => {
    if (await loadDownloadDirectory()) return true
    return chooseDownloadDirectory()
  }

  return {
    downloadDirectory,
    downloadDirectoryValid,
    loadDownloadDirectory,
    chooseDownloadDirectory,
    ensureDownloadDirectory
  }
}
