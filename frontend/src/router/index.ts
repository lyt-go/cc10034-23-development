import { createRouter, createWebHistory } from 'vue-router'

import ConsentWithdrawalView from '@/views/ConsentWithdrawalView.vue'
import Overview from '@/views/Overview.vue'
import PseudonymDeliveryView from '@/views/PseudonymDeliveryView.vue'
import WithdrawalReceiptsView from '@/views/WithdrawalReceiptsView.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    {
      path: '/consent_registry/withdrawal/:consentId',
      name: 'consent-withdrawal',
      component: ConsentWithdrawalView,
      props: true,
    },
    { path: '/pseudonym-delivery', name: 'pseudonym-delivery', component: PseudonymDeliveryView },
    { path: '/withdrawal-receipts', name: 'withdrawal-receipts', component: WithdrawalReceiptsView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
