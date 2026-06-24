<template>
  <div class="data-view">
    <div class="page-header">
      <h1>发布数据</h1>
      <div class="header-actions">
        <el-button type="primary" :loading="loading" @click="fetchRecords">
          刷新
        </el-button>
      </div>
    </div>

    <!-- 流量统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">总发布</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card views">
          <div class="stat-label">总播放</div>
          <div class="stat-value">{{ formatNumber(stats.totalViews) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card likes">
          <div class="stat-label">总点赞</div>
          <div class="stat-value">{{ formatNumber(stats.totalLikes) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card followers">
          <div class="stat-label">平均播放</div>
          <div class="stat-value">{{ formatNumber(stats.avgViews) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <el-select v-model="filterPlatform" placeholder="全部平台" clearable style="width: 140px">
          <el-option label="抖音" :value="3" />
          <el-option label="视频号" :value="2" />
          <el-option label="小红书" :value="1" />
          <el-option label="快手" :value="4" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 140px; margin-left: 10px">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-input v-model="searchTitle" placeholder="搜索标题..." clearable style="width: 200px; margin-left: 10px" />
      </div>

      <el-table :data="filteredRecords" style="width: 100%" v-loading="loading" stripe>
        <el-table-column label="平台" width="80">
          <template #default="scope">
            <el-tag>{{ platformName(scope.row.platform_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />

        <!-- 账号 + 粉丝数 -->
        <el-table-column label="账号（粉丝）" min-width="180">
          <template #default="scope">
            <div v-for="(name, idx) in getAccountNames(scope.row)" :key="idx" class="account-cell">
              <span class="account-name">{{ name }}</span>
              <span class="account-fans" v-if="getAccountFollower(name) !== null">
                {{ formatNumber(getAccountFollower(name)) }}粉
              </span>
            </div>
          </template>
        </el-table-column>

        <!-- 流量列组 -->
        <el-table-column label="播放" width="90" align="right" sortable prop="views">
          <template #default="scope">
            <el-input-number
              v-model="scope.row.views"
              :min="0"
              size="small"
              controls-position="right"
              style="width: 85px"
              @change="onStatsChange(scope.row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="点赞" width="80" align="right" sortable prop="likes">
          <template #default="scope">
            <el-input-number
              v-model="scope.row.likes"
              :min="0"
              size="small"
              controls-position="right"
              style="width: 75px"
              @change="onStatsChange(scope.row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="评论" width="70" align="right" sortable prop="comments">
          <template #default="scope">
            <el-input-number
              v-model="scope.row.comments"
              :min="0"
              size="small"
              controls-position="right"
              style="width: 65px"
              @change="onStatsChange(scope.row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="分享" width="70" align="right" sortable prop="shares">
          <template #default="scope">
            <el-input-number
              v-model="scope.row.shares"
              :min="0"
              size="small"
              controls-position="right"
              style="width: 65px"
              @change="onStatsChange(scope.row)"
            />
          </template>
        </el-table-column>

        <el-table-column label="状态" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ scope.row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column prop="last_refresh_at" label="最近刷新" width="160">
          <template #default="scope">
            <span class="refresh-time">{{ scope.row.last_refresh_at || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && filteredRecords.length === 0" description="暂无发布数据" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { publishApi } from '@/api/publish'

const loading = ref(false)
const records = ref([])
const accountFollowers = ref({})  // { accountName: followerCount }

// 筛选
const filterPlatform = ref(null)
const filterStatus = ref(null)
const searchTitle = ref('')

const filteredRecords = computed(() => {
  let list = records.value
  if (filterPlatform.value !== null && filterPlatform.value !== '') {
    list = list.filter(r => Number(r.platform_type) === Number(filterPlatform.value))
  }
  if (filterStatus.value) {
    list = list.filter(r => r.status === filterStatus.value)
  }
  if (searchTitle.value) {
    const q = searchTitle.value.toLowerCase()
    list = list.filter(r => (r.title || '').toLowerCase().includes(q))
  }
  return list
})

// 统计卡片
const stats = computed(() => {
  const success = records.value.filter(r => r.status === 'success')
  const total = success.length
  const totalViews = success.reduce((s, r) => s + (Number(r.views) || 0), 0)
  const totalLikes = success.reduce((s, r) => s + (Number(r.likes) || 0), 0)
  return {
    total,
    totalViews,
    totalLikes,
    avgViews: total > 0 ? Math.round(totalViews / total) : 0
  }
})

const platformName = (type) => {
  const map = { 1: '小红书', 2: '视频号', 3: '抖音', 4: '快手' }
  return map[Number(type)] || 
}

// 账号列表缓存：account_list 存的是 filePath（cookie JSON 文件名），需要转成 userName
const accountNameCache = ref({})

const getAccountNames = (row) => {
  const files = row.account_list || []
  return files.map(f => accountNameCache.value[f] || f.replace('.json', ''))
}

const getAccountFollower = (accountName) => {
  return accountFollowers.value[accountName] ?? null
}

const formatNumber = (n) => {
  if (!n) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

const fetchRecords = async () => {
  loading.value = true
  try {
    // 并发获取发布记录 + 账号粉丝数 + 账号名称映射
    const [recordsRes, followersRes] = await Promise.all([
      publishApi.getPublishRecords(),
      publishApi.getAccountFollowers()
    ])

    // 解析发布记录
    records.value = (recordsRes.data || []).map(r => ({
      ...r,
      views: Number(r.views || 0),
      likes: Number(r.likes || 0),
      comments: Number(r.comments || 0),
      shares: Number(r.shares || 0)
    }))

    // 解析账号粉丝数 + 名称映射
    const followers = {}
    const nameMap = {}
    for (const acc of (followersRes.data || [])) {
      nameMap[acc.filePath] = acc.userName
      followers[acc.userName] = Number(acc.follower_count || 0)
    }
    accountNameCache.value = nameMap
    accountFollowers.value = followers

  } catch (error) {
    console.error('获取数据失败:', error)
    ElMessage.error('获取发布数据失败')
  } finally {
    loading.value = false
  }
}

// 防抖自动保存
const saveTimers = {}
const onStatsChange = (row) => {
  if (saveTimers[row.id]) clearTimeout(saveTimers[row.id])
  saveTimers[row.id] = setTimeout(async () => {
    try {
      await publishApi.updateStats({
        id: row.id,
        views: row.views,
        likes: row.likes,
        comments: row.comments,
        shares: row.shares
      })
    } catch (e) {
      // silent
    }
  }, 800)
}

onMounted(fetchRecords)
</script>

<style lang="scss" scoped>
.data-view {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
    }

    .header-actions {
      display: flex;
      gap: 10px;
    }
  }

  .stats-row {
    margin-bottom: 16px;

    .stat-card {
      text-align: center;

      .stat-label {
        font-size: 13px;
        color: #909399;
        margin-bottom: 4px;
      }

      .stat-value {
        font-size: 22px;
        font-weight: 700;
        color: #303133;
      }

      &.views .stat-value { color: #409eff; }
      &.likes .stat-value { color: #e6a23c; }
      &.followers .stat-value { color: #67c23a; }
    }
  }

  .filter-bar {
    margin-bottom: 16px;
    display: flex;
    align-items: center;
  }

  .account-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    line-height: 1.6;

    .account-name {
      font-size: 13px;
      color: #303133;
    }

    .account-fans {
      font-size: 11px;
      color: #909399;
      background: #f5f7fa;
      padding: 0 6px;
      border-radius: 3px;
    }
  }

  .refresh-time {
    color: #909399;
    font-size: 12px;
  }
}
</style>