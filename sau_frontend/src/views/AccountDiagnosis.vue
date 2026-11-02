<template>
  <div class="account-diagnosis-page">
    <header class="page-header">
      <div><p class="eyebrow">Account Diagnosis</p><h1>账号流量诊断</h1><p>基于事实卡判断「为什么播放量低」与「爆款还是粉丝基数」。</p></div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </header>

    <el-tabs v-model="activeTab">
      <!-- 自有账号 -->
      <el-tab-pane label="自有账号诊断" name="own">
        <section class="panel">
          <div class="panel-head"><h2>选择账号</h2><span>账号管理里的抖音账号（type=3）</span></div>
          <div class="row">
            <el-select v-model="selectedOwnId" filterable placeholder="选择抖音账号" class="grow">
              <el-option v-for="a in douyinAccounts" :key="a.id" :label="`${a.userName}（粉丝 ${formatNum(a.follower_count)}）`" :value="a.id" />
            </el-select>
            <el-button type="primary" :loading="diagnosing" :disabled="!selectedOwnId" @click="runDiagnosis('own', selectedOwnId)">开始诊断</el-button>
          </div>
          <div class="hint" v-if="!douyinAccounts.length">还没有可诊断的抖音账号，请先在「账号管理」扫码登录抖音账号。</div>
        </section>

        <section class="panel">
          <div class="panel-head"><h2>绑定自有作品</h2><span>把「自有作品」数据关联到账号管理里的抖音账号</span></div>
          <el-table :data="ownAccounts" empty-text="还没有自有账号，先在「作品复盘」导入创作者后台数据">
            <el-table-column prop="name" label="自有账号" min-width="140" />
            <el-table-column label="绑定到" min-width="280">
              <template #default="s">
                <el-select v-model="s.row._bindTarget" filterable placeholder="选择账号管理里的抖音账号" class="grow">
                  <el-option v-for="a in douyinAccounts" :key="a.id" :label="`${a.userName}（粉丝 ${formatNum(a.follower_count)}）`" :value="a.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="s">
                <el-button link type="primary" :loading="bindingId === s.row.id" @click="bindAccount(s.row)">绑定</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <!-- 对标账号 -->
      <el-tab-pane label="对标账号诊断" name="benchmark">
        <section class="panel">
          <div class="panel-head"><h2>选择对标账号</h2><span>判断它是爆款还是粉丝基数</span></div>
          <div class="row">
            <el-select v-model="selectedBenchmarkId" filterable placeholder="选择对标账号" class="grow">
              <el-option v-for="a in benchmarkAccounts" :key="a.id" :label="`${a.nickname || a.homepage_url}（粉丝 ${formatNum(a.followers_count)}）`" :value="a.id" />
            </el-select>
            <el-button type="primary" :loading="diagnosing" :disabled="!selectedBenchmarkId" @click="runDiagnosis('benchmark', selectedBenchmarkId)">开始诊断</el-button>
          </div>
          <div class="hint" v-if="!benchmarkAccounts.length">还没有对标账号，请先在「对标内容库」同步对标账号。</div>
        </section>
      </el-tab-pane>
    </el-tabs>

    <!-- 诊断进度 -->
    <section class="panel" v-if="diagnosing">
      <el-progress :percentage="progress" :stroke-width="10" :status="progress >= 100 ? 'success' : undefined" />
      <div class="progress-text">{{ progressMessage }}</div>
    </section>

    <!-- 报告结果 -->
    <section class="panel" v-if="report">
      <div class="panel-head"><h2>诊断报告</h2><el-tag size="small" type="success">已完成</el-tag></div>
      <ReportCard :report="report" />
    </section>

    <!-- 历史报告 -->
    <section class="panel">
      <div class="panel-head"><h2>历史报告</h2><el-button link type="primary" @click="loadReports">刷新</el-button></div>
      <el-table :data="reports" empty-text="还没有诊断报告">
        <el-table-column label="类型" width="110"><template #default="s">{{ s.row.target_type === 'own' ? '自有账号' : '对标账号' }}</template></el-table-column>
        <el-table-column label="目标 ID" prop="target_id" width="100" />
        <el-table-column label="时间" prop="created_at" min-width="170" />
        <el-table-column label="摘要" min-width="300"><template #default="s">{{ reportSummary(s.row) }}</template></el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="s"><el-button link type="primary" @click="openReport(s.row)">查看</el-button></template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { accountDiagnosisApi } from '@/api/accountDiagnosis'
import { benchmarkApi } from '@/api/benchmark'
import ReportCard from '@/components/DiagnosisReportCard.vue'

const activeTab = ref('own')
const loading = ref(false), diagnosing = ref(false), bindingId = ref('')
const douyinAccounts = ref([]), ownAccounts = ref([]), benchmarkAccounts = ref([])
const selectedOwnId = ref(''), selectedBenchmarkId = ref('')
const report = ref(null), reports = ref([])
const progress = ref(0)
const progressMessage = ref('')
let pollTimer = null

const formatNum = (v) => {
  const n = Number(v || 0)
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return String(n)
}

const reportSummary = (row) => {
  const r = row.report || {}
  return r.summary || r.viral_conclusion || r.traffic_conclusion || '—'
}

const loadAll = async () => {
  loading.value = true
  try {
    const [accs, owns, benchs] = await Promise.all([
      accountDiagnosisApi.listAccounts(),
      accountDiagnosisApi.listOwnAccounts(),
      benchmarkApi.getDouyinAccounts()
    ])
    douyinAccounts.value = accs.data || []
    ownAccounts.value = (owns.data || []).map((a) => ({ ...a, _bindTarget: a.user_info_id || '' }))
    benchmarkAccounts.value = benchs.data || []
    await loadReports()
  } finally { loading.value = false }
}

const loadReports = async () => {
  const res = await accountDiagnosisApi.listReports()
  reports.value = res.data || []
}

const clearPoll = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

const pollReport = (reportId) => new Promise((resolve, reject) => {
  const tick = async () => {
    try {
      const res = await accountDiagnosisApi.getReport(reportId)
      const row = res.data || {}
      if (row.progress_percent != null) progress.value = row.progress_percent
      if (row.progress_message) progressMessage.value = row.progress_message
      if (row.status === 'success') {
        progress.value = 100
        progressMessage.value = '诊断完成'
        report.value = row.report
        resolve()
      } else if (row.status === 'failed') {
        reject(new Error(row.error_message || '诊断失败'))
      }
    } catch (e) {
      reject(e)
    }
  }
  tick()
  pollTimer = setInterval(tick, 1500)
})

const runDiagnosis = async (targetType, targetId) => {
  diagnosing.value = true
  report.value = null
  progress.value = 0
  progressMessage.value = '任务已创建…'
  clearPoll()
  try {
    const res = await accountDiagnosisApi.diagnose(targetType, targetId)
    const reportId = res.data?.reportId
    if (!reportId) throw new Error('诊断任务创建失败')
    await pollReport(reportId)
    ElMessage.success('诊断完成')
    await loadReports()
  } catch (error) {
    progress.value = 0
    ElMessage.error(error?.message || '诊断失败')
  } finally {
    clearPoll()
    diagnosing.value = false
  }
}

const bindAccount = async (row) => {
  if (!row._bindTarget) return ElMessage.warning('请先选择要绑定的账号')
  bindingId.value = row.id
  try {
    await accountDiagnosisApi.bindOwnAccount(row.id, row._bindTarget)
    row.user_info_id = row._bindTarget
    ElMessage.success(`已把「${row.name}」绑定到账号管理`)
  } catch (error) {
    ElMessage.error(error?.message || '绑定失败')
  } finally { bindingId.value = '' }
}

const openReport = (row) => { report.value = row.report || row }

onMounted(loadAll)
</script>

<style lang="scss" scoped>
.account-diagnosis-page { max-width: 1180px; margin: 0 auto; color: #20242c; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.page-header p { margin: 6px 0 0; color: #737985; }
.eyebrow { color: #53715d !important; font-size: 12px; font-weight: 700; text-transform: uppercase; }
h1 { margin: 0; font-size: 30px; } h2 { margin: 0; font-size: 17px; }
.panel { padding: 22px 0; border-top: 1px solid #e1e4e8; }
.panel-head { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.panel-head span { color: #737985; font-size: 13px; }
.row { display: flex; gap: 12px; align-items: center; }
.grow { width: min(420px, 100%); }
.hint { margin-top: 10px; color: #a2a6ad; font-size: 13px; }
.progress-text { margin-top: 10px; color: #737985; font-size: 13px; }
</style>
