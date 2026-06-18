<template>
  <div class="benchmark-management">
    <div class="page-header">
      <h1>抖音对标管理</h1>
    </div>

    <el-card shadow="never" class="add-card">
      <el-form label-width="100px">
        <el-form-item label="主页链接">
          <div class="add-row">
            <el-input
              v-model="homepageUrl"
              placeholder="粘贴抖音对标账号主页链接"
              clearable
            />
            <el-button type="primary" :loading="adding" @click="addAccount">
              添加并同步
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>对标账号</span>
          <el-button :loading="loading" @click="fetchAccounts">刷新</el-button>
        </div>
      </template>

      <el-table :data="accounts" v-loading="loading" style="width: 100%">
        <el-table-column label="账号" min-width="220">
          <template #default="scope">
            <div class="account-cell">
              <el-avatar :src="scope.row.avatar" :size="36">{{ avatarText(scope.row) }}</el-avatar>
              <div>
                <div class="name">{{ scope.row.nickname || '未识别账号' }}</div>
                <el-link :href="scope.row.homepage_url" target="_blank" type="primary">
                  打开主页
                </el-link>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="followers_count" label="粉丝" width="140" />
        <el-table-column prop="likes_count" label="获赞" width="140" />
        <el-table-column prop="video_count" label="作品" width="140" />
        <el-table-column prop="synced_video_count" label="已同步作品" width="120" />
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'success' ? 'success' : scope.row.status === 'failed' ? 'danger' : 'info'">
              {{ statusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_sync_at" label="最近同步" width="180" />
        <el-table-column prop="error_message" label="错误" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="loadVideos(scope.row)">
              {{ selectedAccount?.id === scope.row.id ? '收起' : '作品' }}
            </el-button>
            <el-button size="small" type="primary" :loading="syncingId === scope.row.id" @click="syncAccount(scope.row)">
              同步
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && accounts.length === 0" description="暂无对标账号" />
    </el-card>

    <el-card v-if="selectedAccount" shadow="never" class="videos-card">
      <template #header>
        <div class="card-header">
          <span>{{ selectedAccount.nickname || '对标账号' }} 的近期作品</span>
        </div>
      </template>

      <el-table :data="videos" v-loading="videosLoading" style="width: 100%">
        <el-table-column label="封面" width="100">
          <template #default="scope">
            <el-image
              v-if="scope.row.cover_url"
              :src="scope.row.cover_url"
              fit="cover"
              style="width: 72px; height: 96px; border-radius: 4px;"
            />
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题/文案" min-width="260" show-overflow-tooltip />
        <el-table-column prop="like_count" label="点赞" width="100" />
        <el-table-column label="链接" min-width="220">
          <template #default="scope">
            <el-link :href="scope.row.video_url" target="_blank" type="primary">
              打开作品
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="同步时间" width="180" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              plain
              :loading="analyzingId === scope.row.id"
              @click="openVideoAnalysis(scope.row)"
            >
              拆解
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!videosLoading && videos.length === 0" description="暂无作品数据" />
    </el-card>

    <el-drawer
      v-model="analysisDrawerVisible"
      title="作品内拆解"
      size="520px"
      class="analysis-drawer"
    >
      <div v-loading="analysisLoading" class="analysis-content">
        <template v-if="selectedVideo">
          <section class="analysis-section">
            <div class="section-title">作品基础信息</div>
            <div class="video-summary">
              <el-image
                v-if="selectedVideo.cover_url"
                :src="selectedVideo.cover_url"
                fit="cover"
                class="analysis-cover"
              />
              <div class="video-meta">
                <div class="video-title">{{ selectedVideo.title || '暂无标题/文案' }}</div>
                <el-link :href="selectedVideo.video_url" target="_blank" type="primary">
                  打开原作品
                </el-link>
              </div>
            </div>
          </section>

          <template v-if="videoAnalysis">
            <el-alert
              v-if="videoAnalysis.analysis_type === 'codex_cli'"
              title="当前为 Codex CLI 深度拆解结果，已结合标题、文案、链接、封面和同步数据进行对标分析。"
              type="success"
              show-icon
              :closable="false"
              class="analysis-tip"
            />
            <el-alert
              v-else-if="videoAnalysis.analysis_type === 'metadata_fallback'"
              title="Codex CLI 暂未返回可用结果，当前展示规则兜底拆解。可稍后点击“重新拆解”再试。"
              type="warning"
              show-icon
              :closable="false"
              class="analysis-tip"
            />
            <el-alert
              v-else-if="videoAnalysis.analysis_type === 'metadata'"
              title="当前为基于已同步标题/封面/链接的元数据拆解，深度版可继续接入评论、详情页和视频转写。"
              type="info"
              show-icon
              :closable="false"
              class="analysis-tip"
            />

            <section class="analysis-section">
              <div class="section-title">内容结构拆解</div>
              <el-descriptions :column="1" border>
                <el-descriptions-item label="开头钩子">
                  {{ videoAnalysis.hook || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="核心观点">
                  {{ videoAnalysis.core_viewpoint || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="总结">
                  {{ videoAnalysis.summary || '-' }}
                </el-descriptions-item>
              </el-descriptions>
            </section>

            <section class="analysis-section">
              <div class="section-title">爆点分析</div>
              <div class="tag-list">
                <el-tag
                  v-for="item in videoAnalysis.viral_points"
                  :key="item"
                  type="warning"
                  effect="plain"
                >
                  {{ item }}
                </el-tag>
              </div>
              <el-empty
                v-if="!videoAnalysis.viral_points?.length"
                description="暂无爆点分析"
                :image-size="80"
              />
            </section>

            <section class="analysis-section">
              <div class="section-title">人群痛点</div>
              <ul class="analysis-list">
                <li v-for="item in videoAnalysis.pain_points" :key="item">{{ item }}</li>
              </ul>
            </section>

            <section class="analysis-section">
              <div class="section-title">可复刻点</div>
              <ul class="analysis-list">
                <li v-for="item in videoAnalysis.reusable_points" :key="item">{{ item }}</li>
              </ul>
            </section>

            <section class="analysis-section">
              <div class="section-title">脚本复刻建议</div>
              <div class="script-list">
                <div
                  v-for="(item, index) in videoAnalysis.script_suggestions"
                  :key="item"
                  class="script-item"
                >
                  <span class="script-index">{{ index + 1 }}</span>
                  <span>{{ item }}</span>
                </div>
              </div>
            </section>

            <div class="drawer-actions">
              <el-button
                type="primary"
                :loading="analysisLoading"
                @click="regenerateVideoAnalysis"
              >
                重新拆解
              </el-button>
            </div>
          </template>

          <el-empty v-else-if="!analysisLoading" description="暂无拆解数据" />
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { benchmarkApi } from '@/api/benchmark'

const homepageUrl = ref('')
const loading = ref(false)
const adding = ref(false)
const syncingId = ref(null)
const accounts = ref([])
const selectedAccount = ref(null)
const videos = ref([])
const videosLoading = ref(false)
const analysisDrawerVisible = ref(false)
const analysisLoading = ref(false)
const analyzingId = ref(null)
const selectedVideo = ref(null)
const videoAnalysis = ref(null)

const avatarText = (account) => {
  return (account.nickname || '抖').slice(0, 1)
}

const statusText = (status) => {
  const map = {
    success: '已同步',
    failed: '失败',
    pending: '待同步'
  }
  return map[status] || status || '未知'
}

const fetchAccounts = async () => {
  loading.value = true
  try {
    const response = await benchmarkApi.getDouyinAccounts()
    accounts.value = response.data || []
  } catch (error) {
    console.error('获取对标账号失败:', error)
    ElMessage.error('获取对标账号失败')
  } finally {
    loading.value = false
  }
}

const addAccount = async () => {
  if (!homepageUrl.value.trim()) {
    ElMessage.warning('请先粘贴抖音主页链接')
    return
  }
  adding.value = true
  try {
    await benchmarkApi.addDouyinAccount(homepageUrl.value.trim())
    ElMessage.success('对标账号已同步')
    homepageUrl.value = ''
    await fetchAccounts()
  } catch (error) {
    console.error('添加对标账号失败:', error)
    ElMessage.error('添加对标账号失败')
  } finally {
    adding.value = false
  }
}

const syncAccount = async (account) => {
  syncingId.value = account.id
  try {
    const response = await benchmarkApi.syncDouyinAccount(account.id)
    const sync = response.data?.sync || {}
    ElMessage.success(`同步完成，新增 ${sync.inserted || 0} 条，更新 ${sync.updated || 0} 条`)
    await fetchAccounts()
    if (selectedAccount.value?.id === account.id) {
      await fetchVideosForAccount(account)
    }
  } catch (error) {
    console.error('同步失败:', error)
    ElMessage.error('同步失败')
    await fetchAccounts()
  } finally {
    syncingId.value = null
  }
}

const fetchVideosForAccount = async (account) => {
  videosLoading.value = true
  try {
    const response = await benchmarkApi.getDouyinVideos(account.id)
    videos.value = response.data || []
  } catch (error) {
    console.error('获取作品失败:', error)
    ElMessage.error('获取作品失败')
  } finally {
    videosLoading.value = false
  }
}

const loadVideos = async (account) => {
  if (selectedAccount.value?.id === account.id) {
    selectedAccount.value = null
    videos.value = []
    return
  }

  selectedAccount.value = account
  await fetchVideosForAccount(account)
}

const openVideoAnalysis = async (video) => {
  selectedVideo.value = video
  videoAnalysis.value = null
  analysisDrawerVisible.value = true
  analysisLoading.value = true
  analyzingId.value = video.id
  try {
    const response = await benchmarkApi.createDouyinVideoAnalysis(video.id)
    videoAnalysis.value = response.data || null
  } catch (error) {
    console.error('作品拆解失败:', error)
    ElMessage.error('作品拆解失败')
  } finally {
    analysisLoading.value = false
    analyzingId.value = null
  }
}

const regenerateVideoAnalysis = async () => {
  if (!selectedVideo.value) return
  analysisLoading.value = true
  analyzingId.value = selectedVideo.value.id
  try {
    const response = await benchmarkApi.createDouyinVideoAnalysis(selectedVideo.value.id, true)
    videoAnalysis.value = response.data || null
    ElMessage.success('拆解已更新')
  } catch (error) {
    console.error('重新拆解失败:', error)
    ElMessage.error('重新拆解失败')
  } finally {
    analysisLoading.value = false
    analyzingId.value = null
  }
}

onMounted(fetchAccounts)
</script>

<style lang="scss" scoped>
.benchmark-management {
  .page-header {
    margin-bottom: 20px;

    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
    }
  }

  .add-card,
  .videos-card {
    margin-bottom: 16px;
  }

  .add-row {
    display: flex;
    width: 100%;
    gap: 12px;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .account-cell {
    display: flex;
    align-items: center;
    gap: 12px;

    .name {
      font-weight: 600;
      margin-bottom: 4px;
    }
  }

  .analysis-content {
    min-height: 320px;
  }

  .analysis-section {
    margin-bottom: 20px;
  }

  .section-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #303133;
  }

  .video-summary {
    display: flex;
    gap: 12px;
  }

  .analysis-cover {
    width: 92px;
    height: 124px;
    border-radius: 6px;
    flex: 0 0 auto;
  }

  .video-meta {
    min-width: 0;
  }

  .video-title {
    font-weight: 600;
    line-height: 1.5;
    margin-bottom: 8px;
    word-break: break-word;
  }

  .analysis-tip {
    margin-bottom: 18px;
  }

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .analysis-list {
    margin: 0;
    padding-left: 20px;

    li {
      line-height: 1.7;
      margin-bottom: 6px;
    }
  }

  .script-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .script-item {
    display: flex;
    gap: 10px;
    line-height: 1.6;
    padding: 10px 12px;
    background: #f5f7fa;
    border-radius: 6px;
  }

  .script-index {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: #409eff;
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    font-size: 12px;
  }

  .drawer-actions {
    display: flex;
    justify-content: flex-end;
    padding-top: 8px;
  }
}
</style>
