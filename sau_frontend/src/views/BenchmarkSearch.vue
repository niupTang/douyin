<template>
  <div class="benchmark-search">
    <div class="page-header">
      <h1>抖音搜索</h1>
      <el-button @click="router.push('/benchmark-management')">查看对标库</el-button>
    </div>
    <el-card shadow="never" class="auto-card">
      <template #header>
        <div class="card-header">
          <span>自动找对标</span>
          <el-button type="primary" :loading="autoDiscovering" @click="autoDiscoverAccounts">
            搜索候选账号
          </el-button>
        </div>
      </template>
      <el-form label-width="100px">
        <el-form-item label="对标关键词">
          <el-input
            v-model="autoKeywords"
            type="textarea"
            :rows="3"
            placeholder="例如：AI 自媒体、知识付费、个人IP。多个关键词用逗号或换行分隔"
          />
        </el-form-item>
        <div class="auto-options">
          <el-form-item label="找账号数">
            <el-input-number v-model="autoLimit" :min="1" :max="20" />
          </el-form-item>
          <el-form-item label="每号作品数">
            <el-input-number v-model="autoMaxVideos" :min="1" :max="30" />
          </el-form-item>
        </div>
      </el-form>
      <el-alert
        v-if="autoResult"
        :title="autoResult.status === 'failed' || autoResult.status === 'interrupted' ? autoResult.error : `找到 ${autoResult.summary?.found || 0} 个候选，已读取 ${autoResult.summary?.ready || 0} 个，失败 ${autoResult.summary?.failed || 0} 个，已入库 ${autoResult.summary?.imported || 0} 个`"
        :type="['failed', 'interrupted'].includes(autoResult.status) ? 'error' : 'info'"
        :closable="false"
        show-icon
      />
      <p class="empty-content">先搜索账号并读取作品，展开候选查看内容；觉得合适再加入对标库。搜索本身不会添加账号。</p>
      <el-table v-if="autoResult?.candidates?.length" :data="autoResult.candidates" row-key="id" class="auto-results">
        <el-table-column type="expand">
          <template #default="scope">
            <div style="padding: 16px 24px">
              <p>{{ scope.row.bio || '暂无简介' }}</p>
              <el-table v-if="scope.row.videos?.length" :data="scope.row.videos" size="small">
                <el-table-column label="作品" min-width="380">
                  <template #default="item">
                    <el-link type="primary" @click.prevent="openDouyinPreview(item.row.video_url)">{{ item.row.title || '打开作品' }}</el-link>
                  </template>
                </el-table-column>
                <el-table-column label="页面赞数（待核对）" width="170">
                  <template #default="item">{{ item.row.like_count || '未获取' }}</template>
                </el-table-column>
              </el-table>
              <el-empty v-else :description="scope.row.error || '正在读取作品，请稍候'" :image-size="60" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="候选账号" min-width="210">
          <template #default="scope">
            <div class="auto-account-name">{{ scope.row.nickname || '待识别账号' }}</div>
            <el-link type="primary" @click.prevent="openDouyinPreview(scope.row.homepage_url)">查看主页</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="source_keyword" label="来源关键词" min-width="140" />
        <el-table-column prop="followers_count" label="粉丝" width="130" />
        <el-table-column label="已读取作品" width="110">
          <template #default="scope">{{ scope.row.videos?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="180">
          <template #default="scope">
            <span>{{ ({ pending: '正在读取作品', ready: '待你判断', failed: '读取失败', imported: '已入库' })[scope.row.status] }}</span>
            <p v-if="scope.row.error" class="empty-content">{{ scope.row.error }}</p>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="scope">
            <el-button type="primary" size="small" :loading="importingCandidates.has(scope.row.id)"
              :disabled="scope.row.status !== 'ready' || scope.row.already_in_library"
              @click="importCandidate(scope.row)">
              {{ scope.row.status === 'imported' || scope.row.already_in_library ? '已在对标库' : '加入对标库' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { benchmarkApi } from '@/api/benchmark'
import { useDouyinPreview } from '@/composables/useDouyinPreview'

const router = useRouter()
const route = useRoute()
const { openDouyinPreview } = useDouyinPreview()
const autoKeywords = ref('')
const autoLimit = ref(5)
const autoMaxVideos = ref(10)
const autoDiscovering = ref(false)
const autoResult = ref(null)

const importingCandidates = ref(new Set())
const discoveryStorageKey = 'sunbird-benchmark-discovery-task'
let discoveryPollTimer = null
let discoveryPolling = false
let disposed = false

const stopDiscoveryPolling = () => {
  if (discoveryPollTimer) clearInterval(discoveryPollTimer)
  discoveryPollTimer = null
}

const refreshDiscovery = async (taskId) => {
  if (disposed || discoveryPolling) return
  discoveryPolling = true
  try {
    const response = await benchmarkApi.getCandidateDiscovery(taskId)
    if (disposed) return
    autoResult.value = response.data
    autoDiscovering.value = ['queued', 'running'].includes(autoResult.value.status)
    if (!autoDiscovering.value) stopDiscoveryPolling()
  } catch (error) {
    stopDiscoveryPolling()
    autoDiscovering.value = false
    if (error.response?.status === 404) localStorage.removeItem(discoveryStorageKey)
    ElMessage.error('读取候选进度失败，可刷新页面后继续查看')
  } finally {
    discoveryPolling = false
  }
}

const watchDiscovery = (taskId) => {
  stopDiscoveryPolling()
  discoveryPollTimer = setInterval(() => refreshDiscovery(taskId), 1800)
}

const autoDiscoverAccounts = async () => {
  if (!autoKeywords.value.trim()) {
    ElMessage.warning('请先填写对标关键词')
    return
  }
  stopDiscoveryPolling()
  autoDiscovering.value = true
  try {
    const response = await benchmarkApi.discoverCandidates({
      keywords: autoKeywords.value, limit: autoLimit.value, maxVideos: autoMaxVideos.value
    })
    autoResult.value = response.data
    localStorage.setItem(discoveryStorageKey, response.data.id)
    if (['queued', 'running'].includes(response.data.status)) watchDiscovery(response.data.id)
    else autoDiscovering.value = false
    ElMessage.success('已开始搜索候选，确认前不会入库')
  } catch (error) {
    autoDiscovering.value = false
    ElMessage.error(error.response?.data?.msg || '搜索候选失败')
  }
}

const importCandidate = async (candidate) => {
  if (importingCandidates.value.has(candidate.id)) return
  importingCandidates.value.add(candidate.id)
  try {
    await benchmarkApi.importCandidate(autoResult.value.id, candidate.id)
    candidate.status = 'imported'
    candidate.already_in_library = true
    await refreshDiscovery(autoResult.value.id)
    ElMessage.success('已加入对标库')
  } catch (error) {
    ElMessage.error(error.response?.data?.msg || '加入对标库失败')
  } finally {
    importingCandidates.value.delete(candidate.id)
  }
}

const resumeDiscovery = async (requestedTaskId) => {
  stopDiscoveryPolling()
  const taskId = typeof requestedTaskId === 'string' && requestedTaskId
    ? requestedTaskId : localStorage.getItem(discoveryStorageKey)
  if (taskId) {
    localStorage.setItem(discoveryStorageKey, taskId)
    await refreshDiscovery(taskId)
    if (autoDiscovering.value) watchDiscovery(taskId)
  }
}

onMounted(() => {
  resumeDiscovery(route.query.discovery_task_id)
})
watch(() => route.query.discovery_task_id, (taskId) => resumeDiscovery(taskId))
onBeforeUnmount(() => {
  disposed = true
  stopDiscoveryPolling()
})
</script>

<style scoped>
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.page-header { margin-bottom: 20px; }
h1 { margin: 0; font-size: 24px; font-weight: 600; }
.auto-options { display: flex; flex-wrap: wrap; gap: 16px; }
.auto-results { margin-top: 12px; }
.auto-account-name { margin-bottom: 4px; font-weight: 600; }
.empty-content { color: #909399; font-size: 13px; }
</style>
