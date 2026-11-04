<template>
  <div class="chat-workbench">
    <aside class="conversation-panel">
      <el-button type="primary" plain :disabled="sending || uploading || publishing" @click="newConversation">＋ 新建对话</el-button>
      <div class="conversation-list">
        <button v-for="item in conversations" :key="item.id" :class="{ active: item.id === activeId }"
          :disabled="sending || uploading || publishing" @click="selectConversation(item.id)">{{ item.title }}</button>
      </div>
      <el-button text @click="router.push('/agent-models')">配置 Agent 模型</el-button>
    </aside>

    <section class="chat-panel">
      <header class="chat-header">
        <div><h1>聊天工作台</h1><p>查询数据、同步账号、上传与发布视频</p></div>
        <el-button text @click="router.push('/overview')">数据总览</el-button>
      </header>

      <div ref="messageList" class="message-list" aria-live="polite" v-loading="loading">
        <div v-if="!messages.length" class="welcome">
          <span class="welcome-mark">↗</span>
          <h2>今天想完成什么？</h2>
          <p>直接告诉我你的需求，我会调用业务工具执行。</p>
          <div class="suggestions">
            <button v-for="suggestion in suggestions" :key="suggestion" @click="prompt = suggestion">{{ suggestion }}</button>
          </div>
        </div>
        <article v-for="message in messages" :key="message.id" class="message" :class="message.role">
          <div class="message-label">{{ message.role === 'user' ? '你' : 'Sunbird' }}
            <el-tag v-if="message.status !== 'succeeded'" size="small" :type="statusType(message.status)">{{ statusLabel(message.status) }}</el-tag>
          </div>
          <MarkdownContent v-if="message.role === 'assistant'" class="message-body"
            :content="message.content || (busyStatus(message.status) ? '正在处理…' : '暂无回复')" />
          <div v-else class="message-body">{{ message.content }}</div>
          <div v-if="message.kind === 'publish'" class="publish-summary">
            <span>{{ platformNames[message.payload.platform_type] }} · {{ message.payload.accounts?.join('、') }}</span>
            <span>{{ message.payload.title }}</span>
            <span>{{ message.payload.files?.join('、') }}</span>
          </div>
          <el-collapse v-if="message.events?.length" class="execution-details">
            <el-collapse-item title="查看执行过程">
              <div v-for="event in message.events" :key="event.id" class="execution-event">
                {{ eventLabel(event) }}
              </div>
            </el-collapse-item>
          </el-collapse>
          <el-button v-if="message.kind === 'upload'" text type="primary"
            @click="openPublish(message.payload.material_id)">发布这个视频</el-button>
        </article>
      </div>

      <section v-if="publishVisible" class="publish-card">
        <div class="card-heading"><strong>视频发布确认</strong><el-button text :disabled="publishing" @click="publishVisible = false">收起</el-button></div>
        <el-form label-position="top" :disabled="publishing">
          <div class="publish-fields">
            <el-form-item label="发布平台">
              <el-select v-model="publishForm.platform" @change="publishForm.account_ids = []">
                <el-option v-for="(name, type) in platformNames" :key="type" :label="name" :value="Number(type)" />
              </el-select>
            </el-form-item>
            <el-form-item label="发布账号">
              <el-select v-model="publishForm.account_ids" multiple placeholder="选择已登录账号">
                <el-option v-for="account in platformAccounts" :key="account.id" :value="account.id" :label="account.name" :disabled="account.status !== 1" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="视频素材">
            <el-select v-model="publishForm.material_ids" multiple filterable placeholder="选择已上传的视频">
              <el-option v-for="material in videoMaterials" :key="material.id" :value="material.id" :label="material.filename" />
            </el-select>
          </el-form-item>
          <div class="publish-fields">
            <el-form-item label="发布标题"><el-input v-model="publishForm.title" maxlength="200" show-word-limit /></el-form-item>
            <el-form-item label="话题（逗号分隔）"><el-input v-model="publishForm.tags" placeholder="AI,自动化" /></el-form-item>
          </div>
        </el-form>
        <div class="publish-actions"><span>确认后会将视频发布到所选账号。</span><el-button type="primary" :loading="publishing" @click="confirmPublish">确认发布</el-button></div>
      </section>

      <footer class="composer">
        <el-input v-model="prompt" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" maxlength="12000"
          placeholder="例如：查询最近的发布记录，或同步对标账号… Enter 发送，Shift+Enter 换行"
          @keydown.enter="onEnter" />
        <div class="composer-actions">
          <div>
            <input ref="fileInput" type="file" accept=".mp4,.mov,.mkv,.avi,.webm,.m4v" hidden @change="uploadVideo" />
            <el-button :loading="uploading" :disabled="sending || publishing" @click="fileInput?.click()">上传视频</el-button>
            <el-button :disabled="uploading || publishing" @click="openPublish()">发布视频</el-button>
          </div>
          <el-button v-if="agentRunning" :loading="cancelling" @click="cancelRun">停止任务</el-button>
          <el-button v-else type="primary" :loading="sending" :disabled="!prompt.trim() || uploading || busy" @click="send">发送</el-button>
        </div>
        <p v-if="pollError" class="connection-error">{{ pollError }} <el-button text type="primary" @click="refreshMessages">重试</el-button></p>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { chatApi } from '@/api/chat'
import MarkdownContent from '@/components/MarkdownContent.vue'

const router = useRouter()
const conversations = ref([])
const messages = ref([])
const activeId = ref('')
const prompt = ref('')
const loading = ref(false)
const sending = ref(false)
const uploading = ref(false)
const publishing = ref(false)
const cancelling = ref(false)
const pollError = ref('')
const fileInput = ref(null)
const messageList = ref(null)
const publishVisible = ref(false)
const options = ref({ accounts: [], materials: [] })
const publishForm = reactive({ platform: 3, account_ids: [], material_ids: [], title: '', tags: '' })
const platformNames = { 1: '小红书', 2: '视频号', 3: '抖音', 4: '快手' }
const platformAccounts = computed(() => options.value.accounts.filter(a => a.type === publishForm.platform))
const videoMaterials = computed(() => options.value.materials.filter(m => /\.(mp4|mov|mkv|avi|webm|m4v)$/i.test(m.filename)))
const suggestions = ['查询我的账号和登录状态', '查看最近 10 条发布记录', '列出对标账号及最近同步时间', '查询素材库中的视频']
const busyStatus = status => ['queued', 'running'].includes(status)
const busy = computed(() => messages.value.some(m => busyStatus(m.status)))
const agentRunning = computed(() => messages.value.some(m => m.run_id && busyStatus(m.status)))
const statusLabel = status => ({ queued: '排队中', running: '执行中', failed: '失败', cancelled: '已停止', interrupted: '已中断' })[status] || status
const statusType = status => ['failed', 'interrupted'].includes(status) ? 'danger' : 'info'
const eventLabel = event => {
  const names = { model_call: '正在分析需求', tool_call: '调用工具', tool_result: '工具执行', run_started: '任务开始', run_succeeded: '任务完成', run_failed: '任务失败', run_cancelled: '任务停止', model_fallback: '切换备用模型' }
  return `${names[event.event_type] || event.event_type}${event.payload?.tool ? `：${event.payload.tool}` : ''}${event.payload?.ok === false ? '（失败）' : ''}`
}
let timer = null
let disposed = false
let refreshing = false
let publishRequestId = ''
const storageKey = 'sunbird-chat-conversation'
const stopPolling = () => { clearTimeout(timer); timer = null }
const scrollBottom = async () => { await nextTick(); if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight }
const loadConversations = async () => { conversations.value = (await chatApi.list()).data || [] }

const refreshMessages = async () => {
  if (!activeId.value || disposed) return
  if (refreshing) {
    stopPolling()
    timer = setTimeout(refreshMessages, 300)
    return
  }
  const id = activeId.value
  refreshing = true
  stopPolling()
  try {
    const response = await chatApi.messages(id)
    if (disposed || id !== activeId.value) return
    const nearBottom = !messageList.value || messageList.value.scrollHeight - messageList.value.scrollTop - messageList.value.clientHeight < 100
    messages.value = response.data || []
    pollError.value = ''
    if (nearBottom) await scrollBottom()
    if (busy.value) timer = setTimeout(refreshMessages, 1500)
  } catch (error) {
    if (!disposed && id === activeId.value) pollError.value = '进度读取失败，任务可能仍在后台运行。请重试查看。'
  } finally { refreshing = false }
}

const selectConversation = async (id) => {
  stopPolling()
  activeId.value = id
  localStorage.setItem(storageKey, id)
  publishVisible.value = false
  messages.value = []
  loading.value = true
  try {
    // A pending request for the previous conversation is allowed to finish first.
    const response = await chatApi.messages(id)
    if (disposed || activeId.value !== id) return
    messages.value = response.data || []
    pollError.value = ''
    await scrollBottom()
    if (busy.value) timer = setTimeout(refreshMessages, 1500)
  } catch (error) { pollError.value = '读取对话失败，请重试。' }
  finally { if (activeId.value === id) loading.value = false }
}

const newConversation = async () => {
  try {
    const response = await chatApi.create()
    await loadConversations()
    await selectConversation(response.data.id)
  } catch (error) { ElMessage.error(error.message || '新建对话失败') }
}
const ensureConversation = async () => {
  if (!activeId.value) await newConversation()
  if (!activeId.value) throw new Error('请先建立对话')
  return activeId.value
}
const send = async () => {
  if (sending.value || busy.value || !prompt.value.trim()) return
  const text = prompt.value.trim()
  sending.value = true
  try {
    const id = await ensureConversation()
    const response = await chatApi.send(id, text)
    messages.value = response.data || []
    prompt.value = ''
    await scrollBottom()
    await loadConversations()
    if (busy.value) timer = setTimeout(refreshMessages, 1000)
  } catch (error) {
    ElMessage.error(error.message || '发送失败，请检查 Agent 模型配置')
    await refreshMessages()
  } finally { sending.value = false }
}
const onEnter = event => {
  if (!event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); send() }
}
const cancelRun = async () => {
  cancelling.value = true
  try { await chatApi.cancel(activeId.value); await refreshMessages() }
  catch (error) { ElMessage.error(error.message || '停止任务失败，请重新查看进度') }
  finally { cancelling.value = false }
}
const uploadVideo = async event => {
  const file = event.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const id = await ensureConversation()
    const response = await chatApi.upload(id, file)
    await refreshMessages()
    await scrollBottom()
    await openPublish(response.data.material_id)
    ElMessage.success('视频已上传到素材库')
  } catch (error) { ElMessage.error(error.message || '视频上传失败') }
  finally { uploading.value = false; event.target.value = '' }
}
const openPublish = async materialId => {
  try {
    options.value = (await chatApi.options()).data
    if (materialId) publishForm.material_ids = [materialId]
    publishRequestId = crypto.randomUUID().replaceAll('-', '')
    publishVisible.value = true
    await scrollBottom()
  } catch (error) { ElMessage.error(error.message || '读取发布选项失败') }
}
const confirmPublish = async () => {
  if (publishing.value) return
  if (!publishForm.title.trim() || !publishForm.account_ids.length || !publishForm.material_ids.length) {
    return ElMessage.warning('请填写标题并选择账号、视频')
  }
  publishing.value = true
  try {
    const id = await ensureConversation()
    await chatApi.publish(id, {
      request_id: publishRequestId, confirmed: true, title: publishForm.title,
      account_ids: [...publishForm.account_ids], material_ids: [...publishForm.material_ids],
      tags: publishForm.tags.split(/[,，]/).map(t => t.trim()).filter(Boolean)
    })
    publishVisible.value = false
    publishForm.material_ids = []
    publishForm.title = ''
    await refreshMessages()
    await scrollBottom()
  } catch (error) { ElMessage.error(error.message || '提交发布失败') }
  finally { publishing.value = false }
}
onMounted(async () => {
  try {
    await loadConversations()
    const previous = localStorage.getItem(storageKey)
    const id = conversations.value.find(c => c.id === previous)?.id || conversations.value[0]?.id
    if (id) await selectConversation(id)
  } catch (error) { pollError.value = '聊天服务连接失败，请确认后端已经更新并启动。' }
})
onBeforeUnmount(() => { disposed = true; stopPolling() })
</script>

<style scoped>
.chat-workbench { display: flex; min-height: 640px; height: calc(100dvh - 136px); background: #fff; border: 1px solid #e7ecf3; border-radius: 16px; overflow: hidden; }
.conversation-panel { width: 208px; flex-shrink: 0; padding: 20px 12px; background: #f8fafc; border-right: 1px solid #e7ecf3; display: flex; flex-direction: column; gap: 14px; }
.conversation-list { flex: 1; overflow: auto; }
.conversation-list button { display: block; width: 100%; padding: 12px; margin-bottom: 4px; border: 0; border-radius: 8px; text-align: left; background: transparent; color: #596a80; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conversation-list button.active { color: #2168c6; background: #eaf2ff; }
.chat-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.chat-header { padding: 20px 28px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eef1f5; }
h1 { margin: 0; font-size: 22px; color: #263b56; }
.chat-header p { margin: 6px 0 0; color: #8895a7; font-size: 13px; }
.message-list { flex: 1; overflow-y: auto; padding: 24px 32px; }
.welcome { max-width: 650px; margin: 50px auto; text-align: center; }
.welcome-mark { display: inline-grid; place-items: center; width: 54px; height: 54px; border-radius: 16px; background: #edf4ff; color: #3a7de0; font-size: 32px; }
.welcome h2 { color: #263b56; }.welcome p { color: #8895a7; font-size: 14px; }
.suggestions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 28px; }
.suggestions button { padding: 16px; border: 1px solid #e5ebf4; border-radius: 10px; color: #566a84; background: #fff; text-align: left; cursor: pointer; }
.suggestions button:hover { background: #f4f8ff; border-color: #b8d2f5; }
.message { max-width: 850px; margin: 0 auto 24px; }.message-label { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: #7b8b9e; margin-bottom: 8px; }
.message-body { overflow-wrap: anywhere; line-height: 1.8; color: #34465d; font-size: 14px; }
.message.user .message-body { white-space: pre-wrap; padding: 12px 16px; background: #edf4ff; border-radius: 10px; }
.execution-details { margin-top: 10px; max-width: 650px; }.execution-event { color: #7b8b9e; font-size: 12px; padding: 4px 0; }
.publish-summary { display: grid; gap: 6px; padding: 12px; margin-top: 8px; border: 1px solid #e5ebf4; border-radius: 8px; font-size: 13px; color: #7b8b9e; }
.composer { padding: 16px 28px; border-top: 1px solid #eef1f5; }.composer-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; gap: 8px; }
.publish-card { padding: 12px 24px; border-top: 1px solid #e0e9f6; background: #f8fbff; max-height: 45%; overflow: auto; }.card-heading,.publish-actions { display: flex; justify-content: space-between; align-items: center; gap: 10px; }.publish-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }.publish-card .el-select { width: 100%; }.publish-card .el-form-item { margin-bottom: 10px; }.publish-actions span { color: #8895a7; font-size: 12px; }.connection-error { color: #c65353; font-size: 12px; }
@media (max-width: 900px) { .conversation-panel { width: 150px; }.message-list { padding: 18px; }.chat-header,.composer { padding: 16px; } }
@media (max-width: 650px) { .chat-workbench { height: calc(100dvh - 100px); }.conversation-panel { width: 110px; padding: 10px 4px; }.suggestions,.publish-fields { grid-template-columns: 1fr; }.chat-header { gap: 6px; }.composer-actions { flex-wrap: wrap; }.composer-actions .el-button { padding: 8px; }.publish-card { padding: 12px; } }
</style>
