import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref({
    id: '',
    username: '',
    displayName: ''
  })
  
  const isLoggedIn = ref(Boolean(localStorage.getItem('token')))
  
  const setUserInfo = (info = {}) => {
    userInfo.value = info
    isLoggedIn.value = true
  }

  const setSession = ({ token, user }) => {
    localStorage.setItem('token', token)
    setUserInfo(user)
  }
  
  const logout = () => {
    localStorage.removeItem('token')
    userInfo.value = {
      id: '',
      username: '',
      displayName: ''
    }
    isLoggedIn.value = false
  }
  
  return {
    userInfo,
    isLoggedIn,
    setUserInfo,
    setSession,
    logout
  }
})
