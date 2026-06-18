import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import AccountManagement from '../views/AccountManagement.vue'
import MaterialManagement from '../views/MaterialManagement.vue'
import PublishCenter from '../views/PublishCenter.vue'
import About from '../views/About.vue'
import DataView from '../views/DataView.vue'
import BenchmarkManagement from '../views/BenchmarkManagement.vue'
import VideoEditCenter from '../views/VideoEditCenter.vue'
import OneClickVideoEdit from '../views/OneClickVideoEdit.vue'

const routes = [
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
    path: '/video-edit-center',
    name: 'VideoEditCenter',
    component: VideoEditCenter
  },
  {
    path: '/one-click-video-edit',
    name: 'OneClickVideoEdit',
    component: OneClickVideoEdit
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
    path: '/about',
    name: 'About',
    component: About
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
