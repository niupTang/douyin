<template>
  <div class="video-edit-workspace">
    <header class="workspace-topbar">
      <div class="brand-block">
        <div class="brand-mark">
          <el-icon><VideoCamera /></el-icon>
        </div>
        <div>
          <h1>AI 视频剪辑中心</h1>
          <p>一站式 AI 剪辑，高效产出爆款内容</p>
        </div>
      </div>

      <div class="workflow-steps">
        <div
          v-for="(step, index) in workflowSteps"
          :key="step.name"
          class="workflow-step"
          :class="{ active: index === activeStep, done: index < activeStep }"
        >
          <span class="step-index">
            <el-icon v-if="index < activeStep"><Check /></el-icon>
            <template v-else>{{ index + 1 }}</template>
          </span>
          <span>{{ step.name }}</span>
          <el-icon v-if="index < workflowSteps.length - 1" class="step-arrow"><ArrowRight /></el-icon>
        </div>
      </div>

      <div class="top-actions">
        <el-button text @click="fetchAll" :loading="isRefreshing">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="submitTalkingEdit" :disabled="!selectedMaterial" :loading="isEditing">
          <el-icon><Promotion /></el-icon>
          导出发布
        </el-button>
      </div>
    </header>

    <main class="workspace-grid">
      <aside class="left-rail">
        <el-button type="primary" class="new-task-button" @click="resetEditForm">
          <el-icon><Plus /></el-icon>
          新建视频任务
        </el-button>

        <section class="panel-section">
          <div class="section-head">
            <h2>素材库</h2>
            <button class="plain-action" @click="fetchMaterials">全部素材</button>
          </div>

          <div class="asset-stats">
            <span><el-icon><VideoPlay /></el-icon> 视频 {{ videoMaterials.length }}</span>
            <span><el-icon><Picture /></el-icon> 图片 {{ imageCount }}</span>
            <span><el-icon><Headset /></el-icon> 音频 {{ audioCount }}</span>
            <span><el-icon><Tickets /></el-icon> 字幕 {{ subtitleCount }}</span>
          </div>

          <el-input
            v-model="searchKeyword"
            placeholder="搜索视频素材"
            clearable
            class="material-search"
          />

          <div class="material-grid">
            <button
              v-for="material in filteredVideoMaterials"
              :key="material.id || material.file_path"
              class="material-card"
              :class="{ selected: selectedMaterial?.file_path === material.file_path }"
              @click="selectMaterial(material)"
            >
              <div class="material-thumb">
                <video muted preload="metadata">
                  <source :src="getPreviewUrl(material.file_path)" type="video/mp4">
                </video>
                <span class="duration-pill">{{ inferDuration(material) }}</span>
              </div>
              <strong>{{ material.filename }}</strong>
              <small>{{ material.upload_time || '未记录时间' }}</small>
              <em>{{ material.recognized ? '已识别字幕' : '待内容识别' }}</em>
            </button>
          </div>

          <el-empty v-if="!isRefreshing && filteredVideoMaterials.length === 0" description="暂无视频素材" :image-size="72" />
        </section>

        <section class="panel-section history-section">
          <div class="section-head">
            <h2>历史任务</h2>
            <button class="plain-action" @click="fetchTasks">刷新任务</button>
          </div>

          <div class="task-tabs">
            <button
              v-for="tab in taskTabs"
              :key="tab.value"
              :class="{ active: taskFilter === tab.value }"
              @click="taskFilter = tab.value"
            >
              {{ tab.label }}
            </button>
          </div>

          <div class="history-list" v-loading="tasksLoading">
            <button
              v-for="task in filteredTasks"
              :key="task.id"
              class="history-card"
              @click="task.output_files?.length && previewOutput(task.output_files[0])"
            >
              <div class="history-thumb">
                <el-icon><Film /></el-icon>
              </div>
              <div class="history-info">
                <strong>{{ getTaskTitle(task) }}</strong>
                <span>{{ getTaskMeta(task) }}</span>
                <small>{{ task.created_at || '-' }}</small>
              </div>
              <el-tag :type="getTaskStatusType(task.status)" effect="dark" round>
                {{ getTaskStatusName(task.status) }}
              </el-tag>
            </button>
          </div>
        </section>
      </aside>

      <section class="center-stage">
        <div class="player-panel">
          <div class="player-head">
            <strong>{{ selectedMaterial?.filename || '请选择一个视频素材' }}</strong>
            <div class="ratio-group">
              <button
                v-for="ratio in ratioOptions"
                :key="ratio.value"
                :class="{ active: editForm.aspectRatio === ratio.value }"
                @click="editForm.aspectRatio = ratio.value"
              >
                <el-icon><component :is="ratio.icon" /></el-icon>
                {{ ratio.label }}
              </button>
              <button class="fit-button">适应</button>
              <button class="icon-button" title="全屏预览">
                <el-icon><FullScreen /></el-icon>
              </button>
            </div>
          </div>

          <div class="preview-shell" :class="`ratio-${editForm.aspectRatio.replace(':', '-')}`">
            <video
              ref="videoRef"
              class="main-video"
              controls
              :src="selectedMaterial ? getPreviewUrl(selectedMaterial.file_path) : ''"
              @loadedmetadata="syncVideoMeta"
              @timeupdate="syncCurrentTime"
            />
            <div class="subtitle-overlay">{{ activeSubtitle }}</div>
          </div>

          <div class="playbar">
            <span>{{ formatTime(currentTime) }} / {{ formatTime(videoDuration) }}</span>
            <div class="transport">
              <button title="上一段"><el-icon><DArrowLeft /></el-icon></button>
              <button class="play-button" title="播放" @click="togglePlay">
                <el-icon><VideoPlay /></el-icon>
              </button>
              <button title="下一段"><el-icon><DArrowRight /></el-icon></button>
            </div>
            <div class="play-tools">
              <button title="音量"><el-icon><Mute /></el-icon></button>
              <span>1.0x</span>
              <button title="画中画"><el-icon><Monitor /></el-icon></button>
              <button title="全屏"><el-icon><FullScreen /></el-icon></button>
            </div>
          </div>
        </div>

        <div class="timeline-panel">
          <div class="marker-legend">
            <span v-for="marker in markerLegend" :key="marker.label">
              <i :style="{ background: marker.color }"></i>{{ marker.label }}
            </span>
          </div>

          <div class="timeline-ruler">
            <span v-for="tick in timelineTicks" :key="tick">{{ tick }}</span>
          </div>

          <div class="timeline-body">
            <div class="track-labels">
              <span><el-icon><Film /></el-icon> 视频轨道</span>
              <span><el-icon><Tickets /></el-icon> 字幕轨道</span>
              <span><el-icon><Headset /></el-icon> 音频轨道</span>
              <span><el-icon><CollectionTag /></el-icon> 贴纸/标题</span>
            </div>

            <div class="tracks">
              <div class="playhead" :style="{ left: playheadLeft }">
                <span></span>
              </div>

              <div class="track video-track">
                <span v-for="item in videoBlocks" :key="item" class="clip-block"></span>
              </div>
              <div class="track caption-track">
                <span v-for="caption in subtitleBlocks" :key="caption.text">{{ caption.text }}</span>
              </div>
              <div class="track audio-track">
                <i v-for="bar in waveformBars" :key="bar" :style="{ height: `${bar}%` }"></i>
              </div>
              <div class="track title-track">
                <span v-for="tag in titleBlocks" :key="tag.text" :class="tag.type">{{ tag.text }}</span>
              </div>
            </div>
          </div>

          <div class="edit-toolbar">
            <button v-for="tool in editTools" :key="tool.label" :disabled="tool.disabled">
              <el-icon><component :is="tool.icon" /></el-icon>
              {{ tool.label }}
            </button>
          </div>
        </div>

        <footer class="output-bar">
          <span>视频时长：{{ formatTime(videoDuration || estimatedDuration) }}</span>
          <span>预计导出时长：00:00:30</span>
          <span>预计大小：{{ estimatedSize }}</span>
          <el-button type="primary" @click="submitTalkingEdit" :disabled="!selectedMaterial" :loading="isEditing">
            <el-icon><MagicStick /></el-icon>
            AI 自动优化
          </el-button>
        </footer>
      </section>

      <aside class="right-rail">
        <div class="assistant-head">
          <div>
            <h2>AI 剪辑助手</h2>
            <p>识别内容结构，推荐可剪片段</p>
          </div>
          <el-button text @click="fetchAll">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>

        <div class="assistant-tabs">
          <button
            v-for="tab in assistantTabs"
            :key="tab.value"
            :class="{ active: assistantTab === tab.value }"
            @click="assistantTab = tab.value"
          >
            {{ tab.label }}
          </button>
        </div>

        <section class="ai-card">
          <h3>视频摘要</h3>
          <p>{{ aiSummary }}</p>
        </section>

        <section class="ai-card">
          <h3>核心观点</h3>
          <ul class="point-list">
            <li v-for="point in aiPoints" :key="point">
              <el-icon><CircleCheck /></el-icon>
              {{ point }}
            </li>
          </ul>
        </section>

        <section class="ai-card clip-card">
          <div class="card-title-row">
            <h3>可剪片段推荐</h3>
            <el-button size="small" text @click="activeStep = 2">重新分析</el-button>
          </div>

          <div class="clip-list">
            <div v-for="clip in recommendedClips" :key="clip.title" class="clip-row">
              <div>
                <strong :class="clip.type">{{ clip.title }}</strong>
                <span>{{ clip.time }}</span>
              </div>
              <p>{{ clip.reason }}</p>
              <button title="加入时间线" @click="applyClip(clip)">
                <el-icon><Plus /></el-icon>
              </button>
            </div>
          </div>
        </section>

        <section class="ai-card export-card">
          <el-form label-position="top">
            <el-form-item label="顶部标题">
              <el-input v-model="editForm.title" placeholder="例如：AI 不是替代人，而是放大内容能力" />
            </el-form-item>
            <el-form-item label="输出文件名">
              <el-input v-model="editForm.outputName" placeholder="例如：AI内容系统介绍_剪辑版.mp4" />
            </el-form-item>
            <el-form-item label="剪辑区间">
              <div class="time-inputs">
                <el-input v-model="editForm.startTime" placeholder="开始 00:00:05" />
                <el-input v-model="editForm.endTime" placeholder="结束 00:00:35" />
              </div>
            </el-form-item>
          </el-form>

          <el-button type="primary" class="generate-button" @click="submitTalkingEdit" :disabled="!selectedMaterial" :loading="isEditing">
            一键生成剪辑版本
          </el-button>
          <p>将基于推荐片段，自动生成可发布版本并加入素材库。</p>
        </section>
      </aside>
    </main>

    <el-dialog v-model="outputPreviewVisible" title="剪辑结果预览" width="68%" top="6vh">
      <div v-if="previewOutputFile" class="output-preview">
        <video controls class="dialog-video">
          <source :src="getPreviewUrl(previewOutputFile)" type="video/mp4">
        </video>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, markRaw, onMounted, reactive, ref } from 'vue'
import {
  ArrowRight,
  Check,
  CircleCheck,
  CollectionTag,
  Crop,
  DArrowLeft,
  DArrowRight,
  Delete,
  Film,
  FullScreen,
  Headset,
  MagicStick,
  Monitor,
  Mute,
  Picture,
  Plus,
  Promotion,
  Refresh,
  Scissor,
  Tickets,
  VideoCamera,
  VideoPlay,
  ZoomIn
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { materialApi } from '@/api/material'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const searchKeyword = ref('')
const selectedMaterial = ref(null)
const isRefreshing = ref(false)
const isEditing = ref(false)
const tasksLoading = ref(false)
const videoTasks = ref([])
const outputPreviewVisible = ref(false)
const previewOutputFile = ref('')
const assistantTab = ref('analysis')
const taskFilter = ref('all')
const activeStep = ref(1)
const videoRef = ref(null)
const videoDuration = ref(225)
const currentTime = ref(84)

const editForm = reactive({
  startTime: '00:00:05',
  endTime: '00:00:35',
  aspectRatio: '9:16',
  title: 'AI 不是替代人，而是放大内容能力',
  outputName: ''
})

const workflowSteps = [
  { name: '上传素材' },
  { name: '内容识别' },
  { name: '智能剪辑' },
  { name: '字幕封面' },
  { name: '导出发布' }
]

const assistantTabs = [
  { label: '智能拆解', value: 'analysis' },
  { label: '智能剪辑', value: 'edit' },
  { label: '字幕口播', value: 'subtitle' },
  { label: '封面标题', value: 'cover' },
  { label: '导出发布', value: 'export' }
]

const taskTabs = [
  { label: '全部', value: 'all' },
  { label: '处理中', value: 'running' },
  { label: '已完成', value: 'success' },
  { label: '失败', value: 'failed' }
]

const ratioOptions = [
  { label: '9:16', value: '9:16', icon: markRaw(Monitor) },
  { label: '16:9', value: '16:9', icon: markRaw(Monitor) },
  { label: '1:1', value: '1:1', icon: markRaw(Crop) },
  { label: '原始', value: 'original', icon: markRaw(FullScreen) }
]

const markerLegend = [
  { label: '爆点', color: '#7c5cff' },
  { label: '金句', color: '#f5a623' },
  { label: '转折', color: '#ffc233' },
  { label: '情绪峰值', color: '#9b6cff' },
  { label: '可剪片段', color: '#24d6a3' },
  { label: '废话片段', color: '#ff4d6d' }
]

const timelineTicks = ['00:00', '00:30', '01:00', '01:30', '02:00', '02:30', '03:00', '03:45']
const videoBlocks = Array.from({ length: 12 }, (_, index) => index)
const waveformBars = [42, 58, 68, 46, 72, 55, 63, 49, 80, 67, 38, 60, 73, 44, 57, 76, 52, 68, 48, 64, 71, 45, 61, 54, 78, 66, 41, 59, 70, 50]

const subtitleBlocks = [
  { text: 'AI 不是替代人' },
  { text: '而是放大内容能力' },
  { text: '内容创作流程' },
  { text: '形成稳定系统' },
  { text: '21 天搭建' }
]

const titleBlocks = [
  { text: '重点来了', type: 'hot' },
  { text: '核心观点', type: 'core' },
  { text: '记住这句话', type: 'quote' },
  { text: '总结一下', type: 'summary' }
]

const editTools = [
  { label: '分割', icon: markRaw(Scissor) },
  { label: '删除', icon: markRaw(Delete) },
  { label: '裁剪', icon: markRaw(Crop) },
  { label: '变速', icon: markRaw(Refresh) },
  { label: '音量', icon: markRaw(Mute) },
  { label: '滤镜', icon: markRaw(MagicStick) },
  { label: '转场', icon: markRaw(CollectionTag) },
  { label: '美颜', icon: markRaw(ZoomIn) },
  { label: '画中画', icon: markRaw(Monitor) }
]

const isVideoFile = (filename = '') => ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv'].some(ext => filename.toLowerCase().endsWith(ext))
const isImageFile = (filename = '') => ['.jpg', '.jpeg', '.png', '.webp', '.gif'].some(ext => filename.toLowerCase().endsWith(ext))
const isAudioFile = (filename = '') => ['.mp3', '.wav', '.m4a', '.aac'].some(ext => filename.toLowerCase().endsWith(ext))
const isSubtitleFile = (filename = '') => ['.srt', '.vtt', '.ass'].some(ext => filename.toLowerCase().endsWith(ext))

const videoMaterials = computed(() => appStore.materials.filter(material => isVideoFile(material.filename)))
const imageCount = computed(() => appStore.materials.filter(material => isImageFile(material.filename)).length)
const audioCount = computed(() => appStore.materials.filter(material => isAudioFile(material.filename)).length)
const subtitleCount = computed(() => appStore.materials.filter(material => isSubtitleFile(material.filename)).length)

const filteredVideoMaterials = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  return videoMaterials.value.filter(material => !keyword || material.filename.toLowerCase().includes(keyword))
})

const filteredTasks = computed(() => {
  if (taskFilter.value === 'all') return videoTasks.value.slice(0, 8)
  return videoTasks.value.filter(task => task.status === taskFilter.value).slice(0, 8)
})

const estimatedDuration = computed(() => Math.max(videoDuration.value || 0, 225))
const estimatedSize = computed(() => {
  const base = selectedMaterial.value?.filesize || 68
  return `${Math.max(8, Math.round(base * 0.48))}MB`
})

const playheadLeft = computed(() => {
  const duration = videoDuration.value || 225
  return `${Math.min(100, Math.max(0, (currentTime.value / duration) * 100))}%`
})

const activeSubtitle = computed(() => {
  if (currentTime.value < 40) return 'AI 不是要替代我们，而是要放大我们的内容能力'
  if (currentTime.value < 100) return '把选题、脚本、素材和发布流程变成一条生产线'
  return '持续输出优质内容，才是建立信任的关键'
})

const aiSummary = computed(() => {
  const name = selectedMaterial.value?.filename || '当前视频'
  return `${name} 适合拆成知识分享短视频：先用痛点开场，再讲核心方法，最后给出行动建议。当前版本建议优先输出 30 秒竖屏剪辑。`
})

const aiPoints = computed(() => [
  '内容系统比单个工具更重要',
  'AI 适合承担识别、拆解、剪辑和复用',
  '口播内容要突出开头钩子和中段金句',
  '短视频版本应该服务于引流和信任建立'
])

const recommendedClips = computed(() => [
  { title: '开场痛点', time: '00:05 - 00:22', reason: '适合做短视频开头', type: 'hot', start: '00:00:05', end: '00:00:22' },
  { title: '核心观点', time: '01:10 - 01:45', reason: '信息密度高，金句多', type: 'core', start: '00:01:10', end: '00:01:45' },
  { title: '案例分享', time: '02:10 - 02:50', reason: '案例具体，有说服力', type: 'case', start: '00:02:10', end: '00:02:50' },
  { title: '方法总结', time: '03:00 - 03:20', reason: '适合知识卡片', type: 'summary', start: '00:03:00', end: '00:03:20' },
  { title: '结尾转化', time: '03:20 - 03:45', reason: '适合引导报名/关注', type: 'hot', start: '00:03:20', end: '00:03:45' }
])

const getPreviewUrl = (filePath) => {
  const filename = String(filePath || '').split('/').pop()
  return materialApi.getMaterialPreviewUrl(filename)
}

const inferDuration = (material) => {
  if (material.duration) return material.duration
  if (material.filesize && Number(material.filesize) > 80) return '03:45'
  if (material.filesize && Number(material.filesize) > 30) return '01:20'
  return '00:45'
}

const selectMaterial = (material) => {
  if (!material) return
  selectedMaterial.value = material
  editForm.startTime = '00:00:05'
  editForm.endTime = '00:00:35'
  editForm.aspectRatio = '9:16'
  editForm.title = 'AI 不是替代人，而是放大内容能力'
  editForm.outputName = `${material.filename.replace(/\.[^.]+$/, '')}_AI剪辑版.mp4`
  activeStep.value = 1
}

const resetEditForm = () => {
  if (selectedMaterial.value) {
    selectMaterial(selectedMaterial.value)
  }
}

const fetchMaterials = async () => {
  isRefreshing.value = true
  try {
    const response = await materialApi.getAllMaterials()
    if (response.code === 200) {
      appStore.setMaterials(response.data || [])
      if (!selectedMaterial.value && filteredVideoMaterials.value.length > 0) {
        selectMaterial(filteredVideoMaterials.value[0])
      }
    } else {
      ElMessage.error(response.msg || '获取素材失败')
    }
  } catch (error) {
    console.error('获取素材失败:', error)
    ElMessage.error('获取素材失败')
  } finally {
    isRefreshing.value = false
  }
}

const fetchTasks = async () => {
  tasksLoading.value = true
  try {
    const response = await materialApi.getVideoTasks()
    if (response.code === 200) {
      videoTasks.value = response.data || []
    } else {
      ElMessage.error(response.msg || '获取任务记录失败')
    }
  } catch (error) {
    console.error('获取任务记录失败:', error)
    ElMessage.error('获取任务记录失败')
  } finally {
    tasksLoading.value = false
  }
}

const fetchAll = async () => {
  await Promise.all([fetchMaterials(), fetchTasks()])
}

const submitTalkingEdit = async () => {
  if (!selectedMaterial.value) {
    ElMessage.warning('请选择要剪辑的视频素材')
    return
  }

  activeStep.value = 2
  isEditing.value = true
  try {
    const response = await materialApi.talkingEdit({
      file: selectedMaterial.value.file_path,
      options: {
        startTime: editForm.startTime.trim(),
        endTime: editForm.endTime.trim(),
        aspectRatio: editForm.aspectRatio,
        title: editForm.title.trim(),
        outputName: editForm.outputName.trim()
      }
    })

    if (response.code === 200) {
      activeStep.value = 4
      ElMessage.success('剪辑完成，已加入素材库')
      await fetchAll()
      const output = response.data?.output?.filepath
      if (output) {
        previewOutput(output)
      }
    } else {
      ElMessage.error(response.msg || '剪辑失败')
    }
  } catch (error) {
    console.error('剪辑失败:', error)
    ElMessage.error('剪辑失败: ' + (error.message || '未知错误'))
    await fetchTasks()
  } finally {
    isEditing.value = false
  }
}

const previewOutput = (filePath) => {
  previewOutputFile.value = filePath
  outputPreviewVisible.value = true
}

const applyClip = (clip) => {
  editForm.startTime = clip.start
  editForm.endTime = clip.end
  activeStep.value = 2
  ElMessage.success(`已应用推荐片段：${clip.title}`)
}

const togglePlay = () => {
  const video = videoRef.value
  if (!video) return
  if (video.paused) {
    video.play()
  } else {
    video.pause()
  }
}

const syncVideoMeta = () => {
  if (videoRef.value?.duration && Number.isFinite(videoRef.value.duration)) {
    videoDuration.value = Math.round(videoRef.value.duration)
  }
}

const syncCurrentTime = () => {
  if (videoRef.value?.currentTime !== undefined) {
    currentTime.value = Math.round(videoRef.value.currentTime)
  }
}

const formatTime = (seconds) => {
  const total = Math.max(0, Math.round(Number(seconds) || 0))
  const minutes = String(Math.floor(total / 60)).padStart(2, '0')
  const rest = String(total % 60).padStart(2, '0')
  return `${minutes}:${rest}`
}

const getTaskTitle = (task) => {
  const output = task.output_files?.[0]
  const input = task.input_files?.[0]
  return output || input || `剪辑任务 #${task.id}`
}

const getTaskMeta = (task) => {
  if (task.status === 'success') return '9:16 | 30秒 | 1个版本'
  if (task.status === 'failed') return task.error_message || '生成失败'
  return '处理中 | AI 剪辑中'
}

const getTaskStatusName = (status) => {
  const map = {
    success: '已完成',
    failed: '失败',
    pending: '待确认',
    running: '处理中'
  }
  return map[status] || status || '-'
}

const getTaskStatusType = (status) => {
  const map = {
    success: 'success',
    failed: 'danger',
    pending: 'warning',
    running: 'primary'
  }
  return map[status] || 'info'
}

onMounted(() => {
  fetchAll()
})
</script>

<style lang="scss" scoped>
.video-edit-workspace {
  min-height: calc(100vh - 60px);
  margin: -20px;
  padding: 18px;
  color: #edf3ff;
  background:
    radial-gradient(circle at 18% 0%, rgba(95, 84, 255, 0.2), transparent 30%),
    linear-gradient(135deg, #101624 0%, #111827 48%, #17131f 100%);
}

.workspace-topbar,
.left-rail,
.center-stage,
.right-rail,
.player-panel,
.timeline-panel,
.output-bar,
.panel-section,
.ai-card {
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(17, 24, 39, 0.78);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.24);
}

.workspace-topbar {
  display: grid;
  grid-template-columns: 330px minmax(520px, 1fr) 230px;
  align-items: center;
  gap: 18px;
  min-height: 74px;
  padding: 0 18px;
  border-radius: 8px;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 12px;

  h1 {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
  }

  p {
    margin: 4px 0 0;
    color: #9ca9bf;
    font-size: 12px;
  }
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: linear-gradient(135deg, #4d7dff, #8b5cf6);
  font-size: 22px;
}

.workflow-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-width: 0;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #7d8aa0;
  font-size: 13px;
  white-space: nowrap;

  &.done,
  &.active {
    color: #f8fbff;
  }

  &.active .step-index,
  &.done .step-index {
    background: linear-gradient(135deg, #4d7dff, #8b5cf6);
    color: #fff;
  }
}

.step-index {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #293244;
  color: #aab5c8;
  font-weight: 700;
}

.step-arrow {
  color: #4b5565;
}

.top-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 310px minmax(560px, 1fr) 360px;
  gap: 14px;
  margin-top: 14px;
}

.left-rail,
.right-rail {
  min-height: calc(100vh - 168px);
  border-radius: 8px;
  padding: 14px;
}

.left-rail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.new-task-button,
.generate-button {
  width: 100%;
  min-height: 44px;
  border: 0;
  background: linear-gradient(135deg, #4f7cff, #8a4dff);
  font-weight: 700;
}

.panel-section,
.ai-card {
  border-radius: 8px;
  padding: 12px;
}

.section-head,
.card-title-row,
.assistant-head,
.player-head,
.playbar,
.output-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-head h2,
.assistant-head h2,
.ai-card h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}

.assistant-head p,
.ai-card p {
  margin: 6px 0 0;
  color: #aeb8ca;
  line-height: 1.7;
  font-size: 13px;
}

.plain-action {
  border: 0;
  background: transparent;
  color: #aab5c8;
  cursor: pointer;
}

.asset-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 12px 0;
  color: #c7d2e5;
  font-size: 12px;

  span {
    display: flex;
    align-items: center;
    gap: 6px;
  }
}

.material-search {
  margin-bottom: 12px;
}

.material-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  max-height: 315px;
  overflow: auto;
  padding-right: 2px;
}

.material-card,
.history-card,
.clip-row button,
.ratio-group button,
.transport button,
.play-tools button,
.edit-toolbar button,
.task-tabs button,
.assistant-tabs button {
  border: 0;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.material-card {
  min-width: 0;
  padding: 7px;
  text-align: left;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.76);
  border: 1px solid transparent;

  &.selected {
    border-color: #5b7cff;
    box-shadow: inset 0 0 0 1px rgba(91, 124, 255, 0.25);
  }

  strong,
  small,
  em {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    margin-top: 7px;
    font-size: 12px;
  }

  small {
    margin-top: 4px;
    color: #8592a7;
    font-size: 11px;
  }

  em {
    margin-top: 5px;
    color: #22c55e;
    font-style: normal;
    font-size: 11px;
  }
}

.material-thumb {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border-radius: 6px;
  background: #020617;

  video {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.duration-pill {
  position: absolute;
  left: 6px;
  bottom: 6px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.82);
  color: #fff;
  font-size: 11px;
}

.history-section {
  flex: 1;
  min-height: 260px;
}

.task-tabs,
.assistant-tabs {
  display: flex;
  gap: 6px;
  margin: 12px 0;
  overflow-x: auto;

  button {
    flex: 0 0 auto;
    padding: 7px 10px;
    border-radius: 7px;
    background: rgba(30, 41, 59, 0.9);
    color: #aeb8ca;
    font-size: 12px;

    &.active {
      color: #fff;
      background: rgba(91, 124, 255, 0.35);
    }
  }
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  max-height: 360px;
  overflow: auto;
}

.history-card {
  display: grid;
  grid-template-columns: 48px 1fr auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 9px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.72);
  text-align: left;
}

.history-thumb {
  display: grid;
  place-items: center;
  width: 48px;
  height: 36px;
  border-radius: 6px;
  background: linear-gradient(135deg, #1d4ed8, #6d28d9);
}

.history-info {
  min-width: 0;

  strong,
  span,
  small {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    font-size: 12px;
  }

  span,
  small {
    color: #8f9aad;
    font-size: 11px;
  }
}

.center-stage {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  background: transparent;
  border: 0;
  box-shadow: none;
}

.player-panel,
.timeline-panel,
.output-bar {
  border-radius: 8px;
  padding: 12px;
}

.player-head strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
}

.ratio-group,
.transport,
.play-tools,
.edit-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ratio-group button,
.transport button,
.play-tools button,
.edit-toolbar button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-height: 32px;
  padding: 0 10px;
  border-radius: 7px;
  background: rgba(30, 41, 59, 0.86);
  color: #aeb8ca;
  font-size: 12px;

  &.active {
    color: #fff;
    background: rgba(91, 124, 255, 0.35);
    box-shadow: inset 0 0 0 1px #6d7dff;
  }
}

.icon-button {
  width: 34px;
  padding: 0 !important;
}

.fit-button {
  min-width: 54px;
}

.preview-shell {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 410px;
  margin-top: 12px;
  overflow: hidden;
  border-radius: 8px;
  background:
    linear-gradient(rgba(15, 23, 42, 0.28), rgba(15, 23, 42, 0.28)),
    #030712;
}

.main-video {
  width: 100%;
  height: 100%;
  max-height: 560px;
  object-fit: contain;
  background: #000;
}

.ratio-9-16 .main-video {
  max-width: 44%;
}

.ratio-1-1 .main-video {
  max-width: 64%;
}

.subtitle-overlay {
  position: absolute;
  left: 50%;
  bottom: 24px;
  max-width: 78%;
  transform: translateX(-50%);
  padding: 8px 16px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.58);
  color: #fff;
  font-size: 16px;
  text-align: center;
}

.playbar {
  margin-top: 10px;
  color: #b8c3d6;
  font-size: 12px;
}

.play-button {
  width: 38px;
  height: 34px;
  color: #fff !important;
  background: linear-gradient(135deg, #4d7dff, #8b5cf6) !important;
}

.marker-legend {
  display: flex;
  justify-content: center;
  gap: 22px;
  margin: 4px 0 18px;
  color: #b7c1d4;
  font-size: 12px;

  span {
    display: flex;
    align-items: center;
    gap: 7px;
  }

  i {
    width: 9px;
    height: 9px;
    transform: rotate(45deg);
  }
}

.timeline-ruler {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  padding-left: 102px;
  margin-bottom: 8px;
  color: #7d879a;
  font-size: 12px;
}

.timeline-body {
  display: grid;
  grid-template-columns: 100px 1fr;
  min-height: 210px;
}

.track-labels {
  display: grid;
  grid-template-rows: repeat(4, 1fr);
  color: #aab5c8;
  font-size: 12px;

  span {
    display: flex;
    align-items: center;
    gap: 6px;
  }
}

.tracks {
  position: relative;
  display: grid;
  grid-template-rows: repeat(4, 1fr);
  gap: 12px;
  padding-left: 6px;
  border-left: 1px solid rgba(148, 163, 184, 0.12);
}

.track {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  border-radius: 7px;
}

.video-track .clip-block {
  flex: 1;
  height: 34px;
  border-radius: 5px;
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.5), rgba(168, 85, 247, 0.42)),
    #263247;
  border: 1px solid rgba(147, 197, 253, 0.2);
}

.caption-track span {
  flex: 1;
  min-width: 70px;
  padding: 8px 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-radius: 5px;
  background: rgba(79, 124, 255, 0.28);
  border: 1px solid rgba(96, 165, 250, 0.32);
  font-size: 12px;
}

.audio-track {
  align-items: flex-end;
  gap: 3px;
  padding: 6px;
  background: rgba(16, 185, 129, 0.16);

  i {
    flex: 1;
    min-width: 3px;
    border-radius: 8px 8px 0 0;
    background: linear-gradient(180deg, #2dd4bf, #059669);
  }
}

.title-track span {
  min-width: 108px;
  padding: 8px 12px;
  border-radius: 5px;
  color: #ffdca8;
  background: rgba(245, 158, 11, 0.2);
  border: 1px solid rgba(245, 158, 11, 0.45);
  font-size: 12px;
  text-align: center;
}

.playhead {
  position: absolute;
  top: -28px;
  bottom: -2px;
  z-index: 3;
  width: 2px;
  background: #f8fafc;

  span {
    position: absolute;
    top: -8px;
    left: 50%;
    width: 13px;
    height: 13px;
    transform: translateX(-50%);
    border-radius: 50%;
    background: #fff;
  }
}

.edit-toolbar {
  justify-content: space-around;
  padding-top: 14px;
  margin-top: 14px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);

  button {
    flex-direction: column;
    min-width: 58px;
    min-height: 50px;
    background: transparent;
  }
}

.output-bar {
  min-height: 60px;
  color: #aab5c8;
  font-size: 13px;
}

.right-rail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.point-list {
  display: grid;
  gap: 10px;
  padding: 0;
  margin: 12px 0 0;
  list-style: none;

  li {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #c8d2e4;
    font-size: 13px;
  }

  .el-icon {
    color: #8fa3ff;
  }
}

.clip-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.clip-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 12px;
  align-items: center;
  padding: 10px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.72);

  div {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  strong {
    font-size: 13px;
  }

  strong.hot {
    color: #f59e0b;
  }

  strong.core,
  strong.case,
  strong.summary {
    color: #34d399;
  }

  span,
  p {
    color: #aab5c8;
    font-size: 12px;
  }

  p {
    grid-column: 1 / 2;
    margin: 0;
  }

  button {
    grid-column: 2;
    grid-row: 1 / 3;
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: linear-gradient(135deg, #4d7dff, #8b5cf6);
    color: #fff;
  }
}

.export-card {
  margin-top: auto;
}

.time-inputs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.generate-button {
  margin-top: 2px;
}

.dialog-video {
  width: 100%;
  max-height: 70vh;
  background: #000;
  border-radius: 8px;
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: rgba(15, 23, 42, 0.86);
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.18) inset;
}

:deep(.el-input__inner) {
  color: #edf3ff;
}

:deep(.el-form-item__label) {
  color: #c8d2e4;
}

@media (max-width: 1280px) {
  .workspace-grid {
    grid-template-columns: 280px minmax(520px, 1fr);
  }

  .right-rail {
    grid-column: 1 / -1;
    min-height: auto;
  }

  .workspace-topbar {
    grid-template-columns: 1fr;
    align-items: flex-start;
    padding: 16px;
  }

  .workflow-steps {
    justify-content: flex-start;
    overflow-x: auto;
  }
}
</style>
