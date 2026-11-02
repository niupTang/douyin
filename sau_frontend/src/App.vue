<template>
  <router-view v-if="isLoginPage" />
  <el-container v-else class="app-shell">
    <el-aside :width="isCollapse ? '72px' : '248px'" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">↗</div>
        <div v-show="!isCollapse" class="brand-copy">
          <strong>Sunbird OS</strong>
          <span>本地内容运营工作台</span>
        </div>
      </div>

      <el-menu
        :router="true"
        :default-active="activeMenu"
        :collapse="isCollapse"
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>增长总览</template>
        </el-menu-item>
        <el-menu-item index="/benchmark-management">
          <el-icon><Aim /></el-icon>
          <template #title>抖音对标管理</template>
        </el-menu-item>
        <el-menu-item index="/benchmark-search">
          <el-icon><Search /></el-icon>
          <template #title>抖音搜索</template>
        </el-menu-item>
        <el-menu-item index="/idea-radar">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>爆款拆解</template>
        </el-menu-item>
        <el-menu-item index="/own-content-review">
          <el-icon><TrendCharts /></el-icon>
          <template #title>作品复盘</template>
        </el-menu-item>
        <el-menu-item index="/account-diagnosis">
          <el-icon><Aim /></el-icon>
          <template #title>账号诊断</template>
        </el-menu-item>
        <el-menu-item index="/material-management">
          <el-icon><Picture /></el-icon>
          <template #title>素材资产</template>
        </el-menu-item>
        <el-menu-item index="/koubo-studio">
          <el-icon><VideoCamera /></el-icon>
          <template #title>口播工作台</template>
        </el-menu-item>
        <el-menu-item index="/publish-center">
          <el-icon><Upload /></el-icon>
          <template #title>发布中心</template>
        </el-menu-item>
        <el-menu-item index="/account-management">
          <el-icon><User /></el-icon>
          <template #title>账号管理</template>
        </el-menu-item>
        <el-menu-item index="/data">
          <el-icon><PieChart /></el-icon>
          <template #title>数据明细</template>
        </el-menu-item>
        <el-menu-item index="/agent-models">
          <el-icon><Setting /></el-icon>
          <template #title>Agent 模型</template>
        </el-menu-item>
      </el-menu>

      <div v-show="!isCollapse" class="sidebar-note">
        <span>本周重点</span>
        <strong>把每条内容变成下一条的证据</strong>
      </div>
    </el-aside>

    <el-container class="workspace">
      <el-header class="topbar">
        <button class="icon-button" aria-label="切换侧边栏" @click="toggleSidebar"><el-icon><Fold /></el-icon></button>
        <div class="global-search"><el-icon><Search /></el-icon><span>搜索作品、对标账号或关键词...</span><kbd>⌘ K</kbd></div>
        <div class="topbar-actions">
          <el-button class="sync-button" text :icon="Refresh">同步数据</el-button>
          <el-button class="new-button" type="primary" :icon="Plus">新建复盘</el-button>
          <button class="notification-button" aria-label="通知"><el-icon><Bell /></el-icon><i></i></button>
          <button class="theme-button" aria-label="切换主题">☼</button>
          <div class="profile"><span class="profile-avatar"><el-icon><User /></el-icon></span><span class="profile-name">用户</span><el-icon><ArrowDown /></el-icon></div>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Aim,
  ArrowDown,
  Bell,
  DataAnalysis,
  Fold,
  HomeFilled,
  Picture,
  PieChart,
  Plus,
  Refresh,
  Search,
  Setting,
  SwitchButton,
  TrendCharts,
  Upload,
  User,
  VideoCamera
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isCollapse = ref(false)

const pageMeta = {
  '/': { kicker: 'Dashboard', title: '增长总览' },
  '/benchmark-management': { kicker: 'Benchmark', title: '抖音对标管理' },
  '/benchmark-search': { kicker: 'Search', title: '抖音搜索' },
  '/idea-radar': { kicker: 'Insight', title: '爆款拆解' },
  '/own-content-review': { kicker: 'Review', title: '作品复盘' },
  '/account-diagnosis': { kicker: 'Diagnosis', title: '账号流量诊断' },
  '/material-management': { kicker: 'Assets', title: '素材资产' },
  '/koubo-studio': { kicker: 'Koubo Studio', title: '口播生产工作台' },
  '/publish-center': { kicker: 'Publish', title: '发布中心' },
  '/account-management': { kicker: 'Accounts', title: '账号管理' },
  '/data': { kicker: 'Data', title: '数据明细' },
  '/agent-models': { kicker: 'Settings', title: 'Agent 模型' }
}

const activeMenu = computed(() => route.path)
const routeMeta = computed(() => pageMeta[route.path] || pageMeta['/'])
const isLoginPage = computed(() => route.path === '/login')

const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}

const logout = async () => {
  try {
    await ElMessageBox.confirm('解绑后本机将退出授权，卡密可用于重新激活其他电脑。是否继续？', '解绑当前设备', { type: 'warning' })
    if (window.sunbirdDesktop?.deactivateLicense) await window.sunbirdDesktop.deactivateLicense()
    userStore.logout()
    router.replace('/login')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '解绑失败')
  }
}
</script>

<style lang="scss" scoped>
.app-shell {
  min-height: 100vh;
  background:
    radial-gradient(ellipse 70% 55% at 0% 0%, #ffe4e0 0%, #fff8f7 36%, transparent 68%),
    radial-gradient(ellipse 75% 65% at 100% 100%, #dceaff 0%, #f3f7ff 42%, transparent 75%),
    linear-gradient(145deg, #ffffff 0%, #f6f9ff 100%);
}

.app-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden;
  border-right: 1px solid #e6e8ec;
  background: rgba(255, 255, 255, 0.76);
  backdrop-filter: blur(16px);
  transition: width 0.24s ease;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 88px;
  padding: 0 18px;
  border-bottom: 1px solid #edf2f8;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 14px 14px 14px 4px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  background: linear-gradient(145deg, #ff6d59, #ef3d40);
  color: #ffffff;
  font-size: 24px;
  font-weight: 800;
  transform: rotate(-28deg);
}

.brand-copy {
  min-width: 0;

  strong,
  span {
    display: block;
  }

  strong {
    color: #14171f;
    font-size: 16px;
  }

  span {
    margin-top: 2px;
    color: #7a8493;
    font-size: 12px;
  }
}

.sidebar-menu {
  border-right: 0;
  padding: 18px 10px;

  :deep(.el-menu-item) {
    height: 46px;
    margin-bottom: 6px;
    border-radius: 11px;
    color: #66758f;
    font-size: 15px;
  }

  :deep(.el-menu-item.is-active) {
    background: linear-gradient(100deg, #ff6557, #ff8470);
    color: #ffffff;
  }
}

.sidebar-note {
  position: absolute;
  right: 14px;
  bottom: 14px;
  left: 14px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;

  span,
  strong {
    display: block;
  }

  span {
    margin-bottom: 6px;
    color: #7a8493;
    font-size: 12px;
  }

  strong {
    color: #1f2937;
    font-size: 13px;
    line-height: 1.5;
  }
}

.workspace {
  min-width: 0;
}

.topbar {
  height: 66px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid #e4ebf5;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(12px);
}

.icon-button {
  width: 36px;
  height: 36px;
  border: 1px solid #e4ebf5;
  border-radius: 11px;
  background: #f7faff;
  color: #4d6d9b;
  cursor: pointer;
}

.global-search {
  width: min(430px, 42vw);
  height: 40px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  border: 1px solid #e3ebf5;
  border-radius: 11px;
  background: #f6f9fd;
  color: #a0adbf;
  font-size: 13px;
}
.global-search kbd { margin-left: auto; padding: 2px 7px; border: 1px solid #e0e8f3; border-radius: 6px; background: #fff; color: #8c9ab0; font-size: 11px; }
.global-search .el-icon { color:#6888b6; font-size:18px; }

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}
.sync-button { color:#71819a; }.new-button { border-radius:9px; background:#ff6859; border-color:#ff6859; }.notification-button,.theme-button { position:relative; width:36px; height:36px; display:grid; place-items:center; color:#536987; font-size:20px; }.notification-button i { position:absolute; top:4px; right:4px; width:7px; height:7px; border-radius:50%; background:#ff6557; }.profile { display:flex; align-items:center; gap:7px; padding-left:10px; border-left:1px solid #e7edf5; color:#293a56; font-size:13px; }.profile-avatar { width:32px; height:32px; display:grid; place-items:center; border-radius:50%; background:linear-gradient(145deg,#303944,#151b28); color:#fff; font-size:12px; }.profile small { padding:3px 6px; border-radius:6px; background:#fff2d8; color:#c28a2d; font-size:10px; }.profile .el-icon { color:#657792; }

.app-main {
  min-height: calc(100vh - 66px);
  padding: 26px 28px;
  background: transparent;
  overflow-y: auto;
}

@media (max-width: 860px) {
  .app-sidebar {
    display: none;
  }

  .topbar {
    padding: 0 16px;
  }

  .global-search { display:none; }

  .topbar-actions {
    gap: 4px;
  }

  .sync-button,.new-button { display:none; }

  .profile-name,.profile small { display:none; }

  .app-main {
    padding: 16px;
  }
}
</style>
