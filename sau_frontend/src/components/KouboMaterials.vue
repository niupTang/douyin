<template>
  <section class="material-workspace" v-loading="loading">
    <aside class="asset-pane">
      <div class="pane-title"><strong>项目素材</strong><span>{{ assets.length }}</span></div>
      <label class="upload-button" :class="{ busy: uploading }">
        {{ uploading ? '正在上传并解析…' : '＋ 上传原视频' }}
        <input type="file" accept=".mp4,.mov,.mkv,.webm,.avi,.m4v" :disabled="uploading" @change="upload" />
      </label>
      <el-input v-model="keyword" placeholder="搜索素材名称" clearable size="small" />
      <div class="asset-scroll">
        <button v-for="asset in visibleAssets" :key="asset.id" class="asset-item"
          :class="{ active: selected?.id === asset.id }" @click="selectAsset(asset)">
          <img v-if="asset.kind === 'frame'" :src="assetUrl(asset)" loading="lazy" alt="抽帧图片" />
          <span v-else class="asset-icon">{{ isVideo(asset) ? '▶' : '◇' }}</span>
          <span class="asset-caption"><strong>{{ asset.original_name }}</strong><small>{{ kindLabel[asset.kind] || asset.kind }} · {{ formatSize(asset.size) }}</small></span>
        </button>
        <el-empty v-if="!visibleAssets.length" description="暂无匹配素材，上传视频开始" :image-size="48" />
      </div>
      <el-button text size="small" @click="loadAssets">刷新素材</el-button>
    </aside>

    <main class="preview-pane">
      <div class="pane-title"><strong>素材预览</strong><span>{{ selected ? kindLabel[selected.kind] || '素材' : '等待选择' }}</span></div>
      <div class="preview-stage">
        <video v-if="selected && isVideo(selected)" :key="selected.id" ref="player" :src="assetUrl(selected)"
          controls preload="metadata" @timeupdate="updateTime" @seeking="seeking = true" @seeked="onSeeked"
          @loadedmetadata="onMetadata" @error="videoError = true" />
        <img v-else-if="selected && ['frame', 'cover', 'portrait', 'preview'].includes(selected.kind)" :src="assetUrl(selected)" alt="项目图片预览" />
        <div v-else class="stage-empty"><span>▷</span><p>{{ selected ? '此素材暂不支持画面预览' : '选择原视频，定位并保存需要的画面' }}</p></div>
      </div>
      <el-alert v-if="videoError" title="浏览器无法播放此视频，可转换为 H.264 MP4 后预览。" type="warning" :closable="false" />
      <template v-if="selected && isVideo(selected)">
        <div class="transport">
          <span>{{ time.toFixed(3) }} / {{ duration.toFixed(3) }} 秒</span>
          <el-button-group>
            <el-button size="small" :disabled="!canSeek || seeking || !info.fps" @click="step(-1)">上一帧</el-button>
            <el-button size="small" :disabled="!canSeek || seeking || !info.fps" @click="step(1)">下一帧</el-button>
          </el-button-group>
        </div>
        <el-slider :model-value="time" :min="0" :max="Math.max(0.001, maxTime)" :step="0.001" :disabled="!canSeek" @change="seek" />
        <small class="muted">按视频平均帧率前后定位；可变帧率素材以导出画面为准。</small>
      </template>
    </main>

    <aside class="properties-pane">
      <div class="pane-title"><strong>素材属性</strong><span>FFmpeg</span></div>
      <template v-if="selected">
        <p class="selected-name">{{ selected.original_name }}</p>
        <dl><dt>类型</dt><dd>{{ kindLabel[selected.kind] || selected.kind }}</dd><dt>文件大小</dt><dd>{{ formatSize(selected.size) }}</dd></dl>
        <template v-if="isVideo(selected)">
          <dl><dt>分辨率</dt><dd>{{ info.width ? `${info.width} × ${info.height}` : '读取中' }}</dd><dt>帧率</dt><dd>{{ info.fps ? `${info.fps.toFixed(3)} fps` : '—' }}</dd><dt>时长</dt><dd>{{ duration.toFixed(3) }} 秒</dd></dl>
          <label class="time-label" :for="`koubo-time-${projectId}`">定位时间（秒）</label>
          <input :id="`koubo-time-${projectId}`" class="time-input" type="number" :value="time.toFixed(3)" min="0" :max="maxTime" step="0.001" :disabled="!canSeek" @change="seek($event.target.value)" />
          <el-button class="save-frame" type="primary" :loading="saving" :disabled="!canSeek || seeking || videoError" @click="saveFrame">保存当前画面</el-button>
          <p class="muted">从原视频提取原始分辨率 PNG，保存到当前项目，自动记录来源和时间点。</p>
        </template>
        <template v-if="selected.kind === 'frame' && selected.metadata?.source_asset_id">
          <div class="source-info"><small>来源视频</small><p>{{ selected.metadata.source_name }}</p><strong>{{ Number(selected.metadata.seconds).toFixed(3) }} 秒</strong></div>
          <el-button size="small" @click="returnToSource">返回原视频位置</el-button>
        </template>
        <a class="download-link" :href="assetUrl(selected)" target="_blank" rel="noreferrer">打开原文件 / 保存</a>
      </template>
      <el-empty v-else description="选择素材查看属性" :image-size="48" />
    </aside>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { kouboApi } from '@/api/koubo'

const props = defineProps({ projectId: { type: String, required: true } })
const emit = defineEmits(['uploaded'])
const assets = ref([])
const selected = ref(null)
const keyword = ref('')
const player = ref(null)
const time = ref(0)
const duration = ref(0)
const info = ref({})
const loading = ref(false)
const uploading = ref(false)
const saving = ref(false)
const seeking = ref(false)
const videoError = ref(false)
let selectionVersion = 0
const kindLabel = { raw_video: '原视频', edited_video: '成片', frame: '抽帧图片', cover: '封面', portrait: '人物照片', subtitle: '字幕', preview: '预览图' }
const visibleAssets = computed(() => assets.value.filter(a => (a.original_name || '').toLowerCase().includes(keyword.value.toLowerCase())))
const maxTime = computed(() => Math.max(0, duration.value - (info.value.fps ? 1 / info.value.fps : 0.001)))
const canSeek = computed(() => duration.value > 0 && !!player.value && !loading.value)
const isVideo = asset => ['raw_video', 'edited_video'].includes(asset.kind)
const formatSize = size => `${((size || 0) / 1024 / 1024).toFixed(2)} MB`
const assetUrl = asset => `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'}/api/koubo/assets/${asset.id}/content?token=${encodeURIComponent(localStorage.getItem('token') || '')}`

async function loadAssets() {
  loading.value = true
  try {
    const response = await kouboApi.listAssets(props.projectId)
    assets.value = response.data || []
    if (!selected.value && assets.value.length) await selectAsset(assets.value.find(isVideo) || assets.value[0])
  } catch { /* 请求层显示错误 */ } finally { loading.value = false }
}

async function selectAsset(asset) {
  const version = ++selectionVersion
  player.value?.pause()
  selected.value = asset
  time.value = 0
  duration.value = 0
  info.value = {}
  seeking.value = false
  videoError.value = false
  if (isVideo(asset)) {
    try {
      const response = await kouboApi.videoInfo(asset.id)
      if (version !== selectionVersion) return
      info.value = response.data
      if (!duration.value) duration.value = response.data.duration || 0
    } catch { /* 请求层显示错误 */ }
  }
}
function onMetadata() {
  const length = player.value?.duration
  if (Number.isFinite(length)) duration.value = length
}
function updateTime() { time.value = player.value?.currentTime || 0 }
function onSeeked() { seeking.value = false; updateTime() }
function seek(value) {
  if (!player.value || !Number.isFinite(Number(value))) return
  player.value.pause()
  const position = Math.min(maxTime.value, Math.max(0, Number(value)))
  time.value = position
  player.value.currentTime = position
}
function step(direction) { seek(time.value + direction / info.value.fps) }
async function upload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const response = await kouboApi.uploadVideo(props.projectId, file)
    await loadAssets()
    await selectAsset(response.data)
    emit('uploaded')
    ElMessage.success('原视频已加入项目素材')
  } catch { /* 请求层显示错误 */ } finally { uploading.value = false; event.target.value = '' }
}
async function saveFrame() {
  const source = selected.value
  player.value?.pause()
  const position = player.value?.currentTime ?? time.value
  saving.value = true
  try {
    const response = await kouboApi.saveFrame(source.id, position)
    assets.value.push(response.data)
    ElMessage.success(`已保存 ${position.toFixed(3)} 秒的画面，可在左侧素材中查看`)
  } catch { /* 请求层显示错误 */ } finally { saving.value = false }
}
async function returnToSource() {
  const metadata = selected.value.metadata
  const source = assets.value.find(a => a.id === metadata.source_asset_id)
  if (!source) return ElMessage.warning('来源视频不存在')
  await selectAsset(source)
  await nextTick()
  if (player.value?.readyState >= 1) seek(metadata.seconds)
  else player.value?.addEventListener('loadedmetadata', () => seek(metadata.seconds), { once: true })
}
onMounted(loadAssets)
</script>

<style scoped>
.material-workspace{display:grid;grid-template-columns:210px minmax(250px,1fr) 220px;gap:1px;background:#e2e6ec;border:1px solid #e2e6ec;border-radius:14px;overflow:hidden;min-height:540px}
.asset-pane,.preview-pane,.properties-pane{background:#fff;padding:16px;min-width:0}.pane-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;font-size:13px}.pane-title>span{font-size:11px;color:#8892a2}
.time-input{box-sizing:border-box;width:100%;height:34px;border:1px solid #d6dce6;border-radius:5px;padding:0 10px;color:#344760;font:inherit;font-size:13px}.time-input:focus{outline:2px solid #b2d4ff;border-color:#409eff}.time-input:disabled{background:#f5f7fa;color:#a8abb2}
.upload-button{display:block;border:1px dashed #b2c1d5;border-radius:8px;padding:13px 5px;text-align:center;font-size:12px;cursor:pointer;color:#3763a0;margin-bottom:12px}.upload-button input{display:none}.busy{opacity:.6;cursor:wait}
.asset-scroll{max-height:470px;overflow:auto;margin-top:12px}.asset-item{display:flex;align-items:center;gap:9px;border:1px solid transparent;border-radius:8px;padding:9px 7px;width:100%;background:transparent;text-align:left;cursor:pointer;margin-bottom:5px;color:#273446}.asset-item.active{background:#edf4ff;border-color:#b4cef5}.asset-item:hover{background:#f2f5fa}.asset-item img,.asset-icon{width:42px;height:42px;object-fit:contain;border-radius:5px;background:#e6ebf2;flex-shrink:0}.asset-icon{display:grid;place-items:center;color:#607694}.asset-caption{min-width:0}.asset-caption strong{display:block;overflow-wrap:anywhere;font-size:12px;font-weight:500}.asset-caption small{display:block;color:#87909d;font-size:10px;margin-top:5px}
.preview-stage{height:370px;background:#151923;border-radius:10px;display:flex;align-items:center;justify-content:center;overflow:hidden}.preview-stage video,.preview-stage img{max-width:100%;max-height:100%;object-fit:contain}.stage-empty{color:#98a5b8;text-align:center;padding:20px;font-size:12px}.stage-empty>span{font-size:48px}.transport{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:18px;font-variant-numeric:tabular-nums;font-size:12px;color:#69788e;flex-wrap:wrap}.muted{font-size:11px;line-height:1.8;color:#8691a1}.selected-name{font-size:13px;overflow-wrap:anywhere;line-height:1.7}dl{display:grid;grid-template-columns:70px 1fr;gap:12px 4px;font-size:12px;margin:22px 0}dt{color:#8c96a4}dd{margin:0;overflow-wrap:anywhere}.time-label{display:block;font-size:12px;margin:20px 0 10px}.properties-pane .el-input-number{width:100%}.save-frame{width:100%;margin-top:16px}.download-link{display:block;font-size:12px;color:#5279b0;margin-top:22px}.source-info{background:#f5f7fa;padding:12px;border-radius:8px;margin-bottom:15px;font-size:12px;overflow-wrap:anywhere}.source-info small{color:#8892a2}
@container(max-width:850px){.material-workspace{grid-template-columns:170px minmax(220px,1fr)}.properties-pane{grid-column:1/-1}.properties-pane dl{max-width:500px}.properties-pane .el-input-number,.save-frame{max-width:240px}.save-frame{display:block}.preview-stage{height:330px}}
@container(max-width:560px){.material-workspace{grid-template-columns:1fr}.properties-pane{grid-column:auto}.asset-scroll{max-height:180px}.preview-stage{height:300px}}
</style>
