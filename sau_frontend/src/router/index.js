import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import AccountManagement from '../views/AccountManagement.vue'
import MaterialManagement from '../views/MaterialManagement.vue'
import PublishCenter from '../views/PublishCenter.vue'
import About from '../views/About.vue'
import DataView from '../views/DataView.vue'
import BenchmarkManagement from '../views/BenchmarkManagement.vue'
import IdeaRadar from '../views/IdeaRadar.vue'
import OwnContentReview from '../views/OwnContentReview.vue'
import Login from '../views/Login.vue'
import AgentModels from '../views/AgentModels.vue'
import KouboStudio from '../views/KouboStudio.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { public: true }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard
  },
  {
    path: '/account-management',
    name: 'AccountManagement',
    component: AccountManagement
  },
  {
    path: '/material-management',
    name: 'MaterialManagement',
    component: MaterialManagement
  },
  {
    path: '/publish-center',
    name: 'PublishCenter',
    component: PublishCenter
  },
  {
    path: '/data',
    name: 'DataView',
    component: DataView
  },
  {
    path: '/benchmark-management',
    name: 'BenchmarkManagement',
    component: BenchmarkManagement
  },
  {
    path: '/idea-radar',
    name: 'IdeaRadar',
    component: IdeaRadar
  },
  {
    path: '/own-content-review',
    name: 'OwnContentReview',
    component: OwnContentReview
  },
  {
    path: '/agent-models',
    name: 'AgentModels',
    component: AgentModels
  },
  {
    path: '/koubo-studio',
    name: 'KouboStudio',
    component: KouboStudio
  },
  {
    path: '/about',
    name: 'About',
    component: About
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.public && token && to.path === '/login') {
    return '/'
  }
  if (!to.meta.public && !token) {
    return {
      path: '/login',
      query: { redirect: to.fullPath }
    }
  }
})

export default router
