import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const sessionToken = ref(localStorage.getItem('token') || '')
  const userInfo = ref({
    id: '',
    username: '',
    displayName: ''
  })
  
  const isLoggedIn = ref(Boolean(localStorage.getItem('token')) && localStorage.getItem('auth_mode') === 'license')
  
  const setUserInfo = (info = {}) => {
    userInfo.value = info
    isLoggedIn.value = true
  }

  const setSession = ({ token, user }) => {
    sessionToken.value = token
    localStorage.setItem('token', token)
    localStorage.setItem('auth_mode', 'license')
    setUserInfo(user)
  }
  
  const logout = () => {
    sessionToken.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('auth_mode')
    userInfo.value = {
      id: '',
      username: '',
      displayName: ''
    }
    isLoggedIn.value = false
  }
  
  return {
    sessionToken,
    userInfo,
    isLoggedIn,
    setUserInfo,
    setSession,
    logout
  }
})
