<template>
  <main class="license-page">
    <section class="license-panel">
      <div class="brand-lock">
        <div class="brand-mark">S</div>
        <div><strong>Sunbird OS</strong><span>本地内容决策与口播工作台</span></div>
      </div>

      <div class="license-copy">
        <span>设备授权</span>
        <h1>{{ checking ? '正在验证许可证' : '输入购买卡密激活' }}</h1>
        <p>一张卡密默认绑定一台电脑。内容、抖音登录态和 AI 分析数据只保存在本机。</p>
      </div>

      <el-form v-if="!checking" :model="form" :rules="rules" ref="formRef" size="large" @submit.prevent="submit">
        <el-form-item prop="code">
          <el-input
            v-model="form.code"
            placeholder="例如 SB-ABCD-EFGH-JKLM"
            autocomplete="off"
            clearable
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" native-type="submit" class="activate-button" :loading="loading">激活当前设备</el-button>
      </el-form>

      <div v-else class="checking"><el-icon class="is-loading"><Loading /></el-icon><span>正在检查本机安全存储与离线许可证…</span></div>

      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />
      <p class="license-hint">支持断网使用 7 天；授权到期后，本地已有数据仍可查看和导出。</p>
    </section>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)
const checking = ref(true)
const errorMessage = ref('')
const form = reactive({ code: '' })
const rules = { code: [{ required: true, message: '请输入购买后的卡密', trigger: 'blur' }] }

function completeSession(data) {
  if (!data?.token || !data?.user || !data?.license?.valid) return false
  userStore.setSession(data)
  router.replace(route.query.redirect || '/')
  return true
}

function licenseFailureMessage(data, fallback = '激活失败，请检查卡密和网络连接') {
  return data?.license?.message || data?.message || fallback
}

async function submit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!window.sunbirdDesktop?.activateLicense) {
    errorMessage.value = '卡密激活仅支持在 Sunbird 桌面应用中使用'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await window.sunbirdDesktop.activateLicense(form.code)
    if (!completeSession(data)) {
      errorMessage.value = licenseFailureMessage(data)
    }
  } catch (error) {
    errorMessage.value = error?.message || '激活失败，请检查卡密和网络连接'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!window.sunbirdDesktop?.licenseStatus) {
    checking.value = false
    errorMessage.value = '当前为网页开发环境，请通过 Electron 桌面端测试卡密激活'
    return
  }
  try {
    const data = await window.sunbirdDesktop.licenseStatus()
    if (!completeSession(data) && data?.license?.message) errorMessage.value = data.license.message
  } catch (error) {
    errorMessage.value = error?.message || '读取本机许可证失败'
  } finally {
    checking.value = false
  }
})
</script>

<style lang="scss" scoped>
.license-page { min-height:100vh; display:grid; place-items:center; padding:24px; background:radial-gradient(circle at 20% 10%,#334155 0,transparent 38%),linear-gradient(135deg,#0f172a,#111827); }
.license-panel { width:min(460px,100%); padding:38px; border-radius:18px; background:#fff; box-shadow:0 28px 90px #02061766; }
.brand-lock { display:flex; align-items:center; gap:12px; margin-bottom:34px; }
.brand-lock strong,.brand-lock span { display:block; }
.brand-lock strong { color:#111827; font-size:17px; }
.brand-lock span { margin-top:2px; color:#6b7280; font-size:12px; }
.brand-mark { width:42px; height:42px; border-radius:11px; display:grid; place-items:center; background:#111827; color:#fff; font-weight:800; }
.license-copy { margin-bottom:26px; }
.license-copy > span { color:#b7791f; font-size:12px; font-weight:800; letter-spacing:.16em; }
.license-copy h1 { margin:8px 0 10px; color:#111827; font-size:28px; }
.license-copy p,.license-hint { color:#6b7280; line-height:1.75; }
.activate-button { width:100%; }
.checking { min-height:72px; display:flex; align-items:center; justify-content:center; gap:10px; color:#64748b; }
.license-hint { margin:18px 0 0; font-size:12px; text-align:center; }
.el-alert { margin-top:18px; }
</style>
