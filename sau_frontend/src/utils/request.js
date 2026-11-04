import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useUserStore } from '@/stores/user'
import { createSessionRecovery } from './sessionRecovery'

const recoverSession = createSessionRecovery({
  getDesktop: () => window.sunbirdDesktop,
  saveSession: session => useUserStore().setSession(session)
})

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409',
  headers: {
    'Content-Type': 'application/json'
  }
})

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

request.interceptors.response.use(
  (response) => {
    const { data } = response
    const businessCode = Number(data?.code)
    if (data?.success || (businessCode >= 200 && businessCode < 300)) {
      return data
    }
    ElMessage.error(data.message || data.msg || '请求失败')
    return Promise.reject(new Error(data.message || data.msg || '请求失败'))
  },
  async (error) => {
    if (error.response) {
      const { status, data } = error.response
      const offlineExpired = status === 403 && data?.data?.reasonCode === 'OFFLINE_GRACE_EXPIRED'
      // These responses are returned before the backend executes publishing.
      // Retry only authentication failures, never network errors or publisher errors.
      if ((status === 401 || offlineExpired) && error.config && !error.config._sessionRetried) {
        error.config._sessionRetried = true
        try {
          const session = await recoverSession({ refreshLicense: offlineExpired })
          if (session) {
            error.config.headers = error.config.headers || {}
            error.config.headers.Authorization = `Bearer ${session.token}`
            return request(error.config)
          }
        } catch (recoveryError) {
          error.sessionRecoveryMessage = recoveryError.message
        }
      }
      if (status === 401) {
        useUserStore().logout()
        ElMessage.error(error.sessionRecoveryMessage || data?.message || '请重新登录')
        if (router.currentRoute.value.path !== '/login') {
          router.push({
            path: '/login',
            query: { redirect: router.currentRoute.value.fullPath }
          })
        }
      } else {
        ElMessage.error(error.sessionRecoveryMessage || data?.message || data?.msg || '请求失败')
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export const http = {
  get(url, params) {
    return request.get(url, { params })
  },

  post(url, data, config = {}) {
    return request.post(url, data, config)
  },

  put(url, data, config = {}) {
    return request.put(url, data, config)
  },

  delete(url, params) {
    return request.delete(url, { params })
  },

  upload(url, formData) {
    return request.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}

export default request
