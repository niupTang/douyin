<template>
  <div class="idea-radar">
    <header class="page-header">
      <div>
        <div class="page-kicker">AI 洞察工作台</div>
        <h1>观点雷达</h1>
        <p>从真实视频正文中提炼结构、机会和可以直接开拍的选题。</p>
      </div>
      <div class="header-actions">
        <el-input v-model="targetDirection" :prefix-icon="Search" placeholder="输入账号定位" clearable />
        <el-button type="primary" :icon="Refresh" :loading="loadingVideos" @click="fetchVideos">
          刷新作品
        </el-button>
      </div>
    </header>

    <div class="download-location">
      <span>下载目录：{{ downloadDirectory || '未选择' }}</span>
      <el-button size="small" @click="chooseDownloadDirectory">选择目录</el-button>
    </div>

    <div class="radar-workspace">
      <aside class="video-panel">
        <div class="panel-heading">
          <div>
            <strong>热门对标作品</strong>
            <span>按热度选择分析样本</span>
          </div>
          <small>{{ filteredVideos.length }} 条</small>
        </div>
        <el-input v-model="keyword" :prefix-icon="Search" placeholder="搜索标题、账号或关键词" clearable />

        <el-scrollbar class="video-scroll" v-loading="loadingVideos">
          <button
            v-for="video in filteredVideos"
            :key="video.id"
            class="video-item"
            :class="{ active: selectedVideo?.id === video.id }"
            @click="selectVideo(video)"
          >
            <div class="video-topline">
              <span class="platform-mark">抖</span>
              <span class="account">{{ video.account_name || '对标账号' }}</span>
              <span class="heat">{{ formatNumber(video.like_score) }}</span>
            </div>
            <strong class="video-title">{{ video.title || '未命名作品' }}</strong>
            <p>{{ video.title || '暂无作品摘要' }}</p>
            <div class="video-foot">
              <span>{{ video.created_at ? formatDate(video.created_at) : '已同步' }}</span>
              <span class="likes">● {{ formatNumber(video.like_score) }} 赞</span>
            </div>
          </button>
          <el-empty v-if="!loadingVideos && filteredVideos.length === 0" description="暂无对标作品" :image-size="72" />
        </el-scrollbar>
      </aside>

      <main class="analysis-panel" v-loading="analyzing">
        <template v-if="radar">
          <section class="source-hero">
            <div class="source-toolbar">
              <el-button text :icon="ArrowLeft" @click="selectedVideo = null; radar = null; taskState = null">返回</el-button>
              <el-link @click.prevent="openDouyinPreview(radar.source.video_url)" type="primary">打开原作品 ↗</el-link>
            </div>
            <div class="source-main">
              <div class="source-copy">
                <span class="source-account">{{ radar.source.account_name || selectedVideo?.account_name }}</span>
                <h2>{{ radar.viral_theme }}</h2>
                <div class="formula-tags">
                  <span v-for="item in formulaParts" :key="item">{{ item }}</span>
                </div>
              </div>
              <div class="heat-panel">
                <span>●</span>
                <strong>{{ formatNumber(selectedVideo?.like_score) }}</strong>
                <small>作品热度</small>
              </div>
            </div>
            <div class="source-meta">
              <el-tag type="success" effect="light">视频 · 观点类</el-tag>
              <span>分析方向：{{ targetDirection }}</span>
              <span v-if="taskState?.engine">{{ taskState.engine }} · {{ taskState.model }}</span>
              <span>完整文案分析</span>
            </div>
          </section>

          <nav class="analysis-tabs">
            <button
              v-for="tab in analysisTabs"
              :key="tab.key"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              <el-icon><component :is="tab.icon" /></el-icon>
              {{ tab.label }}
            </button>
            <div class="tab-actions">
              <el-tooltip content="复制分析内容" placement="bottom">
                <el-button :icon="CopyDocument" aria-label="复制分析内容" @click="copyAnalysis"><span class="action-label">复制内容</span></el-button>
              </el-tooltip>
              <el-tooltip content="导出 Markdown 方案" placement="bottom">
                <el-button :icon="Download" aria-label="导出分析方案" @click="exportAnalysis"><span class="action-label">导出方案</span></el-button>
              </el-tooltip>
            </div>
          </nav>

          <div class="analysis-body tab-view">
            <section v-if="activeTab === 'breakdown'" class="tab-page breakdown-page">
              <article class="analysis-card tone-red breakdown-card">
                <div class="card-title"><span>01</span><strong>正文拆解</strong></div>
                <h3>{{ radar.content_breakdown?.summary || radar.viral_theme }}</h3>
                <dl class="fact-list">
                  <div><dt>目标人群</dt><dd>{{ radar.content_breakdown?.target_audience || '-' }}</dd></div>
                  <div><dt>开头钩子</dt><dd>{{ radar.content_breakdown?.hook || '-' }}</dd></div>
                  <div><dt>核心观点</dt><dd>{{ radar.content_breakdown?.core_viewpoint || '-' }}</dd></div>
                </dl>
              </article>
              <section class="viewpoint-band">
                <div class="band-label">反常识观点</div>
                <blockquote>{{ radar.contrarian_viewpoint }}</blockquote>
                <span class="quote-mark">”</span>
              </section>
              <article class="analysis-card breakdown-formula">
                <div class="card-title"><span>+</span><strong>爆款公式</strong></div>
                <div class="formula-flow">
                  <template v-for="(item, index) in formulaParts" :key="item">
                    <span>{{ item }}</span><b v-if="index < formulaParts.length - 1">×</b>
                  </template>
                </div>
              </article>
            </section>

            <section v-else-if="activeTab === 'structure'" class="tab-page structure-page">
              <article class="analysis-card tone-blue structure-card">
                <div class="card-title"><span>02</span><strong>内容结构拆解</strong><small>可复用</small></div>
                <div class="timeline">
                  <div v-for="(item, index) in radar.content_breakdown?.structure" :key="item" class="timeline-item">
                    <span class="timeline-index">{{ String(index + 1).padStart(2, '0') }}</span>
                    <div><strong>{{ structureLabel(item) }}</strong><p>{{ item }}</p></div>
                  </div>
                </div>
              </article>
              <article class="analysis-card structure-summary">
                <div class="card-title"><span>↗</span><strong>结构复用提醒</strong></div>
                <p>复用信息推进顺序和论证机制，不直接复制原作者经历、身份与表达原句。</p>
                <div class="structure-chips"><span v-for="item in formulaParts" :key="item">{{ item }}</span></div>
              </article>
            </section>

            <section v-else-if="activeTab === 'opportunity'" class="tab-page opportunity-page">
              <article class="analysis-card tone-purple opportunity-card">
                <div class="card-title"><span>03</span><strong>机会洞察</strong><small>切入角度</small></div>
                <div class="opportunity-list">
                  <div v-for="(item, index) in opportunityItems" :key="item">
                    <span>{{ opportunityLabels[index] || `方向 ${index + 1}` }}</span>
                    <p>{{ item }}</p>
                  </div>
                </div>
              </article>
              <article class="analysis-card migration-card">
                <div class="card-title"><span>↗</span><strong>太阳鸟可迁移方向</strong></div>
                <div class="migration-list">
                  <div v-for="(item, index) in radar.migration_angles" :key="item"><span>{{ String(index + 1).padStart(2, '0') }}</span><p>{{ item }}</p></div>
                </div>
              </article>
            </section>

            <section v-else-if="activeTab === 'audience'" class="tab-page audience-page">
              <article class="analysis-card tone-orange audience-card">
                <div class="card-title"><span>04</span><strong>人群画像</strong></div>
                <div class="persona-tags">
                  <span v-for="tag in audienceTags" :key="tag">{{ tag }}</span>
                </div>
                <ul class="clean-list">
                  <li v-for="item in radar.audience_anxieties" :key="item">{{ item }}</li>
                </ul>
              </article>
              <article class="analysis-card audience-summary">
                <div class="card-title"><span>!</span><strong>核心需求</strong></div>
                <p>{{ radar.content_breakdown?.target_audience }}</p>
                <blockquote>{{ radar.contrarian_viewpoint }}</blockquote>
              </article>
            </section>

            <section v-else-if="activeTab === 'evidence'" class="tab-page evidence-page">
              <article class="analysis-card tone-green evidence-card">
                <div class="card-title"><span>05</span><strong>证据与支撑</strong><small>可引用</small></div>
                <ul class="evidence-list">
                  <li v-for="item in radar.evidence_types" :key="item"><span>✓</span>{{ item }}</li>
                </ul>
                <div class="basis-note">分析依据：视频完整转写、内容结构与作品公开数据</div>
              </article>
              <section class="details-section evidence-details">
                <el-collapse>
                  <el-collapse-item v-if="taskState?.cleaned_transcript" title="查看视频完整转写文案" name="transcript">
                    <div class="transcript-box">{{ taskState.cleaned_transcript }}</div>
                  </el-collapse-item>
                  <el-collapse-item v-if="taskState?.progress_log?.length" :title="`本次处理日志 · 用时 ${formatDuration(taskState.elapsed_seconds)}`" name="log">
                    <div class="log-list">
                      <div v-for="(entry, index) in taskState.progress_log" :key="`${entry.time}-${index}`" class="log-entry">
                        <span>{{ entry.time }}</span><span>{{ entry.percent }}%</span><p>{{ entry.message }}</p>
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </section>
            </section>

            <section v-else class="tab-page titles-page">
              <section class="topics-section">
                <div class="section-heading">
                  <div><span>06</span><div><strong>延伸选题</strong><small>可以直接进入创作流程</small></div></div>
                </div>
                <div class="topic-grid">
                  <article v-for="(title, index) in radar.recommended_titles" :key="title" class="topic-item">
                    <span>{{ String(index + 1).padStart(2, '0') }}</span>
                    <strong>{{ title }}</strong>
                    <el-button text :icon="CopyDocument" aria-label="复制选题" @click="copyText(title, '选题已复制')" />
                  </article>
                </div>
              </section>
              <section class="script-grid">
                <article class="script-panel">
                  <div class="script-header"><strong>口播开头</strong><el-button text :icon="CopyDocument" @click="copyText(radar.opening_script, '开头已复制')">复制</el-button></div>
                  <div class="script-content">{{ radar.opening_script }}</div>
                </article>
                <article v-if="radar.personalized_script" class="script-panel">
                  <div class="script-header"><strong>适合我的完整口播文案</strong><el-button text :icon="CopyDocument" @click="copyText(radar.personalized_script, '口播文案已复制')">复制</el-button></div>
                  <div class="script-content">{{ radar.personalized_script }}</div>
                </article>
              </section>
            </section>
          </div>
        </template>

        <div v-else-if="taskState && taskState.status !== 'idle'" class="task-state-card">
          <template v-if="taskState.status === 'failed'">
            <el-result icon="error" :title="taskState.stage === 'analyzing' ? '模型分析失败' : '视频处理失败'" :sub-title="taskState.error_message || '请重新解析'">
              <template #extra><el-button v-if="taskState.stage === 'analyzing'" @click="$router.push('/agent-models')">检查模型设置</el-button><el-button type="primary" @click="retryAnalysis">{{ taskState.stage === 'analyzing' ? '重试分析' : '重新解析' }}</el-button></template>
            </el-result>
          </template>
          <template v-else>
            <div class="progress-header">
              <div><span>AI 正在工作</span><strong>{{ stageLabel }}</strong><p>{{ taskState.progress_message || '任务正在后台处理' }}</p></div>
              <b>{{ taskProgress }}%</b>
            </div>
            <el-progress :percentage="taskProgress" :stroke-width="10" :show-text="false" striped striped-flow />
            <div class="progress-meta"><span>已用时 {{ formatDuration(taskState.elapsed_seconds) }}</span><span v-if="taskState.engine">{{ taskState.engine }} · {{ taskState.model }}</span></div>
            <div v-if="taskState.progress_log?.length" class="compact-log">
              <div v-for="entry in taskState.progress_log.slice(-3)" :key="`${entry.time}-${entry.percent}`"><span>{{ entry.percent }}%</span>{{ entry.message }}</div>
            </div>
          </template>
        </div>

        <div v-else-if="!analyzing" class="empty-state">
          <div class="empty-mark">R</div>
          <h2>选择一条对标作品</h2>
          <p>系统将读取完整文案，拆解内容结构、机会和可拍选题。</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  CopyDocument,
  DataAnalysis,
  Document,
  Download,
  Opportunity,
  Refresh,
  Search,
  Tickets,
  TrendCharts,
  User
} from '@element-plus/icons-vue'
import { benchmarkApi } from '@/api/benchmark'
import { useDouyinPreview } from '@/composables/useDouyinPreview'

const { openDouyinPreview } = useDouyinPreview()
import { useDownloadDirectory } from '@/composables/useDownloadDirectory'
import { browserSettingsApi } from '@/api/browserSettings'

const videos = ref([])
const selectedVideo = ref(null)
const radar = ref(null)
const taskState = ref(null)
const keyword = ref('')
const loadingVideos = ref(false)
const analyzing = ref(false)
const targetDirection = ref('AI 生产系统研究员')
const activeTab = ref('breakdown')
const { downloadDirectory, loadDownloadDirectory, chooseDownloadDirectory, ensureDownloadDirectory } = useDownloadDirectory()
let pollingTimer = null
let selectionToken = 0

const analysisTabs = [
  { key: 'breakdown', label: '正文拆解', icon: Document },
  { key: 'structure', label: '内容结构', icon: DataAnalysis },
  { key: 'opportunity', label: '机会洞察', icon: Opportunity },
  { key: 'audience', label: '人群画像', icon: User },
  { key: 'evidence', label: '证据链路', icon: Tickets },
  { key: 'titles', label: '延伸选题', icon: TrendCharts }
]

const stageLabels = {
  pending: '等待解析',
  downloading: '正在下载视频',
  transcribing: '正在识别视频文案',
  analyzing: '正在拆解正文和分析机会',
  complete: '解析完成'
}

const opportunityLabels = ['反常识表达', '情绪共鸣点', '可复制方法论', '适配人群', '延伸方向']
const stageLabel = computed(() => stageLabels[taskState.value?.stage] || '正在处理')
const taskProgress = computed(() => Math.max(0, Math.min(Number(taskState.value?.progress_percent || 0), 100)))
const formulaParts = computed(() => String(radar.value?.formula || '').split(/[×+]/).map(item => item.trim()).filter(Boolean))
const opportunityItems = computed(() => {
  const chain = radar.value?.content_breakdown?.opportunity_chain || []
  const migrations = radar.value?.migration_angles || []
  return [...chain, ...migrations].filter((item, index, all) => all.indexOf(item) === index).slice(0, 5)
})
const audienceTags = computed(() => {
  const text = radar.value?.content_breakdown?.target_audience || ''
  const tags = text.split(/[、，,；;]/).map(item => item.trim()).filter(Boolean)
  return tags.length ? tags.slice(0, 5) : ['内容创作者', '创业者', '职场人']
})

const filteredVideos = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return videos.value
  return videos.value.filter(video => `${video.title || ''} ${video.account_name || ''}`.toLowerCase().includes(q))
})

const formatNumber = (value) => {
  const n = Number(value || 0)
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return n.toLocaleString()
}

const formatDate = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '已同步'
  const diff = Date.now() - date.getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours}小时前`
  if (hours < 168) return `${Math.floor(hours / 24)}天前`
  return date.toLocaleDateString('zh-CN')
}

const formatDuration = (seconds) => {
  const value = Math.max(0, Number(seconds || 0))
  const minutes = Math.floor(value / 60)
  const remainingSeconds = Math.floor(value % 60)
  return minutes ? `${minutes}分${remainingSeconds}秒` : `${remainingSeconds}秒`
}

const structureLabel = (item) => {
  const text = String(item || '')
  const match = text.match(/^([^：:。；;]{2,12})[：:]/)
  return match?.[1] || ['提出问题', '展开论证', '给出方法', '价值总结', '行动建议'][0]
}

const copyText = async (text, message = '内容已复制') => {
  if (!text) return ElMessage.warning('暂无可复制内容')
  await navigator.clipboard.writeText(String(text))
  ElMessage.success(message)
}

const analysisText = () => {
  if (!radar.value) return ''
  return [
    `# ${radar.value.viral_theme}`,
    `\n## 反常识观点\n${radar.value.contrarian_viewpoint}`,
    `\n## 人群焦虑\n${(radar.value.audience_anxieties || []).map(item => `- ${item}`).join('\n')}`,
    `\n## 迁移方向\n${(radar.value.migration_angles || []).map(item => `- ${item}`).join('\n')}`,
    `\n## 可拍选题\n${(radar.value.recommended_titles || []).map((item, index) => `${index + 1}. ${item}`).join('\n')}`,
    `\n## 口播开头\n${radar.value.opening_script || ''}`,
    radar.value.personalized_script ? `\n## 完整口播文案\n${radar.value.personalized_script}` : ''
  ].filter(Boolean).join('\n')
}

const copyAnalysis = () => copyText(analysisText(), '分析内容已复制')
const exportAnalysis = async () => {
  const content = analysisText()
  if (!content) return ElMessage.warning('暂无可导出的分析')
  if (!await ensureDownloadDirectory()) return
  try {
    const result = await browserSettingsApi.saveMarkdown(
      `观点雷达-${selectedVideo.value?.id || 'analysis'}.md`, content
    )
    ElMessage.success(`分析方案已保存：${result.data.path}`)
  } catch (error) {
    console.error('保存分析方案失败:', error)
  }
}

const fetchVideos = async () => {
  loadingVideos.value = true
  try {
    const res = await benchmarkApi.getIdeaRadarVideos(100)
    videos.value = res.data || []
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
  activeTab.value = 'breakdown'
  try {
    const status = await benchmarkApi.getIdeaRadarStatus(video.id)
    if (token !== selectionToken) return
    if (!status.data?.cleaned_transcript && !await ensureDownloadDirectory()) return
    const res = await benchmarkApi.analyzeIdeaRadarVideo(video.id, targetDirection.value)
    if (token !== selectionToken) return
    applyTaskState(res.data)
    if (!radar.value && !['failed', 'success'].includes(res.data?.status)) startPolling(video.id, token)
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
  if (pollingTimer) clearTimeout(pollingTimer)
  pollingTimer = null
}

const startPolling = (videoId, token) => {
  stopPolling()
  pollingTimer = setTimeout(async () => {
    try {
      const res = await benchmarkApi.getIdeaRadarStatus(videoId)
      if (token !== selectionToken) return
      applyTaskState(res.data)
      if (!['success', 'failed'].includes(res.data?.status)) startPolling(videoId, token)
    } catch {
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
    if (!taskState.value?.cleaned_transcript && !await ensureDownloadDirectory()) return
    const res = await benchmarkApi.analyzeIdeaRadarVideo(selectedVideo.value.id, targetDirection.value, { force: true })
    if (token !== selectionToken) return
    applyTaskState(res.data)
    startPolling(selectedVideo.value.id, token)
  } catch {
    ElMessage.error('重新解析失败')
  } finally {
    analyzing.value = false
  }
}

onMounted(() => {
  fetchVideos()
  loadDownloadDirectory().catch(() => {})
})
onBeforeUnmount(stopPolling)
</script>

<style lang="scss" scoped>
.idea-radar {
  --accent: #ff4f4f;
  --text: #171a21;
  --muted: #70798a;
  --line: #e7eaf0;
  min-width: 0;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;

  h1 { margin: 2px 0 0; color: var(--text); font-size: 26px; line-height: 1.2; }
  p { margin: 6px 0 0; color: var(--muted); font-size: 13px; }
}

.page-kicker { color: var(--accent); font-size: 12px; font-weight: 700; }
.download-location { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; color: var(--muted); font-size: 12px; }
.download-location span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.header-actions { display: flex; gap: 10px; width: min(470px, 45%); }
.header-actions .el-input { flex: 1; }

.radar-workspace {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  min-height: calc(100vh - 178px);
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 32px rgba(28, 39, 56, 0.05);
  overflow: hidden;
}

.video-panel { min-width: 0; padding: 16px 12px 0; border-right: 1px solid var(--line); background: #fbfcfd; }
.panel-heading { display: flex; justify-content: space-between; gap: 12px; margin: 0 4px 14px; }
.panel-heading strong, .panel-heading span { display: block; }
.panel-heading strong { color: var(--text); font-size: 16px; }
.panel-heading span { margin-top: 3px; color: var(--muted); font-size: 11px; }
.panel-heading small { color: var(--muted); white-space: nowrap; }
.video-scroll { height: calc(100vh - 278px); margin-top: 12px; padding-right: 2px; }

.video-item {
  width: 100%; margin-bottom: 10px; padding: 12px; text-align: left; cursor: pointer;
  border: 1px solid var(--line); border-radius: 7px; background: #fff;
  transition: border-color .16s, background-color .16s, box-shadow .16s;
}
.video-item:hover { border-color: #ffb1ad; }
.video-item.active { border-color: var(--accent); background: #fff8f7; box-shadow: 0 5px 16px rgba(255, 79, 79, .08); }
.video-topline { display: flex; align-items: center; gap: 7px; min-width: 0; font-size: 12px; }
.platform-mark { width: 21px; height: 21px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 5px; background: #181b22; color: #fff; font-size: 11px; font-weight: 800; }
.video-topline .account { color: #444c5a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.video-topline .heat { margin-left: auto; color: var(--accent); font-weight: 700; white-space: nowrap; }
.video-title { display: -webkit-box; margin-top: 9px; overflow: hidden; color: var(--text); font-size: 14px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.video-item p { display: -webkit-box; margin: 7px 0 0; overflow: hidden; color: var(--muted); font-size: 12px; line-height: 1.5; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.video-foot { display: flex; justify-content: space-between; gap: 8px; margin-top: 10px; color: #9aa2b1; font-size: 11px; }
.video-foot .likes { color: var(--accent); }

.analysis-panel { min-width: 0; background: #fff; }
.source-hero { padding: 16px 22px 14px; border-bottom: 1px solid var(--line); }
.source-toolbar { display: flex; align-items: center; justify-content: space-between; }
.source-main { display: flex; align-items: center; justify-content: space-between; gap: 28px; margin-top: 10px; }
.source-copy { min-width: 0; }
.source-account { color: var(--muted); font-size: 12px; }
.source-copy h2 { max-width: 960px; margin: 6px 0 10px; color: var(--text); font-size: 25px; line-height: 1.34; letter-spacing: 0; }
.formula-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.formula-tags span { padding: 5px 9px; border-radius: 5px; background: #f1f3ff; color: #535d77; font-size: 11px; }
.heat-panel { display: grid; grid-template-columns: auto auto; align-items: center; gap: 2px 7px; flex: 0 0 auto; padding: 11px 14px; border-radius: 7px; background: #fff3f2; color: var(--accent); }
.heat-panel > span { grid-row: 1 / 3; }
.heat-panel strong { font-size: 18px; }
.heat-panel small { color: #8b5f5f; }
.source-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 9px 14px; margin-top: 12px; color: var(--muted); font-size: 11px; }

.analysis-tabs { position: sticky; top: 0; z-index: 8; display: flex; align-items: center; min-height: 54px; padding: 0 22px; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.96); backdrop-filter: blur(10px); }
.analysis-tabs > button { height: 54px; display: inline-flex; align-items: center; gap: 6px; padding: 0 12px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #515a6b; cursor: pointer; font-size: 12px; white-space: nowrap; }
.analysis-tabs > button.active { border-bottom-color: var(--accent); color: var(--accent); font-weight: 700; }
.tab-actions { display: flex; gap: 8px; margin-left: auto; }

.analysis-body { padding: 16px 20px 28px; background: #fbfcfe; }
.tab-view { min-height: 520px; }
.tab-page { min-height: 470px; }
.breakdown-page { display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(320px, .92fr); gap: 12px; align-items: start; }
.breakdown-page .breakdown-card { grid-row: span 2; }
.breakdown-page .viewpoint-band { margin-top: 0; }
.breakdown-formula { align-self: stretch; }
.formula-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.formula-flow span { padding: 8px 10px; border-radius: 6px; background: #f4f6fa; color: #3f4857; font-size: 12px; font-weight: 650; }
.formula-flow b { color: var(--accent); font-size: 12px; }
.structure-page, .opportunity-page, .audience-page, .evidence-page { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(280px, .85fr); gap: 12px; align-items: start; }
.structure-summary p, .audience-summary p { margin: 0; color: #535d6b; font-size: 13px; line-height: 1.7; }
.structure-chips { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 16px; }
.structure-chips span { padding: 6px 9px; border-radius: 5px; background: #edf2ff; color: #4e69ab; font-size: 11px; }
.migration-list { display: grid; gap: 9px; }
.migration-list > div { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 9px; padding: 10px; border-radius: 6px; background: #f7f8fa; }
.migration-list span { color: var(--accent); font-size: 11px; font-weight: 800; }
.migration-list p { margin: 0; color: #505966; font-size: 12px; line-height: 1.55; }
.audience-summary blockquote { margin: 16px 0 0; padding: 12px 14px; border-left: 3px solid #f2a44c; background: #fff9f1; color: #585044; font-size: 13px; line-height: 1.65; }
.evidence-details { margin-top: 0; padding: 0 14px; }
.analysis-card { min-width: 0; padding: 15px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.tone-red { border-color: #ffd8d4; background: #fff9f8; }
.tone-blue { border-color: #d7e2ff; background: #f8faff; }
.tone-purple { border-color: #e7dcff; background: #fbf9ff; }
.tone-orange { border-color: #ffe5c7; background: #fffbf6; }
.tone-green { border-color: #d2eee1; background: #f7fcf9; }
.card-title { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.card-title > span, .section-heading > div > span { width: 24px; height: 24px; display: grid; place-items: center; border-radius: 5px; background: #fff; color: var(--accent); font-size: 10px; font-weight: 800; box-shadow: 0 2px 8px rgba(20,30,45,.08); }
.card-title strong { color: var(--text); font-size: 14px; }
.card-title small { margin-left: auto; color: var(--muted); font-size: 10px; }
.breakdown-card h3 { margin: 0 0 12px; color: var(--text); font-size: 14px; line-height: 1.6; }
.fact-list { margin: 0; }
.fact-list > div { display: grid; grid-template-columns: 62px minmax(0, 1fr); gap: 8px; padding: 8px 0; border-top: 1px dashed #efc9c5; font-size: 12px; line-height: 1.55; }
.fact-list dt { color: var(--accent); font-weight: 700; }
.fact-list dd { margin: 0; color: #4f5766; }
.timeline { position: relative; }
.timeline::before { content: ''; position: absolute; top: 14px; bottom: 14px; left: 14px; width: 1px; background: #cad8fa; }
.timeline-item { position: relative; display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: 9px; padding-bottom: 10px; }
.timeline-index { z-index: 1; width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; background: #527eff; color: #fff; font-size: 10px; font-weight: 700; }
.timeline-item:nth-child(2) .timeline-index { background: #ff6868; }
.timeline-item:nth-child(3) .timeline-index { background: #35b983; }
.timeline-item:nth-child(4) .timeline-index { background: #9561e8; }
.timeline-item:nth-child(5) .timeline-index { background: #f5ae43; }
.timeline-item strong { color: #344b82; font-size: 12px; }
.timeline-item p { margin: 3px 0 0; color: var(--muted); font-size: 11px; line-height: 1.45; }
.opportunity-list { display: grid; gap: 7px; }
.opportunity-list > div { padding: 8px 9px; border-radius: 6px; background: rgba(255,255,255,.72); }
.opportunity-list span { color: #7951c4; font-size: 11px; font-weight: 700; }
.opportunity-list p { margin: 3px 0 0; color: #575f6d; font-size: 11px; line-height: 1.45; }

.viewpoint-band { position: relative; margin-top: 12px; padding: 15px 48px 15px 18px; border: 1px solid #dbe5ff; border-radius: 8px; background: #f5f8ff; }
.band-label { margin-bottom: 7px; color: #4d75dd; font-size: 11px; font-weight: 700; }
.viewpoint-band blockquote { margin: 0; color: #26334d; font-size: 17px; font-weight: 650; line-height: 1.55; }
.quote-mark { position: absolute; right: 18px; bottom: 3px; color: #5c82e5; font-family: Georgia, serif; font-size: 48px; }

.persona-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.persona-tags span { padding: 5px 9px; border-radius: 5px; background: #fff1df; color: #7a5b36; font-size: 11px; }
.clean-list { margin: 12px 0 0; padding-left: 18px; }
.clean-list li { margin-bottom: 5px; color: #5b606b; font-size: 12px; line-height: 1.55; }
.evidence-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.evidence-list li { display: flex; gap: 8px; color: #4f5c55; font-size: 12px; line-height: 1.5; }
.evidence-list li span { color: #2fb67c; font-weight: 800; }
.basis-note { margin-top: 12px; padding-top: 10px; border-top: 1px dashed #cfe5d8; color: #748078; font-size: 10px; }

.topics-section { padding: 16px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.section-heading > div { display: flex; align-items: center; gap: 9px; }
.section-heading strong, .section-heading small { display: block; }
.section-heading strong { color: var(--text); font-size: 14px; }
.section-heading small { margin-top: 2px; color: var(--muted); font-size: 10px; }
.topic-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 13px; }
.topic-item { display: grid; grid-template-columns: 28px minmax(0, 1fr) 32px; align-items: center; gap: 9px; padding: 10px 11px; border: 1px solid var(--line); border-radius: 6px; background: #fcfcfd; }
.topic-item > span { color: var(--accent); font-size: 11px; font-weight: 800; }
.topic-item strong { color: #343a45; font-size: 12px; line-height: 1.5; }
.script-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.script-panel { min-width: 0; border: 1px solid var(--line); border-radius: 8px; background: #fff; overflow: hidden; }
.script-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--line); }
.script-header strong { color: var(--text); font-size: 13px; }
.script-content { max-height: 280px; overflow: auto; padding: 14px; color: #4b5361; font-size: 12px; line-height: 1.75; white-space: pre-wrap; }
.details-section { margin-top: 12px; padding: 0 14px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.transcript-box { max-height: 360px; overflow: auto; color: #4b5563; font-size: 12px; line-height: 1.8; white-space: pre-wrap; }
.log-list { max-height: 240px; overflow: auto; }
.log-entry { display: grid; grid-template-columns: 70px 42px minmax(0,1fr); gap: 8px; padding: 6px 0; border-bottom: 1px solid #f0f2f5; color: var(--muted); font-size: 11px; }
.log-entry p { margin: 0; color: #4b5563; }

.task-state-card { width: min(720px, calc(100% - 48px)); margin: 80px auto 0; padding: 28px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.progress-header { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 16px; }
.progress-header span, .progress-header strong { display: block; }
.progress-header span { color: var(--accent); font-size: 11px; font-weight: 700; }
.progress-header strong { margin-top: 5px; color: var(--text); font-size: 20px; }
.progress-header p { margin: 5px 0 0; color: var(--muted); font-size: 12px; }
.progress-header b { color: var(--accent); font-size: 28px; }
.progress-meta { display: flex; justify-content: space-between; margin-top: 9px; color: var(--muted); font-size: 11px; }
.compact-log { display: grid; gap: 7px; margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--line); color: #515968; font-size: 11px; }
.compact-log span { display: inline-block; width: 38px; color: var(--accent); }
.empty-state { display: grid; place-items: center; align-content: center; min-height: 560px; text-align: center; }
.empty-mark { width: 52px; height: 52px; display: grid; place-items: center; border-radius: 8px; background: var(--accent); color: #fff; font-size: 22px; font-weight: 800; }
.empty-state h2 { margin: 14px 0 4px; color: var(--text); font-size: 19px; }
.empty-state p { color: var(--muted); font-size: 12px; }

@media (max-width: 1280px) {
  .radar-workspace { grid-template-columns: 270px minmax(0, 1fr); }
  .opportunity-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .analysis-tabs > button { padding: 0 8px; }
  .tab-actions .el-button { width: 32px; padding: 8px; }
  .tab-actions .action-label { display: none; }
}

@media (max-width: 960px) {
  .page-header { align-items: stretch; flex-direction: column; }
  .header-actions { width: 100%; }
  .radar-workspace { display: block; }
  .video-panel { border-right: 0; border-bottom: 1px solid var(--line); }
  .video-scroll { height: 300px; }
  .analysis-tabs { overflow-x: auto; }
  .analysis-tabs .tab-actions { display: none; }
  .source-main { align-items: flex-start; }
  .breakdown-page, .structure-page, .opportunity-page, .audience-page, .evidence-page, .script-grid { grid-template-columns: 1fr; }
  .breakdown-page .breakdown-card { grid-row: auto; }
}

@media (max-width: 620px) {
  .header-actions, .source-main { flex-direction: column; }
  .source-copy h2 { font-size: 21px; }
  .heat-panel { align-self: stretch; }
  .analysis-body { padding: 12px; }
  .source-hero { padding: 14px; }
  .topic-grid, .opportunity-list { grid-template-columns: 1fr; }
  .viewpoint-band blockquote { font-size: 15px; }
}
</style>
