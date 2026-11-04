<template>
  <div class="agent-models-page">
    <header class="page-header">
      <div><p class="eyebrow">Unified AI Runtime</p><h1>Agent 模型路由</h1><p>按 Provider、模型配置和 Agent 路由三层管理。</p></div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </header>

    <el-alert v-if="migrationStatus.status === 'failed'" class="migration-alert" type="warning" :closable="false" show-icon title="旧配置未自动迁移">
      <template #default>{{ migrationStatus.message }}。新版配置区仍可正常使用；修正旧 settings.json 后重启即可重试。</template>
    </el-alert>

    <section class="settings-section">
      <div class="section-heading"><div><h2>1. Provider</h2><p>每个服务独立保存地址、能力和加密凭据。</p></div><el-button type="primary" :icon="Plus" @click="openProviderEditor()">添加 Provider</el-button></div>
      <el-table :data="providers" v-loading="loading" empty-text="还没有 Provider">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="类型" width="170"><template #default="s">{{ providerTypeLabel(s.row.provider_type) }}</template></el-table-column>
        <el-table-column label="地址" min-width="260" show-overflow-tooltip><template #default="s">{{ s.row.base_url || '本机 CLI' }}</template></el-table-column>
        <el-table-column label="密钥" width="100"><template #default="s"><el-tag :type="s.row.credentialConfigured ? 'success' : 'info'" effect="plain">{{ s.row.credentialConfigured ? '已配置' : '未配置' }}</el-tag></template></el-table-column>
        <el-table-column label="连接" width="100"><template #default="s"><el-tag v-if="connectionResults[s.row.id]" :type="connectionResults[s.row.id].connected ? 'success' : 'danger'" :title="connectionResults[s.row.id].message" effect="plain">{{ connectionResults[s.row.id].connected ? '通过' : '失败' }}</el-tag><span v-else>未测试</span></template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="s"><el-tag :type="s.row.enabled ? 'success' : 'info'" effect="plain">{{ s.row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="270" fixed="right"><template #default="s"><el-button v-if="s.row.provider_type !== 'codex_cli'" link type="primary" :loading="testingProviderIds.includes(s.row.id)" @click="testProvider(s.row)">测试连接</el-button><el-button link type="primary" @click="openProviderEditor(s.row)">编辑</el-button><el-button v-if="s.row.credentialConfigured" link @click="clearCredential(s.row)">清除密钥</el-button><el-button link type="danger" @click="removeProvider(s.row)">删除</el-button></template></el-table-column>
      </el-table>
    </section>

    <section class="settings-section">
      <div class="section-heading"><div><h2>2. 模型配置</h2><p>模型必须绑定一个 Provider，可设置独立推理参数。</p></div><el-button type="primary" :icon="Plus" :disabled="!providers.length" @click="openModelEditor()">添加模型</el-button></div>
      <el-table :data="models" v-loading="loading" empty-text="还没有模型配置">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="Provider" min-width="150"><template #default="s">{{ providerName(s.row.provider_id) }}</template></el-table-column>
        <el-table-column prop="model_name" label="Model" min-width="220" show-overflow-tooltip />
        <el-table-column label="推理" width="100"><template #default="s">{{ s.row.reasoning_effort || '默认' }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="s"><el-tag :type="s.row.enabled ? 'success' : 'info'" effect="plain">{{ s.row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="130" fixed="right"><template #default="s"><el-button link type="primary" @click="openModelEditor(s.row)">编辑</el-button><el-button link type="danger" @click="removeModel(s.row)">删除</el-button></template></el-table-column>
      </el-table>
    </section>

    <section class="settings-section">
      <div class="section-heading"><div><h2>3. Agent 路由</h2><p>每个 Agent 独立选择主模型和备用模型。</p></div></div>
      <el-table :data="agents" v-loading="loading" empty-text="还没有 Agent 配置">
        <el-table-column prop="name" label="Agent" min-width="150" />
        <el-table-column label="方式" width="110"><template #default="s"><el-tag effect="plain">{{ s.row.execution_mode === 'tool_loop' ? '工具循环' : '结构化' }}</el-tag></template></el-table-column>
        <el-table-column label="主模型" min-width="220"><template #default="s"><el-select v-model="s.row.primary_model_profile_id" clearable placeholder="选择主模型"><el-option v-for="item in enabledModels" :key="item.id" :label="modelLabel(item)" :value="item.id" /></el-select></template></el-table-column>
        <el-table-column label="备用模型" min-width="220"><template #default="s"><el-select v-model="s.row.fallback_model_profile_id" clearable placeholder="不使用备用模型"><el-option v-for="item in enabledModels" :key="item.id" :label="modelLabel(item)" :value="item.id" :disabled="item.id === s.row.primary_model_profile_id" /></el-select></template></el-table-column>
        <el-table-column label="超时" width="120"><template #default="s"><el-input-number v-model="s.row.timeout_seconds" :min="1" :max="3600" controls-position="right" /></template></el-table-column>
        <el-table-column label="启用" width="80"><template #default="s"><el-switch v-model="s.row.enabled" /></template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="s"><el-button link type="primary" :loading="savingAgentId === s.row.agent_key" @click="saveAgent(s.row)">保存</el-button></template></el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="providerEditorVisible" :title="editingProviderId ? '编辑 Provider' : '添加 Provider'" width="620px">
      <el-form :model="providerEditor" label-position="top">
        <div class="form-grid"><el-form-item label="名称"><el-input v-model="providerEditor.name" /></el-form-item><el-form-item label="类型"><el-select v-model="providerEditor.providerType"><el-option label="OpenAI Compatible" value="openai_compatible" /><el-option label="Hermes Gateway" value="hermes" /><el-option label="Codex CLI" value="codex_cli" /></el-select></el-form-item></div>
        <el-form-item v-if="providerEditor.providerType !== 'codex_cli'" label="服务地址"><el-input v-model="providerEditor.baseUrl" placeholder="https://api.example.com" /></el-form-item>
        <el-form-item v-if="providerEditor.providerType !== 'codex_cli'" label="API Key"><el-input v-model="providerEditor.apiKey" type="password" show-password :placeholder="editingProviderCredential ? '已配置，留空保持不变' : '输入 API Key'" /></el-form-item>
        <div class="form-grid"><el-form-item label="超时（秒）"><el-input-number v-model="providerEditor.timeoutSeconds" :min="1" :max="3600" /></el-form-item><el-form-item label="支持工具调用"><el-switch v-model="providerEditor.supportsTools" /></el-form-item></div>
        <el-form-item label="启用"><el-switch v-model="providerEditor.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="providerEditorVisible = false">取消</el-button><el-button type="primary" :loading="savingProvider" @click="saveProvider">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="modelEditorVisible" :title="editingModelId ? '编辑模型' : '添加模型'" width="620px">
      <el-form :model="modelEditor" label-position="top">
        <el-form-item label="Provider"><el-select v-model="modelEditor.providerId" filterable><el-option v-for="item in enabledProviders" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <div class="form-grid"><el-form-item label="显示名称"><el-input v-model="modelEditor.name" /></el-form-item><el-form-item label="Model"><el-input v-model="modelEditor.modelName" placeholder="模型 ID" /></el-form-item></div>
        <div class="form-grid"><el-form-item label="推理强度"><el-select v-model="modelEditor.reasoningEffort"><el-option label="默认" value="" /><el-option label="Low" value="low" /><el-option label="Medium" value="medium" /><el-option label="High" value="high" /><el-option label="XHigh" value="xhigh" /></el-select></el-form-item><el-form-item label="服务等级"><el-input v-model="modelEditor.serviceTier" /></el-form-item></div>
        <div class="form-grid"><el-form-item label="Temperature"><el-input-number v-model="modelEditor.temperature" :min="0" :max="2" :step="0.1" /></el-form-item><el-form-item label="Max Tokens"><el-input-number v-model="modelEditor.maxTokens" :min="1" /></el-form-item></div>
        <el-form-item label="启用"><el-switch v-model="modelEditor.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="modelEditorVisible = false">取消</el-button><el-button type="primary" :loading="savingModel" @click="saveModel">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { agentModelsApi } from '@/api/agentModels'

const loading = ref(false), savingAgentId = ref(''), savingProvider = ref(false), savingModel = ref(false)
const providers = ref([]), models = ref([]), agents = ref([])
const testingProviderIds = ref([])
const connectionResults = reactive({})
const migrationStatus = reactive({ status: 'pending', message: '' })
const providerEditorVisible = ref(false), modelEditorVisible = ref(false)
const editingProviderId = ref(''), editingModelId = ref(''), editingProviderCredential = ref(false)
const emptyProvider = () => ({ name: '', providerType: 'openai_compatible', baseUrl: '', apiKey: '', timeoutSeconds: 300, supportsTools: true, enabled: true })
const emptyModel = () => ({ providerId: '', name: '', modelName: '', reasoningEffort: '', serviceTier: '', temperature: null, maxTokens: null, enabled: true })
const providerEditor = reactive(emptyProvider()), modelEditor = reactive(emptyModel())
const enabledProviders = computed(() => providers.value.filter((item) => item.enabled))
const enabledModels = computed(() => models.value.filter((item) => item.enabled))
const providerTypeLabel = (type) => ({ hermes: 'Hermes Gateway', openai_compatible: 'OpenAI Compatible', codex_cli: 'Codex CLI' }[type] || type)
const providerName = (id) => providers.value.find((item) => item.id === id)?.name || 'Provider 不存在'
const modelLabel = (model) => `${model.name} · ${providerName(model.provider_id)}`

const testProvider = async (provider) => {
  if (testingProviderIds.value.includes(provider.id)) return
  testingProviderIds.value.push(provider.id)
  try {
    const result = await agentModelsApi.testProvider(provider.id)
    connectionResults[provider.id] = { connected: true, message: result.message }
    ElMessage.success(`${provider.name} 连接和鉴权通过`)
  } catch (error) {
    connectionResults[provider.id] = { connected: false, message: error.response?.data?.message || error.message }
  } finally {
    testingProviderIds.value = testingProviderIds.value.filter((id) => id !== provider.id)
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    const result = await Promise.allSettled([agentModelsApi.getProviders(), agentModelsApi.getRuntimeModelProfiles(), agentModelsApi.getAgentProfiles(), agentModelsApi.getMigrationStatus()])
    if (result[0].status === 'fulfilled') providers.value = result[0].value.data || []
    if (result[1].status === 'fulfilled') models.value = result[1].value.data || []
    if (result[2].status === 'fulfilled') agents.value = result[2].value.data || []
    if (result[3].status === 'fulfilled') Object.assign(migrationStatus, result[3].value.data || {})
    const failed = result.filter((item) => item.status === 'rejected').length
    if (failed) ElMessage.warning(`${failed} 个配置区块加载失败，其余配置仍可使用`)
  } finally { loading.value = false }
}

const openProviderEditor = (item = null) => {
  editingProviderId.value = item?.id || ''
  editingProviderCredential.value = Boolean(item?.credentialConfigured)
  Object.assign(providerEditor, emptyProvider(), item ? { name: item.name, providerType: item.provider_type, baseUrl: item.base_url || '', timeoutSeconds: item.timeout_seconds, supportsTools: item.capabilities?.tools !== false, enabled: item.enabled } : {})
  providerEditorVisible.value = true
}
const saveProvider = async () => {
  if (!providerEditor.name.trim()) return ElMessage.warning('请填写 Provider 名称')
  if (providerEditor.providerType !== 'codex_cli' && !providerEditor.baseUrl.trim()) return ElMessage.warning('请填写服务地址')
  savingProvider.value = true
  try {
    const payload = { name: providerEditor.name, providerType: providerEditor.providerType, baseUrl: providerEditor.baseUrl, timeoutSeconds: providerEditor.timeoutSeconds, capabilities: { tools: providerEditor.supportsTools }, enabled: providerEditor.enabled }
    const response = editingProviderId.value ? await agentModelsApi.updateProvider(editingProviderId.value, payload) : await agentModelsApi.createProvider(payload)
    if (providerEditor.apiKey.trim()) await agentModelsApi.saveProviderCredential(response.data.id, providerEditor.apiKey.trim())
    providerEditor.apiKey = ''
    delete connectionResults[response.data.id]
    providerEditorVisible.value = false
    await loadAll()
    ElMessage.success('Provider 已保存')
    if (response.data.provider_type !== 'codex_cli') await testProvider(response.data)
  } finally { savingProvider.value = false }
}
const clearCredential = async (item) => { await ElMessageBox.confirm(`确定清除“${item.name}”的 API Key 吗？`, '清除密钥', { type: 'warning' }); await agentModelsApi.clearProviderCredential(item.id); await loadAll(); ElMessage.success('API Key 已清除') }
const removeProvider = async (item) => { await ElMessageBox.confirm(`确定删除“${item.name}”吗？`, '删除 Provider', { type: 'warning' }); await agentModelsApi.deleteProvider(item.id); await loadAll(); ElMessage.success('Provider 已删除') }

const openModelEditor = (item = null) => {
  editingModelId.value = item?.id || ''
  Object.assign(modelEditor, emptyModel(), item ? { providerId: item.provider_id, name: item.name, modelName: item.model_name, reasoningEffort: item.reasoning_effort || '', serviceTier: item.service_tier || '', temperature: item.temperature, maxTokens: item.max_tokens, enabled: item.enabled } : { providerId: enabledProviders.value[0]?.id || '' })
  modelEditorVisible.value = true
}
const saveModel = async () => {
  if (!modelEditor.providerId || !modelEditor.name.trim() || !modelEditor.modelName.trim()) return ElMessage.warning('请选择 Provider，并填写名称和 Model')
  savingModel.value = true
  try {
    if (editingModelId.value) await agentModelsApi.updateModelProfile(editingModelId.value, modelEditor)
    else await agentModelsApi.createModelProfile(modelEditor)
    modelEditorVisible.value = false
    await loadAll()
    ElMessage.success('模型配置已保存')
  } finally { savingModel.value = false }
}
const removeModel = async (item) => { await ElMessageBox.confirm(`确定删除“${item.name}”吗？`, '删除模型', { type: 'warning' }); await agentModelsApi.deleteModelProfile(item.id); await loadAll(); ElMessage.success('模型配置已删除') }
const saveAgent = async (item) => {
  if (item.primary_model_profile_id && item.primary_model_profile_id === item.fallback_model_profile_id) return ElMessage.warning('主模型和备用模型不能相同')
  savingAgentId.value = item.agent_key
  try { await agentModelsApi.saveAgentProfile(item.agent_key, item); await loadAll(); ElMessage.success(`${item.name} 的路由已保存`) } finally { savingAgentId.value = '' }
}
onMounted(loadAll)
</script>

<style lang="scss" scoped>
.agent-models-page { max-width: 1280px; margin: 0 auto; color: #20242c; }
.page-header, .section-heading { display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.page-header { margin-bottom: 28px; } .page-header p, .section-heading p { margin: 6px 0 0; color: #737985; }
.eyebrow { color: #53715d !important; font-size: 12px; font-weight: 700; text-transform: uppercase; }
h1 { margin: 0; font-size: 30px; } h2 { margin: 0; font-size: 18px; }
.settings-section { padding: 24px 0; border-top: 1px solid #e1e4e8; } .section-heading { margin-bottom: 20px; }
.migration-alert { margin-bottom: 24px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; } .el-select { width: 100%; }
@media (max-width: 800px) { .form-grid { grid-template-columns: 1fr; } .page-header, .section-heading { align-items: stretch; flex-direction: column; } }
</style>
