<template>
  <div class="report-card">
    <div class="conclusion" v-if="conclusion">
      <div class="conclusion-label">{{ isBenchmark ? '爆款判断' : '流量结论' }}</div>
      <div class="conclusion-text">{{ conclusion }}</div>
    </div>

    <p class="summary" v-if="report.summary">{{ report.summary }}</p>

    <!-- 四层诊断 -->
    <div v-if="report.diagnosis_layers?.length" class="block">
      <h3>分层诊断</h3>
      <div v-for="(l, i) in report.diagnosis_layers" :key="i" class="layer">
        <div class="layer-head"><strong>{{ l.layer }}</strong><el-tag size="small" :type="tagType(l.judgment)">{{ l.judgment }}</el-tag></div>
        <div class="layer-reason">{{ l.reason }}</div>
      </div>
    </div>

    <!-- 单条视频分类 -->
    <div v-if="report.per_video_classification?.length" class="block">
      <h3>逐条判断</h3>
      <div v-for="(v, i) in report.per_video_classification" :key="i" class="layer">
        <div class="layer-head"><strong>{{ v.title }}</strong><el-tag size="small" :type="classTag(v.classification)">{{ v.classification }}</el-tag></div>
        <div class="layer-reason">{{ v.reason }}</div>
      </div>
    </div>

    <div class="grid">
      <div class="block" v-if="report.key_metrics?.length">
        <h3>关键指标</h3>
        <ul><li v-for="(m, i) in report.key_metrics" :key="i">{{ m }}</li></ul>
      </div>
      <div class="block" v-if="report.takeaways?.length">
        <h3>可借鉴点</h3>
        <ul><li v-for="(t, i) in report.takeaways" :key="i">{{ t }}</li></ul>
      </div>
    </div>

    <div class="block" v-if="report.improvement_actions?.length">
      <h3>改进建议</h3>
      <ol><li v-for="(a, i) in report.improvement_actions" :key="i">{{ a }}</li></ol>
    </div>

    <div class="block" v-if="report.low_performing_videos?.length">
      <h3>低播放作品</h3>
      <ul><li v-for="(v, i) in report.low_performing_videos" :key="i">{{ v }}</li></ul>
    </div>

    <div class="confidence" v-if="report.confidence">置信度：{{ report.confidence }}</div>

    <el-collapse v-if="!isStructured">
      <el-collapse-item title="查看原始 JSON"><pre>{{ pretty }}</pre></el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ report: { type: Object, default: () => ({}) } })

const report = computed(() => props.report || {})
const isBenchmark = computed(() => Boolean(report.value.viral_conclusion))
const isStructured = computed(() =>
  Boolean(report.value.summary || report.value.diagnosis_layers || report.value.per_video_classification)
)
const conclusion = computed(() => report.value.viral_conclusion || report.value.traffic_conclusion || '')
const pretty = computed(() => JSON.stringify(report.value, null, 2))

const tagType = (j) => {
  const t = String(j || '')
  if (t.includes('问题') || t.includes('弱') || t.includes('不足')) return 'danger'
  if (t.includes('不足') || t.includes('待')) return 'info'
  if (t.includes('明显')) return 'danger'
  return 'success'
}
const classTag = (c) => {
  const t = String(c || '')
  if (t.includes('爆款')) return 'danger'
  if (t.includes('半爆') || t.includes('突出')) return 'warning'
  if (t.includes('低') || t.includes('不足')) return 'info'
  return 'success'
}
</script>

<style lang="scss" scoped>
.report-card { color: #20242c; }
.conclusion { background: #f2f6f3; border-left: 4px solid #53715d; padding: 14px 16px; border-radius: 6px; margin-bottom: 14px; }
.conclusion-label { font-size: 12px; color: #53715d; font-weight: 700; margin-bottom: 4px; }
.conclusion-text { font-size: 15px; font-weight: 600; }
.summary { color: #4b5058; line-height: 1.7; margin: 0 0 14px; }
.block { margin-bottom: 18px; }
.block h3 { font-size: 14px; margin: 0 0 10px; color: #20242c; }
.block ul, .block ol { margin: 0; padding-left: 18px; color: #4b5058; line-height: 1.8; }
.layer { padding: 10px 12px; background: #fafbfc; border: 1px solid #eef0f2; border-radius: 6px; margin-bottom: 8px; }
.layer-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.layer-reason { color: #5a6068; font-size: 13px; line-height: 1.6; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.confidence { color: #737985; font-size: 13px; }
pre { white-space: pre-wrap; word-break: break-all; font-size: 12px; color: #4b5058; }
@media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
</style>
