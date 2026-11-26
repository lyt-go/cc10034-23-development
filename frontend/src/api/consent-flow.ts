/**
 * 同意撤回与假名化交付的专用流程接口。
 * 普通登记/列表仍走 backend-service，本文件只承载带业务判断的流程调用。
 */
import { request } from './client'
import type {
  ActionResult,
  EntryRow,
  PageResult,
  WithdrawalPreview,
  WithdrawalReceipt,
} from '@/data/types'

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  let payload: Record<string, unknown> = {}
  try {
    payload = (await response.json()) as Record<string, unknown>
  } catch {
    payload = {}
  }
  if (!response.ok) {
    const detail = (payload.detail as string) || fallback
    throw new Error(detail)
  }
  return payload as T
}

export async function fetchWithdrawalPreview(consentId: number): Promise<WithdrawalPreview> {
  const response = await request(`/api/consent/${consentId}/withdrawal/preview`)
  return readJson<WithdrawalPreview>(response, '撤回影响核对失败')
}

export async function confirmWithdrawal(consentId: number): Promise<ActionResult> {
  const response = await request(`/api/consent/${consentId}/withdrawal/confirm`, {
    method: 'POST',
  })
  const payload = (await response.json()) as ActionResult
  if (!response.ok) throw new Error(payload.message || '撤回确认失败')
  return payload
}

export async function listWithdrawalReceipts(): Promise<WithdrawalReceipt[]> {
  const response = await request('/api/withdrawal-receipts')
  const payload = await readJson<{ items: WithdrawalReceipt[]; total: number }>(
    response,
    '撤回影响回执读取失败',
  )
  return payload.items
}

export async function listDeliveries(): Promise<PageResult> {
  const response = await request('/api/pseudonym_delivery?size=200')
  if (!response.ok) throw new Error('假名化交付清单读取失败')
  return (await response.json()) as PageResult
}

export async function submitDelivery(
  values: Record<string, string>,
): Promise<ActionResult> {
  const response = await request('/api/pseudonym-delivery', {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return (await response.json()) as ActionResult
}

export async function downloadDelivery(deliveryId: number): Promise<ActionResult> {
  const response = await request(`/api/pseudonym-delivery/${deliveryId}/download`, {
    method: 'POST',
  })
  const payload = (await response.json()) as ActionResult
  if (!response.ok) throw new Error(payload.message || '交付下载失败')
  return payload
}

export async function listConsents(): Promise<EntryRow[]> {
  const response = await request('/api/consent_registry?size=200')
  if (!response.ok) throw new Error('同意登记读取失败')
  const payload = (await response.json()) as PageResult
  return payload.items
}
