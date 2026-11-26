<template>
  <section class="page" data-testid="receipts-page">
    <header class="page-head">
      <div>
        <h2>撤回影响回执</h2>
        <p class="page-desc">服务端核对撤回片段后生成的回执，记录停用交付与继续授权用途，已交付记录的历史依据保留不变。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/consent_registry" data-testid="back-consent-list">返回同意登记</RouterLink>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text" data-testid="receipts-error">{{ errorMessage }}</p>

    <table class="data-table">
      <thead>
        <tr>
          <th>回执编号</th><th>数据主体</th><th>撤回同意记录</th><th>撤回处理目的</th>
          <th>撤回时间</th><th>停用交付数</th><th>停用交付明细</th><th>继续授权用途</th><th>历史依据</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="receipt in receipts" :key="String(receipt.id)" :data-testid="`receipt-row-${receipt.id}`">
          <td>{{ receipt.回执编号 }}</td>
          <td>{{ receipt.数据主体 }}</td>
          <td>{{ receipt.撤回同意记录 }}</td>
          <td><span class="tag stop">{{ receipt.撤回处理目的 }}</span></td>
          <td>{{ receipt.撤回时间 }}</td>
          <td>{{ receipt.停用交付数 }}</td>
          <td>{{ receipt.停用交付明细 }}</td>
          <td>{{ receipt.继续授权用途 }}</td>
          <td>{{ receipt.历史依据保留 }}</td>
        </tr>
        <tr v-if="!receipts.length">
          <td colspan="9" class="empty-state" data-testid="receipts-empty">暂无撤回影响回执</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { listWithdrawalReceipts } from '@/api/consent-flow'
import type { WithdrawalReceipt } from '@/data/types'

const receipts = ref<WithdrawalReceipt[]>([])
const errorMessage = ref('')

onMounted(async () => {
  try {
    receipts.value = await listWithdrawalReceipts()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '回执读取失败'
  }
})
</script>
