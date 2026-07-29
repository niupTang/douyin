<template>
  <div class="studio">
    <header class="hero">
      <div>
        <span>CONTENT PIPELINE</span>
        <h1>口播生产工作台</h1>
        <p>文案同步、手机提词、自动剪辑和发布资料在一个项目中流转。</p>
      </div>
      <div class="hero-actions">
        <el-button size="large" @click="setAdminToken">设置管理员令牌</el-button>
        <el-button type="primary" size="large" @click="createProject">新建口播项目</el-button>
      </div>
    </header>

    <div class="layout">
      <aside class="project-list">
        <div class="section-title"><strong>项目</strong><span>{{ projects.length }}</span></div>
        <button
          v-for="item in projects"
          :key="item.id"
          :class="{ active: item.id === selected?.id }"
          @click="selectProject(item)"
        >
          <strong>{{ item.title || item.topic || '未命名项目' }}</strong>
          <small>V{{ item.script_version }} · {{ statusLabel[item.status] || item.status }}</small>
        </button>
        <el-empty v-if="!projects.length" description="还没有口播项目" :image-size="72" />
      </aside>

      <main class="editor">
        <template v-if="selected">
          <div class="editor-head">
            <div><span>当前项目</span><h2>{{ selected.title || selected.topic || '未命名项目' }}</h2></div>
            <el-tag effect="dark">{{ statusLabel[selected.status] || selected.status }}</el-tag>
          </div>
          <label class="script-label">口播文案</label>
          <el-input
            v-model="script"
            type="textarea"
            :rows="15"
            resize="vertical"
            placeholder="粘贴 AI 生成的口播文案"
          />
          <div class="actions">
            <el-button type="primary" :loading="saving" @click="syncScript">保存并同步手机</el-button>
            <el-button @click="generateBindingCode">生成手机绑定码</el-button>
          </div>
          <div v-if="bindingCode" class="binding-code">
            <span>在手机提词器中输入以下一次性绑定码</span>
            <code>{{ bindingCode }}</code>
          </div>
          <section class="template-section">
            <div><strong>选择剪辑模板</strong><span>原片上传后创建 Windows 剪辑任务</span></div>
            <div class="templates">
              <button :class="{ active: template === 'knowledge' }" @click="template = 'knowledge'">
                <b>知识干货</b><small>快节奏 · 黄白字幕 · 信息型 B-roll</small>
              </button>
              <button :class="{ active: template === 'business' }" @click="template = 'business'">
                <b>商业观点</b><small>黑金视觉 · 金句卡片 · 电影感调色</small>
              </button>
            </div>
            <el-button :disabled="selected.status !== 'uploaded'" @click="submitEdit">
              创建剪辑任务
            </el-button>
          </section>
          <section class="template-section">
            <div><strong>口播封面</strong><span>输出 1080 × 1920 PNG</span></div>
            <el-input v-model="coverTitle" placeholder="输入封面标题" />
            <div class="cover-actions">
              <el-button :loading="covering" @click="generateCover">生成对应模板封面</el-button>
              <a v-if="coverUrl" :href="coverUrl" target="_blank" rel="noreferrer">打开封面预览</a>
            </div>
            <img v-if="coverUrl" class="cover-preview" :src="coverUrl" alt="生成的口播封面" />
          </section>
          <section class="publish-ready">
            <div><strong>审核与发布</strong><span>确认成片和封面后交给现有发布中心</span></div>
            <el-button type="success" @click="sendToPublish">审核通过，送到发布中心</el-button>
          </section>
        </template>
        <el-empty v-else description="新建或选择一个项目开始" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { kouboApi } from '@/api/koubo'

const projects = ref([])
const selected = ref(null)
const script = ref('')
const saving = ref(false)
const bindingCode = ref('')
const template = ref('knowledge')
const coverTitle = ref('')
const covering = ref(false)
const coverUrl = ref('')
const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
const router = useRouter()

const statusLabel = {
  draft: '文案草稿',
  synced: '已同步',
  uploaded: '原片已上传',
  waiting_edit: '等待剪辑',
  editing: '剪辑中',
  waiting_cover: '待封面',
  edit_failed: '剪辑失败'
}

async function loadProjects() {
  const response = await kouboApi.listProjects()
  projects.value = response.data || []
  if (selected.value) {
    const latest = projects.value.find((item) => item.id === selected.value.id)
    if (latest) selectProject(latest)
  } else if (projects.value.length) {
    selectProject(projects.value[0])
  }
}

async function setAdminToken() {
  const { value } = await ElMessageBox.prompt('输入服务器配置的 KOUBO_ADMIN_TOKEN', '管理员令牌', {
    confirmButtonText: '保存',
    cancelButtonText: '取消',
    inputType: 'password'
  })
  localStorage.setItem('token', value)
  await loadProjects()
  ElMessage.success('管理员令牌已保存到当前浏览器')
}

function selectProject(project) {
  selected.value = project
  script.value = project.script || ''
  template.value = project.edit_template || 'knowledge'
  bindingCode.value = ''
  coverTitle.value = project.title || project.topic || ''
  coverUrl.value = ''
}

async function createProject() {
  const { value } = await ElMessageBox.prompt('输入本条口播的主题', '新建口播项目', {
    confirmButtonText: '创建',
    cancelButtonText: '取消',
    inputPlaceholder: '例如：普通人如何用 AI 提升效率'
  })
  const response = await kouboApi.createProject({ topic: value, title: value, script: '' })
  await loadProjects()
  selectProject(response.data)
}

async function syncScript() {
  if (!script.value.trim()) return ElMessage.warning('请先输入口播文案')
  saving.value = true
  try {
    const response = await kouboApi.updateScript(selected.value.id, script.value)
    selected.value = response.data
    ElMessage.success('文案已同步到手机')
    await loadProjects()
  } finally {
    saving.value = false
  }
}

async function generateBindingCode() {
  const response = await kouboApi.createBindingCode()
  bindingCode.value = response.data.code
}

async function submitEdit() {
  await kouboApi.createEditJob(selected.value.id, template.value)
  ElMessage.success('剪辑任务已创建')
  await loadProjects()
}

async function generateCover() {
  if (!coverTitle.value.trim()) return ElMessage.warning('请输入封面标题')
  covering.value = true
  try {
    const response = await kouboApi.createCover(selected.value.id, {
      title: coverTitle.value,
      template: template.value
    })
    const token = encodeURIComponent(localStorage.getItem('token') || '')
    coverUrl.value = `${apiBase}/api/koubo/assets/${response.data.id}/content?token=${token}`
    ElMessage.success('封面已生成')
  } finally {
    covering.value = false
  }
}

async function sendToPublish() {
  try {
    const response = await kouboApi.approveProject(selected.value.id)
    localStorage.setItem('koubo_publish_draft', JSON.stringify(response.data))
    ElMessage.success('已通过审核，正在打开发布中心')
    router.push('/publish-center')
  } catch (error) {
    // 统一请求层已经显示具体原因
  }
}

onMounted(loadProjects)
</script>

<style scoped lang="scss">
.studio { color:#18202d; }
.hero { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; padding:28px 30px; border-radius:18px; color:#fff; background:linear-gradient(125deg,#111827,#252019); }
.hero span { color:#f2c94c; font-size:11px; font-weight:800; letter-spacing:.18em; }
.hero h1 { margin:8px 0; font-size:30px; }
.hero p { margin:0; color:#b7bec9; }
.hero-actions { display:flex; gap:10px; }
.layout { display:grid; grid-template-columns:280px 1fr; gap:18px; margin-top:18px; }
.project-list,.editor { min-height:600px; border:1px solid #e5e8ed; border-radius:16px; background:#fff; }
.project-list { padding:14px; }
.section-title { display:flex; justify-content:space-between; padding:8px; }
.project-list button { display:grid; width:100%; gap:6px; margin-top:6px; border:0; border-radius:12px; padding:14px; text-align:left; background:#f5f7fa; color:#253041; }
.project-list button.active { color:#fff; background:#1b1f27; }
.project-list small { color:#8a93a2; }
.editor { padding:28px; }
.editor-head { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:22px; }
.editor-head span,.script-label { color:#8a93a2; font-size:12px; }
.editor-head h2 { margin:5px 0 0; }
.script-label { display:block; margin-bottom:8px; }
.actions { display:flex; gap:10px; margin-top:16px; }
.binding-code { display:grid; gap:8px; margin-top:16px; border:1px solid #ead996; border-radius:12px; padding:14px; background:#fff9df; }
.binding-code code { word-break:break-all; font-size:17px; font-weight:800; }
.template-section { display:grid; gap:14px; margin-top:30px; padding-top:24px; border-top:1px solid #eceef2; }
.template-section > div:first-child { display:flex; justify-content:space-between; }
.template-section span { color:#8a93a2; font-size:12px; }
.templates { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.templates button { display:grid; gap:8px; border:1px solid #e1e5eb; border-radius:12px; padding:16px; text-align:left; background:#fff; }
.templates button.active { border-color:#d7ad27; background:#fffaf0; box-shadow:0 0 0 2px #f2c94c33; }
.templates small { color:#7b8492; }
.cover-actions { display:flex; align-items:center; gap:16px; }
.cover-actions a { color:#9a7412; font-size:13px; }
.cover-preview { width:240px; max-width:100%; border-radius:14px; box-shadow:0 16px 36px #11182726; }
.publish-ready { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-top:28px; border:1px solid #bde4cd; border-radius:14px; padding:18px; background:#f1fbf5; }
.publish-ready div { display:grid; gap:5px; }
.publish-ready span { color:#688075; font-size:12px; }
@media (max-width:900px) { .layout { grid-template-columns:1fr; }.project-list { min-height:auto; }.hero { align-items:flex-start; flex-direction:column; } }
</style>
