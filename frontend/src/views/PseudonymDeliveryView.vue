<template>
  <section class="page" data-testid="delivery-page">
    <header class="page-head">
      <div>
        <h2>假名化交付</h2>
        <p class="page-desc">
          按数据主体的用途授权提交假名数据交付；下载前服务端实时复核资格，撤回的用途停止交付，仍授权用途继续。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" data-testid="open-delivery-create" @click="openCreate">
          提交假名化交付
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">交付批次总数</span>
        <strong class="stat-value">{{ rows.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">可下载/部分可用</span>
        <strong class="stat-value" data-testid="stat-downloadable">{{ downloadableCount }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">停止下载</span>
        <strong class="stat-value" data-testid="stat-stopped">{{ stoppedCount }}</strong>
      </article>
    </div>

    <p v-if="errorMessage" class="error-text" data-testid="delivery-error">{{ errorMessage }}</p>
    <p v-else-if="infoMessage" class="info-text" data-testid="delivery-info">{{ infoMessage }}</p>

    <table class="data-table">
      <thead>
        <tr>
          <th>交付编号</th><th>数据主体</th><th>用途清单</th><th>假名标识</th>
          <th>交付批次</th><th>交付状态</th><th>交付时间</th><th>资格依据（创建时冻结）</th>
          <th>下载次数</th><th>最近下载时间</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :data-testid="`delivery-row-${row.id}`" :data-status="String(row.status)">
          <td>{{ row['交付编号'] }}</td>
          <td>{{ row['数据主体'] }}</td>
          <td>{{ row['用途清单'] }}</td>
          <td>{{ row['假名标识'] }}</td>
          <td>{{ row['交付批次'] }}</td>
          <td>
            <span :class="deliveryStatusClass(row['交付状态'])">{{ row['交付状态'] }}</span>
          </td>
          <td>{{ row['交付时间'] }}</td>
          <td class="basis-cell">{{ row['资格依据'] }}</td>
          <td>{{ row['下载次数'] }}</td>
          <td>{{ row['最近下载时间'] }}</td>
          <td>
            <button
              class="link"
              type="button"
              :data-testid="`download-${row.id}`"
              @click="download(Number(row.id))"
            >
              复核并下载
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="11" class="empty-state">暂无交付批次</td>
        </tr>
      </tbody>
    </table>

    <div v-if="showCreate" class="modal-backdrop" data-testid="delivery-modal">
      <form class="modal" @submit.prevent="submit">
        <h3>提交假名化交付</h3>
        <label class="create-field">
          <span>交付编号</span>
          <input v-model="form.交付编号" data-testid="create-交付编号" required />
        </label>
        <label class="create-field">
          <span>数据主体</span>
          <input v-model="form.数据主体" data-testid="create-数据主体" list="subject-options" required />
          <datalist id="subject-options">
            <option v-for="subject in subjects" :key="subject" :value="subject" />
          </datalist>
        </label>
        <label class="create-field">
          <span>用途清单（多个用途用逗号分隔，逐用途核对有效同意）</span>
          <input v-model="form.用途清单" data-testid="create-用途清单" placeholder="科学研究，教学使用" required />
        </label>
        <label class="create-field">
          <span>假名标识</span>
          <input v-model="form.假名标识" data-testid="create-假名标识" required />
        </label>
        <label class="create-field">
          <span>交付批次</span>
          <input v-model="form.交付批次" data-testid="create-交付批次" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" data-testid="submit-delivery" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '核对资格并提交' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  downloadDelivery,
  listConsents,
  listDeliveries,
  submitDelivery,
} from '@/api/consent-flow'
import type { DeliveryRow, EntryRow } from '@/data/types'

const rows = ref<DeliveryRow[]>([])
const consents = ref<EntryRow[]>([])
const errorMessage = ref('')
const infoMessage = ref('')
const showCreate = ref(false)
const submitting = ref(false)
const emptyForm = () => ({
  交付编号: '',
  数据主体: '',
  用途清单: '',
  假名标识: '',
  交付批次: '',
})
const form = ref(emptyForm())

const subjects = computed(() => {
  const seen = new Set<string>()
  for (const row of consents.value) {
    const value = String(row['数据主体'] ?? '')
    if (value) seen.add(value)
  }
  return [...seen]
})

const downloadableCount = computed(
  () => rows.value.filter((row) => row['交付状态'] !== '停止下载').length,
)
const stoppedCount = computed(
  () => rows.value.filter((row) => row['交付状态'] === '停止下载').length,
)

function deliveryStatusClass(status: string): string {
  if (status === '停止下载') return 'tag stop'
  if (status.startsWith('部分停用')) return 'tag warn'
  return 'tag ok'
}

function openCreate() {
  form.value = emptyForm()
  errorMessage.value = ''
  infoMessage.value = ''
  showCreate.value = true
}

async function reload() {
  const [deliveryPage, consentRows] = await Promise.all([listDeliveries(), listConsents()])
  rows.value = deliveryPage.items as DeliveryRow[]
  consents.value = consentRows
}

async function submit() {
  submitting.value = true
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const result = await submitDelivery(form.value)
    if (!result.ok) throw new Error(result.message)
    showCreate.value = false
    infoMessage.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '交付提交失败'
  } finally {
    submitting.value = false
  }
}

async function download(id: number) {
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const result = await downloadDelivery(id)
    if (!result.ok) throw new Error(result.message)
    infoMessage.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '下载失败'
  }
}

onMounted(async () => {
  try {
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '交付清单读取失败'
  }
})
</script>
