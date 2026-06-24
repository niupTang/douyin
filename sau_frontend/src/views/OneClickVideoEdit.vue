<template>
  <div class="one-click-page">
    <aside class="rail">
      <div class="rail-logo">
        <div class="logo-shape"></div>
      </div>
      <button v-for="item in railItems" :key="item.label" :class="{ active: item.active }">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </button>
    </aside>

    <main class="one-click-main">
      <header class="hero-bar">
        <div>
          <p>AI 视频剪辑工作台</p>
          <h1>从真实素材提取文案，再生成二创剪辑成片</h1>
        </div>
        <div class="hero-actions">
          <el-button type="primary" @click="runWorkflow" :loading="isRunning">
            <el-icon><MagicStick /></el-icon>
            开始二创剪辑
          </el-button>
          <el-button>
            <el-icon><EditPen /></el-icon>
            保存为 Skill
          </el-button>
          <el-button :disabled="!outputFile" @click="downloadOutput">
            <el-icon><Download /></el-icon>
            导出视频
          </el-button>
        </div>
      </header>

      <section class="workspace">
        <section class="input-panel">
          <div class="panel-title">
            <el-icon><Edit /></el-icon>
            <h2>任务输入</h2>
          </div>

          <label class="field-label">主题 / 目标视频</label>
          <el-input
            v-model="topic"
            type="textarea"
            :rows="4"
            resize="none"
            placeholder="输入目标：比如剪出一个知识口播视频，使用云泽大叔的 TTS"
          />

          <label class="field-label">参考内容导入</label>
          <div class="import-grid">
            <button v-for="action in importActions" :key="action.label" @click="activeStage = action.stage">
              <el-icon><component :is="action.icon" /></el-icon>
              <strong>{{ action.label }}</strong>
              <span>{{ action.desc }}</span>
            </button>
          </div>

          <div class="asr-card">
            <div class="mini-head">
              <span>ASR 口播识别</span>
              <el-button size="small" text @click="loadMaterials">刷新素材</el-button>
            </div>
            <div class="asr-row">
              <el-select v-model="selectedSourceFile" filterable placeholder="选择一个视频素材">
                <el-option
                  v-for="material in videoMaterials"
                  :key="material.file_path"
                  :label="material.filename"
                  :value="material.file_path"
                />
              </el-select>
              <el-button type="primary" :loading="isAsrRunning" :disabled="!selectedSourceFile" @click="runAsr">
                ASR 提取文案
              </el-button>
            </div>
            <el-input
              v-model="asrTranscript"
              type="textarea"
              :rows="5"
              resize="none"
              placeholder="识别后的视频口播原文会出现在这里，并作为一键剪辑的参考文案。"
            />
            <el-button
              type="primary"
              class="rewrite-clip-button"
              :loading="isRunning"
              @click="runWorkflow"
            >
              <el-icon><MagicStick /></el-icon>
              开始二创剪辑
            </el-button>
          </div>

          <div class="material-bin">
            <div class="mini-head">
              <span>剪辑素材</span>
              <small>{{ videoMaterials.length }} 个视频素材</small>
            </div>
            <div class="material-list">
              <button
                v-for="material in videoMaterials.slice(0, 5)"
                :key="material.file_path"
                :class="{ active: selectedSourceFile === material.file_path }"
                @click="selectedSourceFile = material.file_path"
              >
                <span class="material-icon">
                  <el-icon><Film /></el-icon>
                </span>
                <strong>{{ material.filename }}</strong>
                <em>{{ material.filesize || 0 }}MB</em>
              </button>
            </div>
          </div>

          <div class="rules-card">
            <div class="mini-head">
              <span>二创规则</span>
              <el-icon><Close /></el-icon>
            </div>
            <ol>
              <li v-for="rule in rewriteRules" :key="rule">{{ rule }}</li>
            </ol>
          </div>

          <div class="voice-card">
            <div class="panel-title small">
              <el-icon><Microphone /></el-icon>
              <h3>TTS 配音</h3>
            </div>
            <div class="voice-row">
              <span>音色</span>
              <el-select v-model="voiceForm.voice">
                <el-option label="云泽大叔 TTS（成熟稳重）" value="x4_lingbosong" />
                <el-option label="知识分享女声" value="knowledge_female" />
              </el-select>
            </div>
            <div class="voice-row">
              <span>语速</span>
              <el-slider v-model="voiceForm.speed" :min="0.8" :max="1.3" :step="0.05" />
              <b>{{ voiceForm.speed.toFixed(2) }}x</b>
            </div>
            <div class="voice-row">
              <span>情绪</span>
              <el-select v-model="voiceForm.mood">
                <el-option label="自信、亲和、专业" value="professional" />
                <el-option label="兴奋、有冲击力" value="energetic" />
              </el-select>
            </div>
            <div class="voice-row">
              <span>背景音乐</span>
              <el-select v-model="voiceForm.music">
                <el-option label="科技感轻音乐（默认）" value="tech" />
                <el-option label="无背景音乐" value="none" />
              </el-select>
            </div>
          </div>
        </section>

        <section class="loop-panel">
          <div class="loop-head">
            <div class="panel-title">
              <el-icon><Refresh /></el-icon>
              <h2>Loop 工作流</h2>
            </div>
            <span>基于 Loop Engineering</span>
          </div>

          <div class="loop-list">
            <div
              v-for="stage in stages"
              :key="stage.key"
              class="loop-item"
              :class="{ active: activeStage === stage.key, done: stage.status === 'done' }"
            >
              <div class="stage-icon">
                <el-icon><component :is="stage.icon" /></el-icon>
              </div>
              <div>
                <strong>{{ stage.title }}</strong>
                <p>{{ stage.desc }}</p>
              </div>
              <em>{{ stageStatusText(stage) }}</em>
            </div>
          </div>

          <div class="script-card">
            <div class="section-line">
              <h3>原文生成</h3>
              <button @click="generateScript">重新生成</button>
            </div>
            <div class="script-grid">
              <article v-for="block in scriptBlocks" :key="block.title">
                <span>{{ block.title }}</span>
                <p>{{ block.text }}</p>
              </article>
              <el-empty v-if="scriptBlocks.length === 0" description="暂无二创文案，先提取文案或开始二创剪辑" :image-size="72" />
            </div>
          </div>

          <div class="storyboard">
            <div class="section-line">
              <h3>分镜时间线 Storyboard</h3>
              <div>
                <button class="active">列表视图</button>
                <button>时间轴视图</button>
              </div>
            </div>
            <div class="shot-row">
              <article v-for="shot in storyboard" :key="shot.title" class="shot-card">
                <div class="shot-cover" :class="shot.theme">
                  <el-icon><component :is="shot.icon" /></el-icon>
                </div>
                <strong>{{ shot.title }}</strong>
                <p>{{ shot.copy }}</p>
                <span>{{ shot.duration }}</span>
              </article>
              <button class="add-shot">
                <el-icon><Plus /></el-icon>
                添加镜头
              </button>
            </div>
          </div>

          <div class="editor-board">
            <div class="section-line">
              <h3>精修时间线</h3>
              <div class="timeline-tools">
                <button class="active">时间线</button>
                <button>关键帧</button>
                <button>画中画</button>
              </div>
            </div>

            <div class="timeline-ruler">
              <span v-for="tick in timelineTicks" :key="tick">{{ tick }}</span>
            </div>

            <div class="edit-timeline">
              <div v-for="track in editTracks" :key="track.name" class="edit-track">
                <label>
                  <el-icon><component :is="track.icon" /></el-icon>
                  {{ track.name }}
                </label>
                <div class="track-lane">
                  <span
                    v-for="clip in track.clips"
                    :key="clip.label"
                    class="timeline-clip"
                    :class="track.type"
                    :style="{ width: clip.width, marginLeft: clip.offset }"
                  >
                    {{ clip.label }}
                  </span>
                </div>
              </div>
            </div>

            <div class="keyframe-panel">
              <div class="mini-head">
                <span>关键帧</span>
                <button @click="addKeyframe">添加关键帧</button>
              </div>
              <div class="keyframe-row">
                <button
                  v-for="frame in keyframes"
                  :key="frame.time"
                  :class="{ active: activeKeyframe === frame.time }"
                  @click="activeKeyframe = frame.time"
                >
                  <i></i>
                  <strong>{{ frame.time }}</strong>
                  <span>{{ frame.action }}</span>
                </button>
                <el-empty v-if="keyframes.length === 0" description="暂无关键帧，ASR 后会按时间戳生成" :image-size="62" />
              </div>
            </div>

            <div class="pip-panel">
              <div>
                <h4>画中画</h4>
                <p>控制素材叠加的位置、大小和透明度，后续可导出为 OpenCut 轨道。</p>
              </div>
              <div class="pip-controls">
                <label>横向 <el-slider v-model="pipForm.x" :min="0" :max="100" /></label>
                <label>纵向 <el-slider v-model="pipForm.y" :min="0" :max="100" /></label>
                <label>缩放 <el-slider v-model="pipForm.scale" :min="20" :max="160" /></label>
                <label>透明 <el-slider v-model="pipForm.opacity" :min="0" :max="100" /></label>
              </div>
            </div>
          </div>
        </section>

        <section class="output-panel">
          <div class="output-head">
            <div class="panel-title">
              <el-icon><Film /></el-icon>
              <h2>成片输出</h2>
            </div>
            <span><i></i>{{ outputStatus }}</span>
          </div>

          <div class="preview-card">
            <video
              v-if="outputFile"
              ref="videoPlayer"
              :src="outputVideoUrl"
              controls
              preload="metadata"
              crossorigin="anonymous"
              class="output-video"
            />
            <div v-else class="preview-placeholder">
              <el-icon :size="54" color="#4c6a9f"><Film /></el-icon>
              <p>{{ previewSubtitle }}</p>
            </div>
            <div class="progress-line">
              <i :style="{ width: `${progress}%` }"></i>
            </div>
            <div class="preview-tools">
              <el-icon @click="$refs.videoPlayer?.play()"><VideoPlay /></el-icon>
              <span>{{ outputFile ? '已生成成片' : '待生成' }}</span>
              <el-icon @click="$refs.videoPlayer?.pause()"><VideoPause /></el-icon>
              <el-icon><Setting /></el-icon>
              <el-icon><FullScreen /></el-icon>
            </div>
          </div>

          <div class="output-actions">
            <el-button type="primary" @click="runWorkflow" :loading="isRunning">
              <el-icon><MagicStick /></el-icon>
              二创剪辑
            </el-button>
            <el-button :disabled="!outputFile" @click="downloadOutput">
              <el-icon><Download /></el-icon>
              下载视频
            </el-button>
            <el-button type="primary" class="purple">
              <el-icon><MagicStick /></el-icon>
              继续优化
            </el-button>
            <el-button :disabled="!outputFile">
              <el-icon><Promotion /></el-icon>
              发布到抖音
            </el-button>
          </div>

          <div class="log-panel">
            <div class="section-line">
              <h3>生成日志</h3>
              <button>查看详情</button>
            </div>
            <ul>
              <li v-for="log in logs" :key="log.title" :class="{ done: log.done }">
                <el-icon><CircleCheck /></el-icon>
                <strong>{{ log.title }}</strong>
                <span>{{ log.desc }}</span>
                <time>{{ log.time }}</time>
              </li>
              <el-empty v-if="logs.length === 0" description="暂无生成日志" :image-size="62" />
            </ul>
          </div>
        </section>
      </section>

      <footer class="bottom-banner">
        <div class="loop-mark">∞</div>
        <strong>素材 → 文案 → 成片</strong>
        <span>选择真实素材，完成 ASR 识别、二创文案、配音和剪辑输出。</span>
        <el-button>查看闭环记录</el-button>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { computed, markRaw, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { materialApi } from '@/api/material'
import {
  Aim,
  CircleCheck,
  Close,
  Connection,
  Download,
  Edit,
  EditPen,
  Film,
  FullScreen,
  MagicStick,
  Microphone,
  Picture,
  Plus,
  Promotion,
  Refresh,
  Setting,
  Share,
  UploadFilled,
  VideoCamera,
  VideoPause,
  VideoPlay,
  View
} from '@element-plus/icons-vue'

const topic = ref('')
const activeStage = ref('extract')
const progress = ref(0)
const isRunning = ref(false)
const isAsrRunning = ref(false)
const outputFile = ref('')
const audioFile = ref('')
const workflowWarnings = ref([])
const materials = ref([])
const selectedSourceFile = ref('')
const asrTranscript = ref('')

const voiceForm = reactive({
  voice: 'x4_lingbosong',
  speed: 1.05,
  mood: 'professional',
  music: 'tech'
})

const videoMaterials = computed(() => {
  return materials.value.filter(material => {
    const filename = String(material.filename || '').toLowerCase()
    return ['.mp4', '.mov', '.mkv', '.avi', '.wmv'].some(ext => filename.endsWith(ext))
  })
})

const railItems = [
  { label: '采集中心', icon: markRaw(Connection) },
  { label: '文案二创', icon: markRaw(EditPen) },
  { label: '分镜生成', icon: markRaw(Picture) },
  { label: 'TTS 配音', icon: markRaw(Microphone) },
  { label: '视频剪辑中心', icon: markRaw(Film), active: true },
  { label: '发布复盘', icon: markRaw(Share) }
]

const importActions = [
  { label: '粘贴文案', desc: '从剪贴板粘贴', icon: markRaw(Edit), stage: 'extract' },
  { label: '上传素材', desc: '图片 / 视频 / 音频', icon: markRaw(UploadFilled), stage: 'clip' },
  { label: '导入对标内容', desc: '链接 / 视频解析', icon: markRaw(Connection), stage: 'extract' }
]

const rewriteRules = [
  '先提取对标内容中的钩子、观点、案例和结尾转化。',
  '不改事实，不照搬原句，表达要口语化。',
  '开头三秒必须有明确痛点或反差。',
  '原文生成后自动拆成分镜和字幕。',
  'TTS 配音与字幕、画面节奏保持一致。',
  '智能剪辑至少压缩 50% 冗余内容。'
]

const stages = ref([
  { key: 'extract', title: '文案提取 Extract', desc: '从对标视频或文案中提取钩子、观点、案例和转化点', icon: markRaw(View), status: 'pending' },
  { key: 'rewrite', title: '原文生成 Rewrite', desc: '基于你的 IP 语气重写成可口播文案', icon: markRaw(EditPen), status: 'pending' },
  { key: 'tts', title: 'TTS 合成 Voice', desc: '调用 x4_lingbosong 音色生成自然旁白', icon: markRaw(Microphone), status: 'pending' },
  { key: 'clip', title: '智能剪辑 Clip', desc: '自动生成分镜、字幕、动画弹窗和成片', icon: markRaw(MagicStick), status: 'pending' }
])

const scriptBlocks = ref([])

const storyboard = reactive([])

const timelineTicks = ['00:00', '00:05', '00:10', '00:15', '00:20', '00:25', '00:30']

const editTracks = computed(() => [
  {
    name: '主视频',
    type: 'video',
    icon: markRaw(Film),
    clips: storyboard.map((shot, index) => ({
      label: shot.title || `镜头 ${index + 1}`,
      width: `${Math.max(16, Number.parseInt(shot.duration, 10) * 5 || 24)}%`,
      offset: index === 0 ? '0' : '2%'
    }))
  },
  {
    name: '字幕',
    type: 'caption',
    icon: markRaw(EditPen),
    clips: scriptBlocks.value.map(block => ({
      label: block.title,
      width: '23%',
      offset: '1%'
    }))
  },
  {
    name: '音频',
    type: 'audio',
    icon: markRaw(Microphone),
    clips: [{ label: audioFile.value ? 'TTS 配音' : '待生成配音', width: '72%', offset: '0' }]
  },
  {
    name: '画中画',
    type: 'pip',
    icon: markRaw(Picture),
    clips: [{ label: selectedSourceFile.value ? '素材叠加' : '选择素材', width: '28%', offset: '18%' }]
  }
])

const keyframes = ref([])
const activeKeyframe = ref('')
const pipForm = reactive({
  x: 68,
  y: 18,
  scale: 64,
  opacity: 92
})

const logs = ref([])

const outputStatus = computed(() => {
  if (isRunning.value) return '处理中 10m'
  if (outputFile.value) return '已生成'
  return '待生成'
})
const previewSubtitle = computed(() => {
  if (asrTranscript.value) return asrTranscript.value.slice(0, 42)
  if (scriptBlocks.value.length) return scriptBlocks.value[0].text.slice(0, 42)
  if (selectedSourceFile.value) return '已选择素材，点击 ASR 提取真实口播文案。'
  return '请选择素材或输入主题后开始二创剪辑。'
})

const outputVideoUrl = computed(() => {
  if (!outputFile.value) return ''
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
  return `${baseUrl}/download/${outputFile.value}`
})

const stageStatusText = (stage) => {
  if (stage.status === 'done') return '已完成'
  if (stage.status === 'running') return '处理中'
  if (stage.status === 'failed') return '失败'
  return '待处理'
}

const generateScript = async () => {
  if (!topic.value && !asrTranscript.value) {
    ElMessage.warning('请先输入主题或完成 ASR 识别')
    return
  }
  activeStage.value = 'rewrite'
  markBeforeDone('rewrite')
  try {
    const response = await materialApi.oneClickRewrite({
      topic: topic.value,
      referenceText: asrTranscript.value || topic.value
    })
    if (response.code === 200) {
      const data = response.data || {}
      if (data.script?.blocks?.length) {
        scriptBlocks.value = data.script.blocks
      }
      if (data.storyboard?.length) {
        storyboard.splice(0, storyboard.length, ...mapStoryboard(data.storyboard))
      }
      setStageStatus('rewrite', 'done')
      ElMessage.success('二创文案生成完成')
    } else {
      throw new Error(response.msg || '文案生成失败')
    }
  } catch (error) {
    console.error('文案生成失败:', error)
    setStageStatus('rewrite', 'failed')
    ElMessage.error('文案生成失败：' + (error.message || '未知错误'))
  }
}

const mapStoryboard = (items) => {
  const themes = ['talking', 'data', 'motion', 'data']
  const icons = [VideoCamera, Aim, MagicStick, Picture]
  return (items || []).map((shot, index) => ({
    title: shot.title || `镜头 ${index + 1}`,
    copy: shot.copy || '',
    duration: `${shot.duration || 6}s`,
    theme: themes[index % 4],
    icon: markRaw(icons[index % 4])
  }))
}

const addKeyframe = () => {
  const nextIndex = keyframes.value.length + 1
  const second = String(Math.min(59, nextIndex * 6)).padStart(2, '0')
  const time = `00:${second}`
  keyframes.value.push({ time, action: '自定义动作' })
  activeKeyframe.value = time
}

const setStageStatus = (key, status) => {
  stages.value = stages.value.map(stage => stage.key === key ? { ...stage, status } : stage)
}

const markBeforeDone = (key) => {
  const order = ['extract', 'rewrite', 'tts', 'clip']
  const current = order.indexOf(key)
  stages.value = stages.value.map(stage => {
    const index = order.indexOf(stage.key)
    if (index < current) return { ...stage, status: 'done' }
    if (index === current) return { ...stage, status: 'running' }
    return { ...stage, status: 'pending' }
  })
}

const nowTime = () => new Date().toLocaleTimeString('zh-CN', { hour12: false })

const formatTimelineTime = (seconds) => {
  const value = Math.max(0, Math.round(Number(seconds) || 0))
  const minute = String(Math.floor(value / 60)).padStart(2, '0')
  const second = String(value % 60).padStart(2, '0')
  return `${minute}:${second}`
}

const syncWorkflowResult = (data) => {
  if (data.transcript?.text) {
    asrTranscript.value = data.transcript.text
  }
  if (data.transcript?.segments?.length) {
    keyframes.value = data.transcript.segments.slice(0, 8).map((segment, index) => ({
      time: formatTimelineTime(segment.start || 0),
      action: segment.text || `片段 ${index + 1}`
    }))
    activeKeyframe.value = keyframes.value[0]?.time || ''
  }
  if (data.script?.blocks?.length) {
    scriptBlocks.value = data.script.blocks
  }
  if (data.storyboard?.length) {
    storyboard.splice(0, storyboard.length, ...data.storyboard.map((shot, index) => ({
      title: shot.title || `镜头 ${index + 1}`,
      copy: shot.copy || '',
      duration: `${shot.duration || 6}s`,
      theme: ['talking', 'data', 'motion', 'data'][index % 4],
      icon: markRaw([VideoCamera, Aim, MagicStick, Picture][index % 4])
    })))
  }
  audioFile.value = data.audio?.filepath || ''
  outputFile.value = data.output?.filepath || ''
  workflowWarnings.value = data.warnings || []
  logs.value = [
    { title: '文案提取', desc: '对标内容结构提取完成', time: nowTime(), done: true },
    { title: '原文生成', desc: '二创口播稿生成完成', time: nowTime(), done: true },
    {
      title: 'TTS 合成',
      desc: audioFile.value ? 'x4_lingbosong 配音生成完成' : '未配置讯飞密钥，已生成无配音预览',
      time: nowTime(),
      done: Boolean(audioFile.value)
    },
    { title: '智能剪辑', desc: outputFile.value ? '成片已生成并加入素材库' : '成片生成失败', time: nowTime(), done: Boolean(outputFile.value) }
  ]
}

const runWorkflow = async () => {
  if (isRunning.value) return
  isRunning.value = true
  progress.value = 12
  outputFile.value = ''
  audioFile.value = ''
  workflowWarnings.value = []
  logs.value = [
    { title: '文案提取', desc: '正在提取对标内容结构', time: nowTime(), done: false },
    { title: '原文生成', desc: '等待二创口播稿', time: '--:--:--', done: false },
    { title: 'TTS 合成', desc: '等待配音合成', time: '--:--:--', done: false },
    { title: '智能剪辑', desc: '等待成片合成', time: '--:--:--', done: false }
  ]
  stages.value = stages.value.map(stage => ({ ...stage, status: 'pending' }))
  let stagesDone = false
  const stageTimer = setTimeout(() => {
    if (!stagesDone) markBeforeDone('extract')
    setTimeout(() => { if (!stagesDone) markBeforeDone('rewrite') }, 2000)
    setTimeout(() => { if (!stagesDone) markBeforeDone('tts') }, 4000)
  }, 1000)
  try {
    progress.value = 22
    const response = await materialApi.oneClickRun({
      topic: topic.value,
      referenceText: asrTranscript.value || topic.value,
      sourceFile: selectedSourceFile.value || '',
      asr: {
        engine: 'whisper',
        model: 'base',
        language: 'zh',
        device: 'cpu',
        computeType: 'int8'
      },
      voice: {
        voice: voiceForm.voice,
        speed: voiceForm.speed,
        mood: voiceForm.mood,
        music: voiceForm.music
      },
      clip: {
        outputName: '一键剪辑成片.mp4'
      }
    })

    if (response.code === 200) {
      activeStage.value = 'clip'
      progress.value = 100
      stages.value = stages.value.map(stage => ({ ...stage, status: 'done' }))
      syncWorkflowResult(response.data || {})
      if (workflowWarnings.value.length) {
        ElMessage.warning('成片已生成，但 TTS 未完成：请检查讯飞环境变量')
      } else {
        ElMessage.success('一键剪辑完成，成片已加入素材库')
      }
    } else {
      throw new Error(response.msg || '一键剪辑失败')
    }
  } catch (error) {
    console.error('一键剪辑失败:', error)
    setStageStatus(activeStage.value, 'failed')
    ElMessage.error('一键剪辑失败：' + (error.message || '未知错误'))
  } finally {
    stagesDone = true
    clearTimeout(stageTimer)
    isRunning.value = false
  }
}

const downloadOutput = () => {
  if (!outputFile.value) return
  window.open(materialApi.downloadMaterial(outputFile.value), '_blank')
}

const loadMaterials = async () => {
  try {
    const response = await materialApi.getAllMaterials()
    if (response.code === 200) {
      materials.value = response.data || []
      if (!selectedSourceFile.value && videoMaterials.value.length) {
        selectedSourceFile.value = videoMaterials.value[0].file_path
      }
    }
  } catch (error) {
    console.error('加载素材失败:', error)
  }
}

const runAsr = async () => {
  if (!selectedSourceFile.value) {
    ElMessage.warning('请先选择一个视频素材')
    return
  }
  isAsrRunning.value = true
  activeStage.value = 'extract'
  markBeforeDone('extract')
  try {
    const response = await materialApi.oneClickAsr({
      file: selectedSourceFile.value,
      options: {
        engine: 'whisper',
        model: 'base',
        language: 'zh',
        device: 'cpu',
        computeType: 'int8'
      }
    })
    if (response.code === 200) {
      asrTranscript.value = response.data?.transcript?.text || ''
      const segments = response.data?.transcript?.segments || []
      keyframes.value = segments.slice(0, 8).map((segment, index) => ({
        time: formatTimelineTime(segment.start || 0),
        action: segment.text || `片段 ${index + 1}`
      }))
      activeKeyframe.value = keyframes.value[0]?.time || ''
      if (asrTranscript.value) {
        ElMessage.success('ASR 文案提取完成')
      } else {
        ElMessage.warning('ASR 完成，但没有识别到文案')
      }
    } else {
      throw new Error(response.msg || 'ASR 提取失败')
    }
  } catch (error) {
    console.error('ASR 提取失败:', error)
    ElMessage.error('ASR 提取失败：' + (error.message || '未知错误'))
  } finally {
    isAsrRunning.value = false
  }
}

onMounted(() => {
  loadMaterials()
})
</script>

<style lang="scss" scoped>
.one-click-page {
  display: grid;
  grid-template-columns: 112px 1fr;
  min-height: calc(100vh - 60px);
  margin: -20px;
  padding: 22px;
  color: #eef4ff;
  background:
    radial-gradient(circle at 45% -10%, rgba(80, 112, 255, 0.18), transparent 35%),
    linear-gradient(135deg, #070b12 0%, #0b111c 48%, #080b12 100%);
}

.rail,
.input-panel,
.loop-panel,
.output-panel,
.bottom-banner {
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(17, 24, 39, 0.72);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.28);
}

.rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  min-height: calc(100vh - 104px);
  padding: 18px 10px;
  border-radius: 14px;
}

.rail-logo {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  margin-bottom: 8px;
}

.logo-shape {
  width: 42px;
  height: 42px;
  border-radius: 10px 18px 10px 18px;
  background: linear-gradient(135deg, #39a7ff, #8d5cff);
  transform: skewY(-8deg);
}

.rail button {
  display: grid;
  place-items: center;
  gap: 8px;
  width: 86px;
  min-height: 72px;
  border: 0;
  border-radius: 12px;
  color: #8f9bad;
  background: transparent;
  cursor: pointer;

  &.active {
    color: #fff;
    background: rgba(124, 92, 255, 0.18);
    box-shadow: inset 0 0 0 1px #7c5cff;
  }

  span {
    font-size: 12px;
  }
}

.one-click-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  padding-left: 16px;
}

.hero-bar {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 18px;

  p {
    margin: 0 0 8px;
    color: #9ca9bd;
    font-size: 13px;
  }

  h1 {
    margin: 0;
    color: #4c8dff;
    font-size: 26px;
    letter-spacing: 0;
  }
}

.hero-actions {
  display: flex;
  gap: 10px;
}

.workspace {
  display: grid;
  grid-template-columns: 420px minmax(520px, 1fr) 440px;
  gap: 14px;
}

.input-panel,
.loop-panel,
.output-panel {
  min-height: 690px;
  padding: 18px;
  border-radius: 12px;
}

.panel-title,
.loop-head,
.output-head,
.section-line,
.mini-head,
.voice-row,
.preview-tools,
.output-actions,
.log-panel li {
  display: flex;
  align-items: center;
}

.panel-title {
  gap: 10px;

  h2,
  h3 {
    margin: 0;
    font-size: 18px;
  }

  &.small h3 {
    font-size: 15px;
  }
}

.field-label {
  display: block;
  margin: 22px 0 8px;
  color: #d5deee;
  font-size: 13px;
  font-weight: 700;
}

.import-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;

  button {
    min-height: 64px;
    padding: 10px;
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: 8px;
    color: #dbe6f7;
    background: rgba(30, 41, 59, 0.72);
    text-align: left;
    cursor: pointer;
  }

  strong,
  span {
    display: block;
    margin-top: 5px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  span {
    color: #8f9bad;
    font-size: 11px;
  }
}

.asr-card,
.material-bin,
.rules-card,
.voice-card,
.script-card,
.storyboard,
.editor-board,
.log-panel {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid rgba(124, 92, 255, 0.22);
  border-radius: 10px;
  background: rgba(30, 21, 53, 0.38);
}

.asr-card {
  border-color: rgba(96, 165, 250, 0.24);
  background: rgba(14, 31, 58, 0.48);
}

.asr-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 126px;
  gap: 10px;
  margin: 12px 0;
}

.rewrite-clip-button {
  width: 100%;
  min-height: 44px;
  margin-top: 12px;
  border: 0;
  background: linear-gradient(135deg, #4f7cff, #8a4dff);
  font-weight: 700;
}

.material-bin {
  border-color: rgba(52, 211, 153, 0.22);
  background: rgba(8, 47, 73, 0.32);
}

.material-bin small {
  color: #93a4ba;
}

.material-list {
  display: grid;
  gap: 9px;
  margin-top: 12px;
}

.material-list button {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 46px;
  padding: 8px 10px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 8px;
  color: #dbe6f7;
  background: rgba(15, 23, 42, 0.64);
  text-align: left;
  cursor: pointer;

  &.active {
    border-color: #34d399;
    background: rgba(20, 83, 45, 0.28);
  }

  strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
  }

  em {
    color: #8fa0b7;
    font-size: 11px;
    font-style: normal;
  }
}

.material-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 7px;
  background: linear-gradient(135deg, #1d4ed8, #7c3aed);
}

.mini-head,
.section-line,
.loop-head,
.output-head {
  justify-content: space-between;
}

.rules-card ol {
  display: grid;
  gap: 8px;
  margin: 12px 0 0;
  padding-left: 22px;
  color: #cbd7e8;
  line-height: 1.55;
  font-size: 13px;
}

.voice-row {
  display: grid;
  grid-template-columns: 70px 1fr auto;
  gap: 10px;
  margin-top: 12px;
  color: #c9d4e8;
  font-size: 13px;
}

.loop-panel,
.output-panel {
  display: flex;
  flex-direction: column;
}

.loop-head span,
.output-head span {
  padding: 6px 12px;
  border-radius: 999px;
  color: #aeb9ca;
  background: rgba(30, 41, 59, 0.8);
  font-size: 12px;
}

.loop-list {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.loop-item {
  display: grid;
  grid-template-columns: 50px 1fr auto;
  align-items: center;
  gap: 12px;
  min-height: 74px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.62);

  &.active {
    border-color: rgba(80, 141, 255, 0.7);
  }

  &.done em {
    color: #6ee7b7;
  }

  strong {
    color: #5a93ff;
  }

  p {
    margin: 7px 0 0;
    color: #9faabd;
    font-size: 13px;
  }

  em {
    color: #fbbf24;
    font-style: normal;
    font-size: 12px;
  }
}

.stage-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  color: #6ea2ff;
  background: rgba(65, 92, 255, 0.18);
  font-size: 22px;
}

.section-line {
  h3 {
    margin: 0;
    font-size: 16px;
  }

  button {
    border: 0;
    color: #9fb0c7;
    background: transparent;
    cursor: pointer;

    &.active {
      color: #fff;
    }
  }
}

.script-grid {
  display: grid;
  gap: 10px;
  margin-top: 12px;

  article {
    padding: 11px;
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.68);
  }

  span {
    color: #fbbf24;
    font-size: 12px;
  }

  p {
    margin: 6px 0 0;
    color: #dce6f5;
    line-height: 1.6;
    font-size: 13px;
  }
}

.shot-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 12px;
}

.shot-card,
.add-shot {
  min-height: 190px;
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 9px;
  background: rgba(15, 23, 42, 0.7);
}

.shot-cover {
  display: grid;
  place-items: center;
  height: 76px;
  border-radius: 7px;
  font-size: 28px;

  &.talking {
    background: linear-gradient(135deg, #312e81, #7c3aed);
  }

  &.data {
    background: linear-gradient(135deg, #0f766e, #2563eb);
  }

  &.motion {
    background: linear-gradient(135deg, #7c2d12, #be185d);
  }
}

.shot-card {
  strong,
  p,
  span {
    display: block;
  }

  strong {
    margin-top: 10px;
  }

  p {
    min-height: 42px;
    color: #aeb9ca;
    font-size: 12px;
    line-height: 1.5;
  }

  span {
    color: #c7d2fe;
    font-size: 12px;
    text-align: right;
  }
}

.add-shot {
  display: grid;
  place-items: center;
  color: #91a2bb;
  border-style: dashed;
  cursor: pointer;
}

.editor-board {
  border-color: rgba(96, 165, 250, 0.22);
  background: rgba(15, 23, 42, 0.6);
}

.timeline-tools {
  display: flex;
  gap: 6px;
}

.timeline-tools button {
  padding: 6px 10px;
  border-radius: 7px;
  background: rgba(30, 41, 59, 0.84);

  &.active {
    color: #fff;
    background: rgba(79, 124, 255, 0.38);
  }
}

.timeline-ruler {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
  margin: 14px 0 8px;
  padding-left: 88px;
  color: #78869d;
  font-size: 11px;
}

.edit-timeline {
  display: grid;
  gap: 10px;
}

.edit-track {
  display: grid;
  grid-template-columns: 82px 1fr;
  align-items: center;
  gap: 8px;

  label {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #aeb9ca;
    font-size: 12px;
  }
}

.track-lane {
  display: flex;
  align-items: center;
  min-height: 38px;
  padding: 5px;
  overflow: hidden;
  border-radius: 8px;
  background: rgba(2, 6, 23, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.1);
}

.timeline-clip {
  display: inline-flex;
  align-items: center;
  min-width: 68px;
  height: 28px;
  padding: 0 10px;
  overflow: hidden;
  border-radius: 6px;
  color: #fff;
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.timeline-clip.video {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
}

.timeline-clip.caption {
  background: rgba(79, 124, 255, 0.42);
  border: 1px solid rgba(96, 165, 250, 0.35);
}

.timeline-clip.audio {
  background: linear-gradient(135deg, #059669, #14b8a6);
}

.timeline-clip.pip {
  background: linear-gradient(135deg, #f59e0b, #db2777);
}

.keyframe-panel,
.pip-panel {
  margin-top: 14px;
  padding: 12px;
  border-radius: 9px;
  background: rgba(2, 6, 23, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.keyframe-panel .mini-head button {
  border: 0;
  color: #93c5fd;
  background: transparent;
  cursor: pointer;
}

.keyframe-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
  margin-top: 10px;
}

.keyframe-row button {
  min-height: 58px;
  padding: 8px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 8px;
  color: #dbeafe;
  background: rgba(30, 41, 59, 0.7);
  text-align: left;
  cursor: pointer;

  &.active {
    border-color: #fbbf24;
    background: rgba(120, 53, 15, 0.36);
  }

  i {
    display: inline-block;
    width: 9px;
    height: 9px;
    margin-right: 6px;
    transform: rotate(45deg);
    background: #fbbf24;
  }

  strong,
  span {
    display: block;
    margin-top: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
  }

  span {
    color: #aeb9ca;
  }
}

.pip-panel {
  display: grid;
  grid-template-columns: 170px 1fr;
  gap: 12px;

  h4 {
    margin: 0 0 6px;
  }

  p {
    margin: 0;
    color: #93a4ba;
    font-size: 12px;
    line-height: 1.5;
  }
}

.pip-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 14px;

  label {
    color: #cbd5e1;
    font-size: 12px;
  }
}

.preview-card {
  position: relative;
  min-height: 310px;
  margin-top: 16px;
  overflow: hidden;
  border-radius: 12px;
  background:
    linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.75)),
    radial-gradient(circle at 15% 12%, rgba(124, 92, 255, 0.5), transparent 26%),
    linear-gradient(135deg, #18243a, #15111b);
}

.preview-placeholder {
  position: absolute;
  inset: 34px 44px 76px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;

  p {
    margin: 0;
    color: #9faabd;
    font-size: 14px;
    text-align: center;
    max-width: 80%;
  }
}

.output-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: calc(100% - 44px);
  object-fit: contain;
  background: #000;
  border-radius: 12px 12px 0 0;
}

.progress-line {
  position: absolute;
  left: 28px;
  right: 28px;
  bottom: 42px;
  height: 4px;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.35);

  i {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #2f7cff, #8b5cf6);
  }
}

.preview-tools {
  position: absolute;
  left: 28px;
  right: 28px;
  bottom: 14px;
  justify-content: space-between;
  color: #fff;
}

.output-actions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 14px;

  .purple {
    background: linear-gradient(135deg, #6d5dfc, #9b4dff);
    border: 0;
  }
}

.log-panel {
  margin-top: 18px;

  ul {
    display: grid;
    gap: 13px;
    margin: 16px 0 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: grid;
    grid-template-columns: 22px 80px 1fr auto;
    gap: 8px;
    color: #93a0b4;

    &.done .el-icon {
      color: #34d399;
    }
  }

  strong {
    color: #dbe6f7;
  }

  span,
  time {
    font-size: 13px;
  }
}

.bottom-banner {
  display: grid;
  grid-template-columns: 90px 180px 1fr auto;
  align-items: center;
  gap: 24px;
  min-height: 76px;
  padding: 0 28px;
  border-radius: 14px;
  background: linear-gradient(120deg, rgba(190, 75, 212, 0.95), rgba(31, 86, 227, 0.95), rgba(14, 145, 224, 0.95));

  .loop-mark {
    font-size: 48px;
    line-height: 1;
  }

  span {
    color: #eaf2ff;
  }
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner),
:deep(.el-select__wrapper) {
  background: rgba(15, 23, 42, 0.86);
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.18) inset;
}

:deep(.el-input__inner),
:deep(.el-textarea__inner),
:deep(.el-select__selected-item) {
  color: #eef4ff;
}

@media (max-width: 1440px) {
  .workspace {
    grid-template-columns: 360px minmax(480px, 1fr);
  }

  .output-panel {
    grid-column: 1 / -1;
    min-height: auto;
  }
}
</style>
