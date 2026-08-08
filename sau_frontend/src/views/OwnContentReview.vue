<template>
  <div class="own-content-review">
    <div class="page-header">
      <div>
        <h1>我的作品复盘</h1>
        <p>导入抖音创作者中心作品数据，沉淀自己的内容表现和复盘样本。</p>
      </div>
      <el-button :loading="loadingWorks" @click="fetchWorks">刷新</el-button>
    </div>

    <el-card shadow="never" class="import-card">
      <template #header>
        <div class="card-header">
          <span>手动导入</span>
          <el-tag type="info" effect="plain">支持 XLSX / CSV</el-tag>
        </div>
      </template>

      <div class="import-row">
        <el-input v-model="accountName" class="account-input" placeholder="账号名称" />
        <el-upload
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.csv"
          :on-change="handleFileChange"
        >
          <el-button>选择文件</el-button>
        </el-upload>
        <div class="file-name">{{ selectedFile?.name || '未选择文件' }}</div>
        <el-button type="primary" :disabled="!selectedFile" :loading="previewLoading" @click="previewImport">
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

      <el-table :data="works" v-loading="loadingWorks" style="width: 100%">
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
      </el-table>

      <el-empty v-if="!loadingWorks && works.length === 0" description="暂无自己的作品数据" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ownContentApi } from '@/api/ownContent'

const accountName = ref('太阳鸟')
const selectedFile = ref(null)
const previewData = ref(null)
const importResult = ref(null)
const previewLoading = ref(false)
const importing = ref(false)
const loadingWorks = ref(false)
const works = ref([])

const canImport = computed(() => {
  return selectedFile.value && previewData.value && previewData.value.valid_count > 0
})

const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile.raw
  previewData.value = null
  importResult.value = null
}

const previewImport = async () => {
  if (!selectedFile.value) return
  previewLoading.value = true
  try {
    const response = await ownContentApi.previewDouyinImport(selectedFile.value)
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
    const response = await ownContentApi.importDouyinWorks(selectedFile.value, accountName.value.trim() || '太阳鸟')
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
  loadingWorks.value = true
  try {
    const response = await ownContentApi.getDouyinWorks(200)
    works.value = response.data || []
  } catch (error) {
    console.error('获取我的作品失败:', error)
  } finally {
    loadingWorks.value = false
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

onMounted(fetchWorks)
</script>

<style lang="scss" scoped>
.own-content-review {
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

  .account-input {
    width: 180px;
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
}
</style>
