<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="brand-lock">
        <div class="brand-mark">S</div>
        <div>
          <strong>Sunbird OS</strong>
          <span>本地内容运营工作台</span>
        </div>
      </div>

      <div class="login-copy">
        <h1>登录本地软件</h1>
        <p>请输入本机管理员账号，登录后才能访问发布、账号和数据功能。</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" size="large" @submit.prevent="submit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            autocomplete="current-password"
            show-password
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" class="login-button" :loading="loading" @click="submit">
          登录
        </el-button>
      </el-form>

      <p class="login-hint">首次启动默认账号：admin / admin123</p>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { userApi } from '@/api/user'
import { useUserStore } from '@/stores'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function submit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    const response = await userApi.login(form)
    userStore.setSession(response.data)
    router.replace(route.query.redirect || '/')
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(17, 24, 39, 0.94), rgba(30, 41, 59, 0.88)),
    url('/vite.svg') center / 180px no-repeat;
}

.login-panel {
  width: min(420px, 100%);
  padding: 34px;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 22px 70px rgba(15, 23, 42, 0.28);
}

.brand-lock {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;

  strong,
  span {
    display: block;
  }

  strong {
    color: #111827;
    font-size: 17px;
  }

  span {
    margin-top: 2px;
    color: #6b7280;
    font-size: 12px;
  }
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: #111827;
  color: #ffffff;
  font-weight: 800;
}

.login-copy {
  margin-bottom: 24px;

  h1 {
    margin: 0 0 8px;
    color: #111827;
    font-size: 26px;
    line-height: 1.25;
  }

  p {
    margin: 0;
    color: #6b7280;
    line-height: 1.7;
  }
}

.login-button {
  width: 100%;
}

.login-hint {
  margin: 18px 0 0;
  color: #8b95a5;
  font-size: 12px;
  text-align: center;
}
</style>
