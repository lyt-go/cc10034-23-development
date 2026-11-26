<template>
  <section class="page" data-testid="withdrawal-confirm-page">
    <header class="page-head">
      <div>
        <h2>撤回影响确认</h2>
        <p class="page-desc">
          服务端核对撤回的是哪一段同意，确认后生成撤回影响回执，假名化交付据此停用受影响用途。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/consent_registry" data-testid="back-consent">返回同意登记</RouterLink>
        <RouterLink class="btn" to="/withdrawal-receipts" data-testid="goto-receipts">查看已发回执</RouterLink>
      </div>
    </header>

    <p v-if="loading" class="page-desc">正在核对撤回影响范围…</p>
    <p v-else-if="errorMessage" class="error-text" data-testid="preview-error">{{ errorMessage }}</p>

    <template v-else-if="preview">
      <article class="confirm-card" data-testid="confirm-scope">
        <h3>可确认范围（服务端核对）</h3>
        <dl class="scope-grid">
          <div><dt>数据主体</dt><dd>{{ preview.数据主体 }}</dd></div>
          <div><dt>撤回同意记录</dt><dd>{{ preview.consent['记录编号'] }}</dd></div>
          <div><dt>撤回处理目的</dt><dd>{{ preview.撤回处理目的 }}</dd></div>
        </dl>
        <p class="scope-text">{{ preview.可确认范围 }}</p>
      </article>

      <article class="confirm-card" data-testid="other-consents">
        <h3>同主体其他同意（不连带取消）</h3>
        <table class="data-table">
          <thead>
            <tr><th>记录编号</th><th>处理目的</th><th>当前状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in preview.同主体其他有效同意" :key="item.id" :data-testid="`other-consent-${item.id}`">
              <td>{{ item.记录编号 }}</td>
              <td>{{ item.处理目的 }}</td>
              <td>
                <span :class="item.status === '已同意' ? 'tag ok' : 'tag muted'">{{ item.status }}</span>
              </td>
            </tr>
            <tr v-if="!preview.同主体其他有效同意.length">
              <td colspan="3" class="empty-state">该主体没有其他同意记录</td>
            </tr>
          </tbody>
        </table>
      </article>

      <article class="confirm-card" data-testid="affected-deliveries">
        <h3>受影响交付（{{ preview.受影响交付.length }}）</h3>
        <table class="data-table">
          <thead>
            <tr><th>交付编号</th><th>交付批次</th><th>原用途清单</th><th>撤回后剩余授权用途</th><th>当前交付状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in preview.受影响交付" :key="item.id" :data-testid="`affected-${item.id}`">
              <td>{{ item.交付编号 }}</td>
              <td>{{ item.交付批次 }}</td>
              <td>{{ item.用途清单 }}</td>
              <td>
                <span v-if="item.撤回后剩余授权用途?.length" class="tag ok">
                  {{ item.撤回后剩余授权用途.join('、') }}
                </span>
                <span v-else class="tag stop">无（全部停止下载）</span>
              </td>
              <td>{{ item.交付状态 }}</td>
            </tr>
            <tr v-if="!preview.受影响交付.length">
              <td colspan="5" class="empty-state">没有引用该用途的在途交付</td>
            </tr>
          </tbody>
        </table>
      </article>

      <article class="confirm-card" data-testid="unaffected-deliveries">
        <h3>不受影响交付（{{ preview.不受影响交付.length }}）</h3>
        <ul v-if="preview.不受影响交付.length" class="plain-list">
          <li v-for="item in preview.不受影响交付" :key="item.id" :data-testid="`unaffected-${item.id}`">
            {{ item.交付编号 }}｜{{ item.用途清单 }}｜{{ item.交付状态 }}
          </li>
        </ul>
        <p v-else class="empty-state">无同主体的其他交付</p>
      </article>

      <div class="confirm-actions">
        <RouterLink class="btn" to="/consent_registry">取消</RouterLink>
        <button
          class="btn primary"
          type="button"
          data-testid="confirm-withdrawal"
          :disabled="submitting"
          @click="submitConfirm"
        >
          {{ submitting ? '确认中…' : `确认撤回「${preview.撤回处理目的}」并生成回执` }}
        </button>
      </div>
    </template>

    <div v-if="receipt" class="modal-backdrop" data-testid="receipt-modal">
      <div class="modal">
        <h3>撤回影响回执已生成</h3>
        <dl class="scope-grid">
          <div><dt>回执编号</dt><dd>{{ receipt.回执编号 }}</dd></div>
          <div><dt>数据主体</dt><dd>{{ receipt.数据主体 }}</dd></div>
          <div><dt>撤回处理目的</dt><dd>{{ receipt.撤回处理目的 }}</dd></div>
          <div><dt>停用交付数</dt><dd>{{ receipt.停用交付数 }}</dd></div>
          <div><dt>停用交付明细</dt><dd>{{ receipt.停用交付明细 }}</dd></div>
          <div><dt>继续授权用途</dt><dd>{{ receipt.继续授权用途 }}</dd></div>
          <div><dt>历史依据</dt><dd>{{ receipt.历史依据保留 }}</dd></div>
        </dl>
        <div class="page-actions">
          <RouterLink class="btn" :to="`/consent_registry`" data-testid="receipt-close">关闭</RouterLink>
          <RouterLink class="btn primary" to="/withdrawal-receipts" data-testid="receipt-view-list">
            查看全部回执
          </RouterLink>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { confirmWithdrawal, fetchWithdrawalPreview } from '@/api/consent-flow'
import type { ActionResult, WithdrawalPreview, WithdrawalReceipt } from '@/data/types'

const route = useRoute()
const consentId = Number(route.params.consentId)
const loading = ref(true)
const submitting = ref(false)
const errorMessage = ref('')
const preview = ref<WithdrawalPreview | null>(null)
const receipt = ref<WithdrawalReceipt | null>(null)

onMounted(async () => {
  try {
    preview.value = await fetchWithdrawalPreview(consentId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '撤回影响核对失败'
  } finally {
    loading.value = false
  }
})

async function submitConfirm() {
  submitting.value = true
  errorMessage.value = ''
  try {
    const result: ActionResult = await confirmWithdrawal(consentId)
    if (!result.ok) throw new Error(result.message)
    receipt.value = result.entry as WithdrawalReceipt
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '撤回确认失败'
  } finally {
    submitting.value = false
  }
}
</script>
