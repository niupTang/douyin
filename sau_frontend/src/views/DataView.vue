<template>
  <div class="data-view">
    <div class="page-header">
      <h1>发布数据</h1>
      <el-button type="primary" :loading="loading" @click="fetchRecords">
        刷新
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="records" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="平台" width="120">
          <template #default="scope">
            <el-tag>{{ platformName(scope.row.platform_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="文件" min-width="220">
          <template #default="scope">
            <div v-for="file in scope.row.file_list" :key="file" class="mono">
              {{ file }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="账号" min-width="220">
          <template #default="scope">
            <div v-for="account in scope.row.account_list" :key="account" class="mono">
              {{ account }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'success' ? 'success' : 'danger'">
              {{ scope.row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="240" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>

      <el-empty v-if="!loading && records.length === 0" description="暂无发布数据" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { publishApi } from '@/api/publish'

const loading = ref(false)
const records = ref([])

const platformName = (type) => {
  const map = {
    1: '小红书',
    2: '视频号',
    3: '抖音',
    4: '快手'
  }
  return map[Number(type)] || `平台 ${type}`
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const response = await publishApi.getPublishRecords()
    records.value = response.data || []
  } catch (error) {
    console.error('获取发布数据失败:', error)
    ElMessage.error('获取发布数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchRecords)
</script>

<style lang="scss" scoped>
.data-view {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
    }
  }

  .mono {
    font-family: Consolas, 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.5;
  }
}
</style>
