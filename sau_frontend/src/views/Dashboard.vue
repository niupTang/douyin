<template>
  <div class="growth-console">
    <header class="console-header">
      <div>
        <div class="project-line">
          <h1>内容增长平台</h1>
          <span class="project-id">SAU</span>
          <span class="project-region">Douyin</span>
        </div>
        <p>复盘内容、对标账号和爆款拆解集中管理。</p>
      </div>
      <el-button class="primary-action" :icon="Plus" @click="navigateTo('/benchmark-management')">
        添加对标
      </el-button>
    </header>

    <section class="large-metrics">
      <article class="metric-card large">
        <div class="metric-top">
          <div>
            <strong>{{ formatNumber(stats.reviewedWorks) }}</strong>
            <span>条</span>
          </div>
          <button class="period-button">30d <el-icon><ArrowDown /></el-icon></button>
        </div>
        <p>复盘内容</p>
        <div class="empty-chart">
          <el-icon><Histogram /></el-icon>
          <span>{{ stats.reviewedWorks ? '等待更多样本形成趋势' : 'No data to show' }}</span>
        </div>
      </article>

      <article class="metric-card large">
        <div class="metric-top">
          <div>
            <strong>{{ formatNumber(stats.viralAnalyses) }}</strong>
          </div>
          <button class="period-button">30d <el-icon><ArrowDown /></el-icon></button>
        </div>
        <p>爆款拆解数</p>
        <div class="empty-chart">
          <el-icon><Histogram /></el-icon>
          <span>{{ stats.viralAnalyses ? '本周拆解持续增加' : 'No data to show' }}</span>
        </div>
      </article>
    </section>

    <section class="small-metrics">
      <article v-for="item in metricCards" :key="item.label" class="metric-card small" @click="navigateTo(item.path)">
        <div class="metric-label">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.kicker }}</span>
        </div>
        <strong>{{ item.value }}</strong>
        <p>{{ item.label }}</p>
      </article>
    </section>

    <section class="workbench">
      <div class="section-heading">
        <h2>工作台</h2>
        <div class="tabs">
          <button class="active">增长动作</button>
          <button>对标样本</button>
          <button>复盘队列</button>
        </div>
      </div>

      <div class="action-bar">
        <el-button class="primary-action" :icon="Plus" @click="navigateTo('/own-content-review')">
          新建复盘
        </el-button>
      </div>

      <div class="action-table">
        <div class="table-row table-head">
          <span>动作</span>
          <span>类型</span>
          <span>状态</span>
        </div>
        <button
          v-for="action in actions"
          :key="action.name"
          class="table-row"
          @click="navigateTo(action.path)"
        >
          <span>{{ action.name }}</span>
          <span>{{ action.type }}</span>
          <span>{{ action.status }}</span>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import {
  Aim,
  ArrowDown,
  DataAnalysis,
  DocumentChecked,
  Histogram,
  MagicStick,
  Plus
} from '@element-plus/icons-vue'
import { benchmarkApi } from '@/api/benchmark'
import { ownContentApi } from '@/api/ownContent'

const router = useRouter()

const stats = reactive({
  reviewedWorks: 0,
  benchmarkAccounts: 0,
  viralAnalyses: 0,
  viralWorks: 0
})

const metricCards = computed(() => [
  {
    kicker: 'REVIEW',
    label: '复盘内容',
    value: formatNumber(stats.reviewedWorks),
    path: '/own-content-review',
    icon: DocumentChecked
  },
  {
    kicker: 'BENCHMARK',
    label: '对标账号',
    value: formatNumber(stats.benchmarkAccounts),
    path: '/benchmark-management',
    icon: Aim
  },
  {
    kicker: 'ANALYSIS',
    label: '爆款拆解数',
    value: formatNumber(stats.viralAnalyses),
    path: '/idea-radar',
    icon: DataAnalysis
  },
  {
    kicker: 'VIRAL',
    label: '爆款数',
    value: formatNumber(stats.viralWorks),
    path: '/idea-radar',
    icon: MagicStick
  }
])

const actions = [
  { name: '导入作品数据', type: '复盘内容', status: '可执行', path: '/own-content-review' },
  { name: '同步对标账号', type: '样本管理', status: '可执行', path: '/benchmark-management' },
  { name: '拆解高赞作品', type: '爆款拆解', status: '可执行', path: '/idea-radar' }
]

const formatNumber = (value) => {
  const n = Number(value || 0)
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return n.toLocaleString()
}

const fetchDashboardData = async () => {
  const [worksResult, accountsResult, videosResult] = await Promise.allSettled([
    ownContentApi.getDouyinWorks(500),
    benchmarkApi.getDouyinAccounts(),
    benchmarkApi.getIdeaRadarVideos(500)
  ])

  const works = worksResult.status === 'fulfilled' ? worksResult.value.data || [] : []
  const accounts = accountsResult.status === 'fulfilled' ? accountsResult.value.data || [] : []
  const videos = videosResult.status === 'fulfilled' ? videosResult.value.data || [] : []

  stats.reviewedWorks = works.length
  stats.benchmarkAccounts = accounts.length
  stats.viralAnalyses = videos.length
  stats.viralWorks = videos.filter((video) => Number(video.like_score || video.like_count || 0) >= 10000).length
}

const navigateTo = (path) => {
  router.push(path)
}

onMounted(fetchDashboardData)
</script>

<style lang="scss">
.growth-console {
  max-width: 1160px;
  margin: 0 auto;
  color: #25272c;
}

.console-header {
  min-height: 104px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 4px 0 28px;

  p {
    margin-top: 8px;
    color: #737780;
    font-size: 14px;
  }
}

.project-line {
  display: flex;
  align-items: center;
  gap: 10px;

  h1 {
    margin: 0;
    color: #2c2d31;
    font-size: 32px;
    font-weight: 500;
    letter-spacing: 0;
  }
}

.project-id {
  padding: 4px 9px;
  border-radius: 7px;
  background: #f1f1f3;
  color: #565a62;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.project-region {
  color: #6f737c;
  font-size: 14px;
}

.primary-action {
  border: 0;
  border-radius: 8px;
  background: #ff3b7f;
  color: #ffffff;
  font-weight: 600;

  &:hover,
  &:focus {
    background: #ef2f72;
    color: #ffffff;
  }
}

.large-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.small-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 22px;
  margin-top: 22px;
}

.metric-card {
  border: 1px solid #e7e7ea;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.02);
}

.metric-card.large {
  min-height: 214px;
  padding: 18px;
}

.metric-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;

  strong {
    color: #2b2d31;
    font-size: 28px;
    font-weight: 500;
    line-height: 1;
  }

  span {
    margin-left: 4px;
    color: #4f535a;
    font-size: 12px;
  }
}

.period-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #626771;
  font-size: 14px;
}

.metric-card.large > p {
  margin: 8px 0 18px;
  color: #6f737c;
  font-size: 15px;
}

.empty-chart {
  height: 106px;
  display: grid;
  place-items: center;
  border: 1px dashed #e8e8ec;
  border-radius: 12px;
  color: #747880;
  font-weight: 600;

  .el-icon {
    margin-bottom: -18px;
    color: #73777f;
    font-size: 20px;
  }
}

.metric-card.small {
  min-height: 158px;
  padding: 20px 18px;
  cursor: pointer;
  transition: border-color 0.16s, transform 0.16s;

  &:hover {
    border-color: #d6d7dc;
    transform: translateY(-1px);
  }

  strong {
    display: block;
    margin-top: 48px;
    color: #2b2d31;
    font-size: 27px;
    font-weight: 500;
    line-height: 1;
  }

  p {
    margin-top: 7px;
    color: #636770;
    font-size: 15px;
  }
}

.metric-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #b7b8bd;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.8px;

  .el-icon {
    font-size: 15px;
  }
}

.workbench {
  margin-top: 34px;
}

.section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 20px;

  h2 {
    margin: 0;
    color: #2c2d31;
    font-size: 26px;
    font-weight: 500;
  }
}

.tabs {
  display: inline-flex;
  padding: 3px;
  border-radius: 9px;
  background: #f1f1f4;

  button {
    height: 32px;
    padding: 0 14px;
    border-radius: 7px;
    color: #626771;
    font-size: 14px;

    &.active {
      background: #ffffff;
      color: #2d3035;
      box-shadow: 0 1px 4px rgba(16, 24, 40, 0.08);
    }
  }
}

.action-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 20px;
}

.action-table {
  overflow: hidden;
  border: 1px solid #e7e7ea;
  border-radius: 9px;
  background: #ffffff;
}

.table-row {
  width: 100%;
  min-height: 42px;
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  align-items: center;
  padding: 0 14px;
  border-bottom: 1px solid #ececef;
  color: #686c75;
  text-align: left;
  font-size: 14px;

  &:last-child {
    border-bottom: 0;
  }
}

.table-head {
  color: #646872;
  background: #fbfbfc;
  font-weight: 500;
}

button.table-row:hover {
  background: #fafafa;
}

@media (max-width: 980px) {
  .large-metrics,
  .small-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .console-header,
  .section-heading {
    display: block;
  }

  .primary-action {
    margin-top: 16px;
  }

  .large-metrics,
  .small-metrics,
  .table-row {
    grid-template-columns: 1fr;
  }

  .table-row {
    gap: 6px;
    padding: 12px 14px;
  }
}
</style>
