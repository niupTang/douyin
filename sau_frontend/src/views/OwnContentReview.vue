<template>
  <div class="own-content-review">
    <div class="page-header">
      <div>
        <h1>我的作品复盘</h1>
        <p>选择账号中心里的抖音账号，同步并分析该账号的创作者数据。</p>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedAccountId" filterable placeholder="选择数据账号" class="data-account-select">
          <el-option
            v-for="account in accounts"
            :key="account.id"
            :label="`${account.userName}${account.status === 1 ? '' : '（登录失效）'}`"
            :value="account.id"
          />
        </el-select>
        <el-button :disabled="!selectedAccountId" :loading="loadingWorks" @click="fetchWorks">刷新</el-button>
        <el-button type="primary" :disabled="!canSync" :loading="exporting" @click="runExport">立即同步</el-button>
      </div>
    </div>

    <div class="download-location">
      <span>下载目录：{{ downloadDirectory || '未选择' }}</span>
      <el-button size="small" @click="chooseDownloadDirectory">选择目录</el-button>
    </div>

    <el-alert
      v-if="selectedAccountId && !selectedAccountActive"
      title="该账号登录态已失效，请到账号管理重新登录后再同步"
      type="warning"
      show-icon
      :closable="false"
      class="export-status"
    >
      <template #default>
        <el-button type="warning" link @click="$router.push('/account-management')">去账号管理重新登录</el-button>
      </template>
    </el-alert>

    <el-alert
      v-if="exportStatus"
      :title="exportStatusText"
      :type="exportStatus.status === 'failed' ? 'error' : exportStatus.status === 'success' ? 'success' : 'info'"
      show-icon
      :closable="false"
      class="export-status"
    />

    <el-card shadow="never" class="import-card">
      <template #header>
        <div class="card-header">
          <span>手动导入</span>
          <el-tag type="info" effect="plain">支持 XLSX / CSV</el-tag>
        </div>
      </template>

      <div class="import-row">
        <el-upload
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.csv"
          :on-change="handleFileChange"
        >
          <el-button :disabled="!canSync">选择文件</el-button>
        </el-upload>
        <div class="file-name">{{ selectedFile?.name || '未选择文件' }}</div>
        <el-button type="primary" :disabled="!canSync || !selectedFile" :loading="previewLoading" @click="previewImport">
          预览
        </el-button>
        <el-button type="success" :disabled="!canImport" :loading="importing" @click="confirmImport">
          确认导入
        </el-button>
      </div>

      <el-alert
        v-if="importResult"
        :title="`导入完成：新增 ${importResult.inserted} 条，更新 ${importResult.updated} 条`"
        type="success"
        show-icon
        :closable="false"
        class="result-alert"
      />

      <div v-if="previewData" class="preview-block">
        <div class="preview-summary">
          <el-statistic title="原始行数" :value="previewData.raw_count" />
          <el-statistic title="有效作品" :value="previewData.valid_count" />
          <el-statistic title="识别字段" :value="Object.keys(previewData.field_map || {}).length" />
        </div>

        <el-table :data="previewData.preview_rows" size="small" style="width: 100%">
          <el-table-column prop="title" label="作品名称" min-width="280" show-overflow-tooltip />
          <el-table-column prop="published_at" label="发布时间" width="180" />
          <el-table-column prop="content_format" label="体裁" width="120" />
          <el-table-column prop="play_count" label="播放" width="100" />
          <el-table-column label="完播率" width="100">
            <template #default="scope">{{ formatPercent(scope.row.completion_rate) }}</template>
          </el-table-column>
          <el-table-column label="5s完播" width="100">
            <template #default="scope">{{ formatPercent(scope.row.five_sec_completion_rate) }}</template>
          </el-table-column>
          <el-table-column prop="like_count" label="点赞" width="90" />
          <el-table-column prop="collect_count" label="收藏" width="90" />
          <el-table-column prop="follower_delta" label="涨粉" width="90" />
        </el-table>
      </div>
    </el-card>

    <el-card shadow="never" class="works-card">
      <template #header>
        <div class="card-header">
          <span>我的作品库</span>
          <span class="muted">共 {{ works.length }} 条</span>
        </div>
      </template>

      <el-table v-if="selectedAccountId" :data="works" v-loading="loadingWorks" style="width: 100%">
        <el-table-column prop="title" label="作品名称" min-width="300" show-overflow-tooltip />
        <el-table-column prop="published_at" label="发布时间" width="180" />
        <el-table-column prop="content_format" label="体裁" width="120" />
        <el-table-column prop="visibility_status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.visibility_status === '公开' ? 'success' : 'info'" effect="plain">
              {{ scope.row.visibility_status || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="play_count" label="播放" width="100" sortable />
        <el-table-column prop="completion_rate" label="完播率" width="105" sortable>
          <template #default="scope">{{ formatPercent(scope.row.completion_rate) }}</template>
        </el-table-column>
        <el-table-column prop="five_sec_completion_rate" label="5s完播" width="105" sortable>
          <template #default="scope">{{ formatPercent(scope.row.five_sec_completion_rate) }}</template>
        </el-table-column>
        <el-table-column prop="two_sec_bounce_rate" label="2s跳出" width="105" sortable>
          <template #default="scope">{{ formatPercent(scope.row.two_sec_bounce_rate) }}</template>
        </el-table-column>
        <el-table-column prop="avg_play_duration" label="均播时长" width="105" sortable>
          <template #default="scope">{{ formatSeconds(scope.row.avg_play_duration) }}</template>
        </el-table-column>
        <el-table-column prop="like_count" label="点赞" width="90" sortable />
        <el-table-column prop="comment_count" label="评论" width="90" sortable />
        <el-table-column prop="collect_count" label="收藏" width="90" sortable />
        <el-table-column prop="profile_visit_count" label="主页访问" width="105" sortable />
        <el-table-column prop="follower_delta" label="涨粉" width="90" sortable />
        <el-table-column label="复盘" width="110" fixed="right">
          <template #default="scope">
            <el-button
              link
              type="primary"
              :loading="analyzingId === scope.row.id"
              @click="analyzeVideo(scope.row)"
            >
              {{ scope.row.analysis_status === 'success' ? '查看' : '分析' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!selectedAccountId" description="请先选择账号中心里的抖音账号" />
      <el-empty v-else-if="!loadingWorks && works.length === 0" description="该账号暂无作品数据" />
    </el-card>

    <el-drawer v-model="analysisVisible" title="作品流量复盘" size="560px">
      <div v-if="selectedVideo" v-loading="analysisLoading" class="analysis-drawer">
        <div class="analysis-title">{{ selectedVideo.title || '未命名作品' }}</div>
        <el-link v-if="selectedVideo.video_url" :href="selectedVideo.video_url" target="_blank" type="primary">
          打开原作品
        </el-link>
        <template v-if="selectedVideo.analysis">
          <el-alert :title="selectedVideo.analysis.summary || '分析完成'" type="success" show-icon :closable="false" class="analysis-summary" />
          <el-descriptions :column="1" border>
            <el-descriptions-item label="流量判断">{{ selectedVideo.analysis.traffic_diagnosis || '-' }}</el-descriptions-item>
            <el-descriptions-item label="没继续放量的原因">{{ selectedVideo.analysis.low_traffic_reason || '-' }}</el-descriptions-item>
            <el-descriptions-item label="前2秒诊断">{{ selectedVideo.analysis.two_second_diagnosis || '-' }}</el-descriptions-item>
            <el-descriptions-item label="可信度">{{ selectedVideo.analysis.confidence || '-' }}</el-descriptions-item>
          </el-descriptions>
          <div class="analysis-block">
            <div class="analysis-heading">数据证据</div>
            <ul><li v-for="item in selectedVideo.analysis.evidence" :key="item">{{ item }}</li></ul>
          </div>
          <div class="analysis-block">
            <div class="analysis-heading">下一步动作</div>
            <ul><li v-for="item in selectedVideo.analysis.actions" :key="item">{{ item }}</li></ul>
          </div>
          <div class="analysis-block">
            <div class="analysis-heading">前2秒改写</div>
            <ol><li v-for="item in selectedVideo.analysis.opening_rewrites" :key="item">{{ item }}</li></ol>
          </div>
          <el-button type="primary" :loading="analysisLoading" @click="analyzeVideo(selectedVideo, true)">重新分析</el-button>
        </template>
        <el-empty v-else-if="!analysisLoading" description="暂无分析结果" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ownContentApi } from '@/api/ownContent'
import { useDownloadDirectory } from '@/composables/useDownloadDirectory'

const accounts = ref([])
const selectedAccountId = ref('')
const selectedFile = ref(null)
const previewData = ref(null)
const importResult = ref(null)
const previewLoading = ref(false)
const importing = ref(false)
const loadingWorks = ref(false)
const works = ref([])
const exportStatus = ref(null)
const exporting = ref(false)
const { downloadDirectory, loadDownloadDirectory, chooseDownloadDirectory, ensureDownloadDirectory } = useDownloadDirectory()
const analyzingId = ref(null)
const analysisVisible = ref(false)
const analysisLoading = ref(false)
const selectedVideo = ref(null)
let exportPollTimer = null

const selectedAccount = computed(() => accounts.value.find(item => item.id === selectedAccountId.value))
const selectedAccountActive = computed(() => Number(selectedAccount.value?.status) === 1)
const canSync = computed(() => Boolean(selectedAccountId.value && selectedAccountActive.value))

const exportStatusText = computed(() => {
  if (!exportStatus.value) return ''
  if (exportStatus.value.status === 'running') return '正在导出创作者中心数据，请稍候...'
  if (exportStatus.value.status === 'success') return `最近一次导出成功，已导入 ${exportStatus.value.imported_count || 0} 条作品`
  return `最近一次导出失败：${exportStatus.value.error_message || '未知错误'}`
})

const canImport = computed(() => {
  return canSync.value && selectedFile.value && previewData.value && previewData.value.valid_count > 0
})

const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile.raw
  previewData.value = null
  importResult.value = null
}

const previewImport = async () => {
  if (!selectedFile.value || !canSync.value) return
  previewLoading.value = true
  try {
    const response = await ownContentApi.previewDouyinImport(selectedFile.value, selectedAccountId.value)
    previewData.value = response.data
    importResult.value = null
    ElMessage.success('预览完成')
  } catch (error) {
    console.error('预览失败:', error)
  } finally {
    previewLoading.value = false
  }
}

const confirmImport = async () => {
  if (!canImport.value) return
  importing.value = true
  try {
    const response = await ownContentApi.importDouyinWorks(selectedFile.value, selectedAccountId.value)
    importResult.value = response.data
    ElMessage.success('导入完成')
    await fetchWorks()
  } catch (error) {
    console.error('导入失败:', error)
  } finally {
    importing.value = false
  }
}

const fetchWorks = async () => {
  if (!selectedAccountId.value) {
    works.value = []
    return
  }
  loadingWorks.value = true
  try {
    const response = await ownContentApi.getDouyinWorks(selectedAccountId.value, 200)
    works.value = response.data || []
  } catch (error) {
    console.error('获取我的作品失败:', error)
  } finally {
    loadingWorks.value = false
  }
}

const fetchExportStatus = async () => {
  if (!selectedAccountId.value) {
    exportStatus.value = null
    return
  }
  try {
    const response = await ownContentApi.getExportStatus(selectedAccountId.value)
    exportStatus.value = response.data
    if (response.data?.status === 'failed' && response.data?.error_message?.includes('登录态已失效')) {
      const account = accounts.value.find(item => item.id === selectedAccountId.value)
      if (account) account.status = 0
    }
  } catch (error) {
    console.error('获取导出状态失败:', error)
  }
}

const runExport = async () => {
  if (!canSync.value) return
  exporting.value = true
  try {
    if (!await ensureDownloadDirectory()) return
    await ownContentApi.runExport(selectedAccountId.value)
    exportStatus.value = { status: 'running' }
    clearExportPoll()
    exportPollTimer = window.setInterval(async () => {
      await fetchExportStatus()
      if (exportStatus.value?.status !== 'running') {
        clearExportPoll()
        if (exportStatus.value?.status === 'success') await fetchWorks()
      }
    }, 3000)
    ElMessage.success('已开始同步')
  } catch (error) {
    console.error('启动同步失败:', error)
    ElMessage.error(error.message || '启动同步失败')
  } finally {
    exporting.value = false
  }
}

const fetchAccounts = async () => {
  try {
    const response = await ownContentApi.listDouyinAccounts()
    accounts.value = response.data || []
    const stored = Number(localStorage.getItem('own_review_user_info_id'))
    if (stored && accounts.value.some(item => item.id === stored)) selectedAccountId.value = stored
  } catch (error) {
    console.error('获取数据账号失败:', error)
    ElMessage.error(error.message || '获取数据账号失败')
  }
}

const clearExportPoll = () => {
  if (exportPollTimer) window.clearInterval(exportPollTimer)
  exportPollTimer = null
}

const analyzeVideo = async (video, force = false) => {
  const accountId = selectedAccountId.value
  selectedVideo.value = video
  analysisVisible.value = true
  if (video.analysis && !force) return
  analyzingId.value = video.id
  analysisLoading.value = true
  try {
    await ownContentApi.analyzeVideo(video.id, force)
    for (let attempt = 0; attempt < 60; attempt += 1) {
      await new Promise(resolve => window.setTimeout(resolve, 2000))
      if (selectedAccountId.value !== accountId) break
      const response = await ownContentApi.getDouyinWorks(accountId, 200)
      const latest = (response.data || []).find(item => item.id === video.id)
      if (latest) {
        Object.assign(video, latest)
        selectedVideo.value = video
      }
      if (latest?.analysis_status === 'success') {
        ElMessage.success('作品分析完成')
        break
      }
      if (latest?.analysis_status === 'failed') {
        throw new Error(latest.analysis_error || '分析失败')
      }
    }
  } catch (error) {
    console.error('作品分析失败:', error)
    ElMessage.error(error.message || '作品分析失败')
  } finally {
    analyzingId.value = null
    analysisLoading.value = false
  }
}

const formatPercent = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  return `${(Number(value) * 100).toFixed(1)}%`
}

const formatSeconds = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  return `${Number(value).toFixed(1)}s`
}

watch(selectedAccountId, async (value) => {
  clearExportPoll()
  selectedFile.value = null
  previewData.value = null
  importResult.value = null
  exportStatus.value = null
  works.value = []
  selectedVideo.value = null
  analysisVisible.value = false
  if (!value) {
    localStorage.removeItem('own_review_user_info_id')
    return
  }
  localStorage.setItem('own_review_user_info_id', String(value))
  await Promise.all([fetchWorks(), fetchExportStatus()])
})

onMounted(() => {
  fetchAccounts()
  loadDownloadDirectory().catch(() => {})
})
onBeforeUnmount(clearExportPoll)
</script>

<style lang="scss" scoped>
.own-content-review {
  .download-location { display: flex; align-items: center; gap: 10px; margin-bottom: 18px; color: #6b7280; font-size: 12px; }
  .download-location span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 18px;

    h1 {
      margin: 0 0 6px;
      font-size: 24px;
      font-weight: 700;
      color: #1f2937;
    }

    p {
      margin: 0;
      color: #6b7280;
      font-size: 14px;
    }
  }

  .header-actions {
    display: flex;
    gap: 10px;
  }

  .data-account-select {
    width: 240px;
  }

  .export-status {
    margin-bottom: 18px;
  }

  .analysis-drawer {
    min-height: 320px;
  }

  .analysis-title {
    font-size: 17px;
    font-weight: 600;
    line-height: 1.5;
    margin-bottom: 6px;
  }

  .analysis-summary {
    margin: 18px 0;
  }

  .analysis-block {
    margin: 20px 0;
    line-height: 1.7;

    ul,
    ol {
      margin: 8px 0 0;
      padding-left: 20px;
    }
  }

  .analysis-heading {
    font-weight: 600;
    color: #303133;
  }

  .import-card,
  .works-card {
    margin-bottom: 18px;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .import-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .file-name,
  .muted {
    color: #6b7280;
    font-size: 13px;
  }

  .result-alert,
  .preview-block {
    margin-top: 16px;
  }

  .preview-summary {
    display: grid;
    grid-template-columns: repeat(3, minmax(120px, 1fr));
    gap: 12px;
    margin-bottom: 14px;
  }

  @media (max-width: 760px) {
    .page-header,
    .header-actions {
      align-items: stretch;
      flex-direction: column;
    }

    .data-account-select {
      width: 100%;
    }
  }
}
</style>
