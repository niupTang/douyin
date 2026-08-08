<template>
  <div class="agent-models-page">
    <header class="page-header">
      <div><p class="eyebrow">Hermes Gateway</p><h1>Agent 模型</h1><p>配置连接并指定爆款拆解使用的模型。</p></div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </header>

    <section class="settings-section">
      <div class="section-heading">
        <div><h2>Gateway 连接</h2><p>连接信息只保存在当前电脑。</p></div>
        <el-tag :type="connectionStatus.type" effect="plain">{{ connectionStatus.label }}</el-tag>
      </div>
      <el-form :model="hermesForm" label-position="top" class="connection-form">
        <el-form-item label="Gateway 地址"><el-input v-model="hermesForm.gatewayUrl" /></el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="hermesForm.apiKey" type="password" show-password :placeholder="hermesForm.apiKeyConfigured ? '已配置，留空保持不变' : 'API Server Key'" />
        </el-form-item>
        <el-form-item label="超时（秒）"><el-input-number v-model="hermesForm.timeout" :min="10" :max="1800" :step="10" /></el-form-item>
      </el-form>
      <div class="section-actions">
        <el-button type="primary" :loading="savingConnection" @click="saveConnection">保存连接</el-button>
        <el-button :loading="testingConnection" @click="testConnection">测试连接</el-button>
        <el-button :icon="Refresh" :loading="discovering" @click="discoverModels(true)">刷新模型目录</el-button>
      </div>
    </section>

    <section class="settings-section">
      <div class="section-heading">
        <div><h2>模型配置</h2><p>可从 Gateway 目录选择，也可手动填写。</p></div>
        <el-button type="primary" :icon="Plus" @click="openEditor()">添加模型</el-button>
      </div>
      <el-table :data="models" v-loading="loading" empty-text="还没有配置 Agent 模型">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="provider" label="Provider" min-width="130" />
        <el-table-column prop="model" label="Model" min-width="220" show-overflow-tooltip />
        <el-table-column label="推理" width="90"><template #default="s">{{ s.row.reasoningEffort || '默认' }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="s"><el-tag :type="s.row.enabled ? 'success' : 'info'" effect="plain">{{ s.row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="210" fixed="right"><template #default="s">
          <el-button link type="primary" :loading="testingModelId === s.row.id" @click="testModel(s.row)">测试</el-button>
          <el-button link @click="openEditor(s.row)">编辑</el-button>
          <el-button link type="danger" @click="removeModel(s.row)">删除</el-button>
        </template></el-table-column>
      </el-table>
    </section>

    <section class="settings-section">
      <div class="section-heading"><div><h2>任务模型</h2><p>开始新任务时读取，切换不会改变历史结果。</p></div></div>
      <div class="task-row">
        <div><strong>爆款拆解</strong><span>正文结构、传播机制与内容机会</span></div>
        <el-select v-model="taskModels.viralAnalysis" placeholder="选择 Agent 模型" clearable>
          <el-option v-for="item in enabledModels" :key="item.id" :label="`${item.name} · ${item.model}`" :value="item.id" />
        </el-select>
        <el-button type="primary" :loading="savingTask" @click="saveTaskModel">保存</el-button>
      </div>
    </section>

    <el-dialog v-model="editorVisible" :title="editingId ? '编辑 Agent 模型' : '添加 Agent 模型'" width="560px">
      <el-form :model="editor" label-position="top">
        <el-form-item v-if="discoveredModels.length" label="Gateway 模型目录">
          <el-select v-model="catalogSelection" filterable clearable placeholder="选择后自动填写" @change="applyCatalogModel">
            <el-option v-for="item in discoveredModels" :key="`${item.provider}:${item.model}`" :label="`${item.provider} · ${item.name}`" :value="`${item.provider}\n${item.model}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称"><el-input v-model="editor.name" placeholder="例如：高质量拆解" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="Provider"><el-input v-model="editor.provider" placeholder="例如：openrouter" /></el-form-item>
          <el-form-item label="Model"><el-input v-model="editor.model" placeholder="模型 ID" /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="推理强度"><el-select v-model="editor.reasoningEffort"><el-option label="Gateway 默认" value="" /><el-option label="Low" value="low" /><el-option label="Medium" value="medium" /><el-option label="High" value="high" /></el-select></el-form-item>
          <el-form-item label="服务等级"><el-input v-model="editor.serviceTier" placeholder="留空使用默认" /></el-form-item>
        </div>
        <el-form-item label="启用"><el-switch v-model="editor.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editorVisible = false">取消</el-button><el-button type="primary" :loading="savingModel" @click="saveModel">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { agentModelsApi } from '@/api/agentModels'

const loading = ref(false), savingConnection = ref(false), testingConnection = ref(false)
const discovering = ref(false), savingModel = ref(false), savingTask = ref(false)
const testingModelId = ref(''), editorVisible = ref(false), editingId = ref(''), catalogSelection = ref('')
const models = ref([]), discoveredModels = ref([])
const taskModels = reactive({ viralAnalysis: '' })
const connectionStatus = reactive({ type: 'info', label: '未测试' })
const hermesForm = reactive({ gatewayUrl: 'http://127.0.0.1:8642', apiKey: '', apiKeyConfigured: false, timeout: 300 })
const emptyEditor = () => ({ name: '', provider: '', model: '', reasoningEffort: '', serviceTier: '', enabled: true })
const editor = reactive(emptyEditor())
const enabledModels = computed(() => models.value.filter((item) => item.enabled))

const flattenCatalog = (payload) => {
  const found = new Map()
  const walk = (value, inherited = '') => {
    if (Array.isArray(value)) return value.forEach((item) => walk(item, inherited))
    if (!value || typeof value !== 'object') return
    const provider = String(value.provider || value.provider_id || value.slug || inherited || '')
    if (Array.isArray(value.models)) value.models.forEach((item) => {
      const model = typeof item === 'string' ? item : String(item?.id || item?.model || item?.name || '')
      const name = typeof item === 'string' ? item : String(item?.name || item?.label || model)
      if (provider && model) found.set(`${provider}:${model}`, { provider, model, name })
    })
    Object.values(value).forEach((item) => walk(item, provider))
  }
  walk(payload)
  return [...found.values()]
}

const loadAll = async () => {
  loading.value = true
  try {
    const [hermes, configured] = await Promise.all([agentModelsApi.getHermesSettings(), agentModelsApi.getAgentModels()])
    Object.assign(hermesForm, hermes.data, { apiKey: '' })
    models.value = configured.data.models || []
    Object.assign(taskModels, configured.data.taskModels || {})
  } finally { loading.value = false }
}
const saveConnection = async () => {
  savingConnection.value = true
  try { const r = await agentModelsApi.saveHermesSettings(hermesForm); Object.assign(hermesForm, r.data, { apiKey: '' }); ElMessage.success('连接已保存') } finally { savingConnection.value = false }
}
const testConnection = async () => {
  testingConnection.value = true
  try { await agentModelsApi.testHermes(); Object.assign(connectionStatus, { type: 'success', label: '连接正常' }); ElMessage.success('Hermes Gateway 连接正常') }
  catch { Object.assign(connectionStatus, { type: 'danger', label: '连接失败' }) }
  finally { testingConnection.value = false }
}
const discoverModels = async (refresh = false) => {
  discovering.value = true
  try { const r = await agentModelsApi.discoverModels(refresh); discoveredModels.value = flattenCatalog(r.data); ElMessage.success(`已读取 ${discoveredModels.value.length} 个模型`) }
  finally { discovering.value = false }
}
const openEditor = (model = null) => { editingId.value = model?.id || ''; Object.assign(editor, emptyEditor(), model || {}); catalogSelection.value = ''; editorVisible.value = true }
const applyCatalogModel = (value) => {
  if (!value) return
  const [provider, model] = value.split('\n'), selected = discoveredModels.value.find((x) => x.provider === provider && x.model === model)
  Object.assign(editor, { provider, model, name: editor.name || selected?.name || model })
}
const saveModel = async () => {
  if (!editor.name.trim() || !editor.provider.trim() || !editor.model.trim()) return ElMessage.warning('请填写名称、Provider 和 Model')
  savingModel.value = true
  try { editingId.value ? await agentModelsApi.updateAgentModel(editingId.value, editor) : await agentModelsApi.createAgentModel(editor); editorVisible.value = false; await loadAll(); ElMessage.success('Agent 模型已保存') }
  finally { savingModel.value = false }
}
const removeModel = async (model) => { await ElMessageBox.confirm(`确定删除“${model.name}”吗？`, '删除模型', { type: 'warning' }); await agentModelsApi.deleteAgentModel(model.id); await loadAll(); ElMessage.success('模型已删除') }
const testModel = async (model) => { testingModelId.value = model.id; try { const r = await agentModelsApi.testAgentModel(model.id); ElMessage.success(`测试成功，耗时 ${r.data.elapsedMs} ms`) } finally { testingModelId.value = '' } }
const saveTaskModel = async () => { savingTask.value = true; try { await agentModelsApi.saveTaskModels(taskModels); ElMessage.success('爆款拆解模型已保存') } finally { savingTask.value = false } }
onMounted(loadAll)
</script>

<style lang="scss" scoped>
.agent-models-page { max-width: 1180px; margin: 0 auto; color: #20242c; }
.page-header, .section-heading, .task-row { display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.page-header { margin-bottom: 28px; } .page-header p, .section-heading p { margin: 6px 0 0; color: #737985; }
.eyebrow { color: #53715d !important; font-size: 12px; font-weight: 700; text-transform: uppercase; }
h1 { margin: 0; font-size: 30px; letter-spacing: 0; } h2 { margin: 0; font-size: 18px; letter-spacing: 0; }
.settings-section { padding: 24px 0; border-top: 1px solid #e1e4e8; } .section-heading { margin-bottom: 20px; }
.connection-form { display: grid; grid-template-columns: 2fr 1.5fr 160px; gap: 18px; } .connection-form :deep(.el-form-item) { margin-bottom: 4px; }
.section-actions { display: flex; gap: 10px; margin-top: 18px; }
.task-row > div { display: flex; flex-direction: column; gap: 5px; min-width: 220px; } .task-row span { color: #737985; font-size: 13px; }
.task-row .el-select { width: min(460px, 100%); margin-left: auto; } .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 800px) { .connection-form, .form-grid { grid-template-columns: 1fr; } .page-header, .section-heading, .task-row { align-items: stretch; flex-direction: column; } .task-row .el-select { width: 100%; margin-left: 0; } .section-actions { flex-wrap: wrap; } }
</style>
