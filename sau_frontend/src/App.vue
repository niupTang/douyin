<template>
  <el-container class="app-shell">
    <el-aside :width="isCollapse ? '72px' : '248px'" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div v-show="!isCollapse" class="brand-copy">
          <strong>Sunbird OS</strong>
          <span>内容增长判断台</span>
        </div>
      </div>

      <el-menu
        :router="true"
        :default-active="activeMenu"
        :collapse="isCollapse"
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>增长总览</template>
        </el-menu-item>
        <el-menu-item index="/benchmark-management">
          <el-icon><Aim /></el-icon>
          <template #title>对标库</template>
        </el-menu-item>
        <el-menu-item index="/idea-radar">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>爆款拆解</template>
        </el-menu-item>
        <el-menu-item index="/own-content-review">
          <el-icon><TrendCharts /></el-icon>
          <template #title>作品复盘</template>
        </el-menu-item>
        <el-menu-item index="/material-management">
          <el-icon><Picture /></el-icon>
          <template #title>素材资产</template>
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
      </el-menu>

      <div v-show="!isCollapse" class="sidebar-note">
        <span>本周重点</span>
        <strong>把每条内容变成下一条的证据</strong>
      </div>
    </el-aside>

    <el-container class="workspace">
      <el-header class="topbar">
        <button class="icon-button" aria-label="切换侧边栏" @click="toggleSidebar">
          <el-icon><Fold /></el-icon>
        </button>
        <div class="topbar-title">
          <span>{{ routeMeta.kicker }}</span>
          <strong>{{ routeMeta.title }}</strong>
        </div>
        <div class="topbar-actions">
          <el-button text :icon="Refresh">同步数据</el-button>
          <el-button type="primary" :icon="Plus">新建复盘</el-button>
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
import { useRoute } from 'vue-router'
import {
  Aim,
  DataAnalysis,
  Fold,
  HomeFilled,
  Picture,
  PieChart,
  Plus,
  Refresh,
  TrendCharts,
  Upload,
  User
} from '@element-plus/icons-vue'

const route = useRoute()
const isCollapse = ref(false)

const pageMeta = {
  '/': { kicker: 'Dashboard', title: '增长总览' },
  '/benchmark-management': { kicker: 'Benchmark', title: '对标内容库' },
  '/idea-radar': { kicker: 'Insight', title: '爆款拆解' },
  '/own-content-review': { kicker: 'Review', title: '作品复盘' },
  '/material-management': { kicker: 'Assets', title: '素材资产' },
  '/publish-center': { kicker: 'Publish', title: '发布中心' },
  '/account-management': { kicker: 'Accounts', title: '账号管理' },
  '/data': { kicker: 'Data', title: '数据明细' }
}

const activeMenu = computed(() => route.path)
const routeMeta = computed(() => pageMeta[route.path] || pageMeta['/'])

const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}
</script>

<style lang="scss" scoped>
.app-shell {
  min-height: 100vh;
  background: #f6f7f9;
}

.app-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden;
  border-right: 1px solid #e6e8ec;
  background: #ffffff;
  transition: width 0.24s ease;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 72px;
  padding: 0 18px;
  border-bottom: 1px solid #edf0f3;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  background: #111827;
  color: #ffffff;
  font-weight: 800;
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
  padding: 12px 10px;

  :deep(.el-menu-item) {
    height: 42px;
    margin-bottom: 4px;
    border-radius: 8px;
    color: #4b5563;
  }

  :deep(.el-menu-item.is-active) {
    background: #111827;
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
  height: 72px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid #e6e8ec;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
}

.icon-button {
  width: 36px;
  height: 36px;
  border: 1px solid #dce1e7;
  border-radius: 8px;
  background: #ffffff;
  color: #374151;
  cursor: pointer;
}

.topbar-title {
  min-width: 0;

  span,
  strong {
    display: block;
  }

  span {
    color: #8b95a5;
    font-size: 12px;
  }

  strong {
    margin-top: 2px;
    color: #111827;
    font-size: 18px;
  }
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.app-main {
  min-height: calc(100vh - 72px);
  padding: 24px;
  overflow-y: auto;
}

@media (max-width: 860px) {
  .app-sidebar {
    display: none;
  }

  .topbar {
    padding: 0 16px;
  }

  .topbar-actions {
    display: none;
  }

  .app-main {
    padding: 16px;
  }
}
</style>
