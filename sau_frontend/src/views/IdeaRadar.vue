<template>
  <div class="idea-radar">
    <div class="page-header">
      <div>
        <h1>观点雷达</h1>
        <p>从抖音对标作品里提炼可迁移观点，生成你能直接拍的选题。</p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="targetDirection"
          placeholder="账号定位"
          clearable
          style="width: 260px"
        />
        <el-button type="primary" :loading="loadingVideos" @click="fetchVideos">
          刷新作品
        </el-button>
      </div>
    </div>

    <div class="radar-layout">
      <section class="video-panel">
        <div class="panel-title">
          <span>高赞对标作品</span>
          <small>{{ filteredVideos.length }} 条</small>
        </div>
        <div class="filter-row">
          <el-input v-model="keyword" placeholder="搜索标题 / 账号" clearable />
        </div>

        <el-scrollbar height="calc(100vh - 230px)" v-loading="loadingVideos">
          <button
            v-for="video in filteredVideos"
            :key="video.id"
            class="video-item"
            :class="{ active: selectedVideo?.id === video.id }"
            @click="selectVideo(video)"
          >
            <div class="video-meta">
              <span class="account">{{ video.account_name || '对标账号' }}</span>
              <span class="likes">{{ formatNumber(video.like_score) }} 赞</span>
            </div>
            <div class="video-title">{{ video.title }}</div>
          </button>
          <el-empty v-if="!loadingVideos && filteredVideos.length === 0" description="暂无对标作品" />
        </el-scrollbar>
      </section>

      <section class="result-panel" v-loading="analyzing">
        <template v-if="radar">
          <div class="source-bar">
            <div>
              <span class="source-account">{{ radar.source.account_name }}</span>
              <h2>{{ radar.viral_theme }}</h2>
            </div>
            <el-link :href="radar.source.video_url" target="_blank" type="primary">
              打开原作品
            </el-link>
          </div>

          <div class="formula">{{ radar.formula }}</div>

          <div class="analysis-basis">
            <el-tag type="success" effect="plain">根据视频完整文案分析</el-tag>
            <span v-if="taskState?.engine">{{ taskState.engine }} · {{ taskState.model }}</span>
          </div>

          <el-collapse v-if="taskState?.progress_log?.length" class="completion-log">
            <el-collapse-item
              :title="`本次处理日志 · 用时 ${formatDuration(taskState.elapsed_seconds)}`"
              name="task-log"
            >
              <div class="log-list">
                <div
                  v-for="(entry, index) in taskState.progress_log"
                  :key="`${entry.time}-${index}`"
                  class="log-entry"
                >
                  <span class="log-time">{{ entry.time }}</span>
                  <span class="log-percent">{{ entry.percent }}%</span>
                  <span class="log-message">{{ entry.message }}</span>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>

          <div v-if="taskState?.cleaned_transcript" class="section-block">
            <el-collapse>
              <el-collapse-item title="查看视频转写文案" name="transcript">
                <div class="transcript-box">{{ taskState.cleaned_transcript }}</div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <div v-if="radar.content_breakdown" class="section-block breakdown-card">
            <div class="section-label">正文拆解</div>
            <h3>{{ radar.content_breakdown.summary }}</h3>
            <p><strong>目标人群：</strong>{{ radar.content_breakdown.target_audience }}</p>
            <p><strong>开头钩子：</strong>{{ radar.content_breakdown.hook }}</p>
            <p><strong>核心观点：</strong>{{ radar.content_breakdown.core_viewpoint }}</p>
            <div class="breakdown-grid">
              <div>
                <strong>内容结构</strong>
                <ul><li v-for="item in radar.content_breakdown.structure" :key="item">{{ item }}</li></ul>
              </div>
              <div>
                <strong>机会链路</strong>
                <ul><li v-for="item in radar.content_breakdown.opportunity_chain" :key="item">{{ item }}</li></ul>
              </div>
            </div>
          </div>

          <div class="section-block">
            <div class="section-label">反常识观点</div>
            <div class="big-viewpoint">{{ radar.contrarian_viewpoint }}</div>
          </div>

          <div class="insight-grid">
            <div class="insight-box">
              <div class="section-label">人群焦虑</div>
              <ul>
                <li v-for="item in radar.audience_anxieties" :key="item">{{ item }}</li>
              </ul>
            </div>
            <div class="insight-box">
              <div class="section-label">可迁移方向</div>
              <ul>
                <li v-for="item in radar.migration_angles" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>

          <div class="section-block">
            <div class="section-label">证据类型</div>
            <div class="tag-row">
              <el-tag v-for="item in radar.evidence_types" :key="item" effect="plain">
                {{ item }}
              </el-tag>
            </div>
          </div>

          <div class="section-block">
            <div class="section-label">可拍选题</div>
            <div class="title-list">
              <div v-for="(title, index) in radar.recommended_titles" :key="title" class="title-item">
                <span>{{ index + 1 }}</span>
                <strong>{{ title }}</strong>
              </div>
            </div>
          </div>

          <div class="section-block">
            <div class="section-label">口播开头</div>
            <pre class="script-box">{{ radar.opening_script }}</pre>
          </div>

          <div v-if="radar.personalized_script" class="section-block">
            <div class="section-label">适合我的完整口播文案</div>
            <pre class="script-box">{{ radar.personalized_script }}</pre>
          </div>
        </template>

        <div v-else-if="taskState && taskState.status !== 'idle'" class="task-state-card">
          <template v-if="taskState.status === 'failed'">
            <el-result icon="error" title="视频解析失败" :sub-title="taskState.error_message || '请重新解析'">
              <template #extra>
                <el-button type="primary" @click="retryAnalysis">重新解析</el-button>
              </template>
            </el-result>
            <el-alert
              v-if="taskState.analysis_basis === 'title_only'"
              title="尚未获得视频正文，当前不会生成完整拆解。"
              type="warning"
              :closable="false"
            />
          </template>
          <template v-else>
            <div class="progress-header">
              <div>
                <div class="progress-stage">{{ stageLabel }}</div>
                <div class="progress-message">
                  {{ taskState.progress_message || '任务正在后台处理' }}
                </div>
              </div>
              <strong>{{ taskProgress }}%</strong>
            </div>
            <el-progress
              :percentage="taskProgress"
              :stroke-width="12"
              :show-text="false"
              striped
              striped-flow
            />
            <div class="progress-meta">
              <span>已用时 {{ formatDuration(taskState.elapsed_seconds) }}</span>
              <span v-if="taskState.engine">{{ taskState.engine }} · {{ taskState.model }}</span>
            </div>
          </template>

          <div v-if="taskState.progress_log?.length" class="task-log">
            <div class="task-log-title">运行日志</div>
            <div class="log-list">
              <div
                v-for="(entry, index) in taskState.progress_log"
                :key="`${entry.time}-${index}`"
                class="log-entry"
              >
                <span class="log-time">{{ entry.time }}</span>
                <span class="log-percent">{{ entry.percent }}%</span>
                <span class="log-message">{{ entry.message }}</span>
              </div>
            </div>
          </div>
        </div>

        <el-empty
          v-else-if="!analyzing"
          description="选择一条高赞对标作品，生成观点雷达"
          :image-size="110"
        />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { benchmarkApi } from '@/api/benchmark'

const videos = ref([])
const selectedVideo = ref(null)
const radar = ref(null)
const taskState = ref(null)
const keyword = ref('')
const loadingVideos = ref(false)
const analyzing = ref(false)
const targetDirection = ref('AI 生产系统研究员')
let pollingTimer = null
let selectionToken = 0

const stageLabels = {
  pending: '等待解析',
  downloading: '正在下载视频',
  transcribing: '正在识别视频文案',
  analyzing: '正在拆解正文和分析机会',
  complete: '解析完成'
}

const stageLabel = computed(() => stageLabels[taskState.value?.stage] || '正在处理')
const taskProgress = computed(() => Math.max(0, Math.min(Number(taskState.value?.progress_percent || 0), 100)))

const filteredVideos = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return videos.value
  return videos.value.filter((video) => {
    return `${video.title || ''} ${video.account_name || ''}`.toLowerCase().includes(q)
  })
})

const formatNumber = (value) => {
  const n = Number(value || 0)
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return n.toLocaleString()
}

const formatDuration = (seconds) => {
  const value = Math.max(0, Number(seconds || 0))
  const minutes = Math.floor(value / 60)
  const remainingSeconds = Math.floor(value % 60)
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60)
    return `${hours}小时${minutes % 60}分${remainingSeconds}秒`
  }
  return minutes ? `${minutes}分${remainingSeconds}秒` : `${remainingSeconds}秒`
}

const fetchVideos = async () => {
  loadingVideos.value = true
  try {
    const res = await benchmarkApi.getIdeaRadarVideos(100)
    videos.value = res.data || []
    if (!selectedVideo.value && videos.value.length) {
      await selectVideo(videos.value[0])
    }
  } catch (error) {
    console.error('获取观点雷达作品失败:', error)
    ElMessage.error('获取观点雷达作品失败')
  } finally {
    loadingVideos.value = false
  }
}

const selectVideo = async (video) => {
  selectionToken += 1
  const token = selectionToken
  stopPolling()
  selectedVideo.value = video
  radar.value = null
  taskState.value = null
  analyzing.value = true
  try {
    const res = await benchmarkApi.analyzeIdeaRadarVideo(video.id, targetDirection.value)
    if (token !== selectionToken) return
    applyTaskState(res.data)
    if (!radar.value && !['failed', 'success'].includes(res.data?.status)) {
      startPolling(video.id, token)
    }
  } catch (error) {
    console.error('观点分析失败:', error)
    ElMessage.error('观点分析失败')
  } finally {
    analyzing.value = false
  }
}

const applyTaskState = (state) => {
  taskState.value = state || null
  radar.value = state?.status === 'success' ? state.radar_json : null
}

const stopPolling = () => {
  if (pollingTimer) {
    clearTimeout(pollingTimer)
    pollingTimer = null
  }
}

const startPolling = (videoId, token) => {
  stopPolling()
  pollingTimer = setTimeout(async () => {
    try {
      const res = await benchmarkApi.getIdeaRadarStatus(videoId)
      if (token !== selectionToken) return
      applyTaskState(res.data)
      if (!['success', 'failed'].includes(res.data?.status)) {
        startPolling(videoId, token)
      }
    } catch (error) {
      if (token === selectionToken) startPolling(videoId, token)
    }
  }, 2000)
}

const retryAnalysis = async () => {
  if (!selectedVideo.value) return
  const token = ++selectionToken
  stopPolling()
  radar.value = null
  analyzing.value = true
  try {
    const res = await benchmarkApi.analyzeIdeaRadarVideo(
      selectedVideo.value.id,
      targetDirection.value,
      { force: true }
    )
    if (token !== selectionToken) return
    applyTaskState(res.data)
    startPolling(selectedVideo.value.id, token)
  } catch (error) {
    ElMessage.error('重新解析失败')
  } finally {
    analyzing.value = false
  }
}

onMounted(fetchVideos)
onBeforeUnmount(stopPolling)
</script>

<style lang="scss" scoped>
.idea-radar {
  .page-header {
    display: flex;
    justify-content: space-between;
    gap: 20px;
    align-items: flex-start;
    margin-bottom: 18px;

    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 650;
      color: #20232a;
    }

    p {
      margin: 6px 0 0;
      color: #6b7280;
      font-size: 14px;
    }
  }

  .header-actions {
    display: flex;
    gap: 10px;
    align-items: center;
  }
}

.radar-layout {
  display: grid;
  grid-template-columns: minmax(330px, 420px) minmax(0, 1fr);
  gap: 16px;
}

.video-panel,
.result-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.video-panel {
  padding: 14px;
}

.panel-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 650;
  color: #1f2937;
  margin-bottom: 12px;

  small {
    font-weight: 400;
    color: #8a94a6;
  }
}

.filter-row {
  margin-bottom: 12px;
}

.video-item {
  width: 100%;
  text-align: left;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: border-color 0.16s, background-color 0.16s;

  &:hover,
  &.active {
    border-color: #409eff;
    background: #f3f8ff;
  }
}

.video-meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  margin-bottom: 8px;

  .account {
    color: #4b5563;
  }

  .likes {
    color: #f56c6c;
    font-weight: 650;
    white-space: nowrap;
  }
}

.video-title {
  color: #111827;
  font-size: 14px;
  line-height: 1.55;
}

.result-panel {
  min-height: calc(100vh - 165px);
  padding: 22px;
}

.source-bar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;

  h2 {
    margin: 4px 0 0;
    font-size: 24px;
    color: #111827;
  }
}

.source-account {
  color: #6b7280;
  font-size: 13px;
}

.formula {
  display: inline-flex;
  padding: 8px 12px;
  background: #111827;
  color: #fff;
  border-radius: 6px;
  font-size: 13px;
  margin-bottom: 18px;
}

.analysis-basis {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #6b7280;
  font-size: 13px;
  margin-bottom: 16px;
}

.transcript-box {
  white-space: pre-wrap;
  line-height: 1.8;
  color: #374151;
  max-height: 360px;
  overflow: auto;
  padding: 4px 8px 12px;
}

.completion-log {
  margin-bottom: 18px;
}

.breakdown-card {
  border: 1px solid #dbeafe;
  background: #f8fbff;
  border-radius: 8px;
  padding: 16px;

  h3 {
    margin: 0 0 12px;
    color: #111827;
  }

  p {
    color: #374151;
    line-height: 1.7;
  }
}

.breakdown-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;

  ul {
    margin: 8px 0 0;
    padding-left: 18px;
  }

  li {
    margin-bottom: 6px;
    line-height: 1.6;
    color: #374151;
  }
}

.task-state-card {
  min-height: 440px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 760px;
  margin: 0 auto;
}

.progress-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 14px;

  strong {
    color: #111827;
    font-size: 28px;
  }
}

.progress-stage {
  color: #111827;
  font-size: 20px;
  font-weight: 650;
}

.progress-message {
  margin-top: 6px;
  color: #6b7280;
  font-size: 14px;
}

.progress-meta {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-top: 10px;
  color: #6b7280;
  font-size: 13px;
}

.task-log {
  margin-top: 24px;
  border-top: 1px solid #e5e7eb;
  padding-top: 16px;
}

.task-log-title {
  margin-bottom: 10px;
  color: #374151;
  font-size: 14px;
  font-weight: 650;
}

.log-list {
  max-height: 240px;
  overflow-y: auto;
  font-size: 13px;
}

.log-entry {
  display: grid;
  grid-template-columns: 70px 48px minmax(0, 1fr);
  gap: 8px;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid #f3f4f6;
}

.log-time,
.log-percent {
  color: #9ca3af;
  font-variant-numeric: tabular-nums;
}

.log-message {
  min-width: 0;
  color: #374151;
  overflow-wrap: anywhere;
}

.section-block {
  margin-top: 18px;
}

.section-label {
  font-size: 13px;
  font-weight: 650;
  color: #6b7280;
  margin-bottom: 8px;
}

.big-viewpoint {
  font-size: 20px;
  line-height: 1.55;
  color: #1f2937;
  font-weight: 650;
  padding: 16px;
  background: #f8fafc;
  border-left: 4px solid #409eff;
  border-radius: 6px;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.insight-box {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 14px;

  ul {
    margin: 0;
    padding-left: 18px;
  }

  li {
    color: #374151;
    line-height: 1.7;
    margin-bottom: 5px;
  }
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.title-list {
  display: grid;
  gap: 10px;
}

.title-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;

  span {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #409eff;
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    font-size: 12px;
  }

  strong {
    color: #111827;
    line-height: 1.55;
  }
}

.script-box {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 14px;
  border-radius: 6px;
  background: #111827;
  color: #f9fafb;
  font-family: inherit;
  line-height: 1.7;
}

@media (max-width: 980px) {
  .idea-radar .page-header,
  .radar-layout,
  .insight-grid,
  .breakdown-grid {
    grid-template-columns: 1fr;
  }

  .idea-radar .page-header {
    display: block;
  }

  .idea-radar .header-actions {
    margin-top: 12px;
  }
}
</style>
