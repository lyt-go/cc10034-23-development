/** 纯前端数据层的公共类型：与全栈版后端返回的结构保持一致，换回后端时页面不用改。 */

export type EntryRow = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  [field: string]: string | number | boolean
}

export type ModuleMeta = {
  key: string
  name: string
  entity: string
  desc: string
  fields: string[]
  statuses: string[]
  actions: string[]
  actionTargets: Record<string, string>
  metrics: string[]
}

export type PageResult = {
  items: EntryRow[]
  total: number
  page: number
  size: number
}

export type ActionResult = {
  ok: boolean
  message: string
  entry?: EntryRow | Record<string, unknown>
}

export type ConsentBrief = {
  id: number
  记录编号: string
  处理目的: string
  status: string
}

export type AffectedDelivery = {
  id: number
  交付编号: string
  交付批次: string
  用途清单: string
  交付状态: string
  资格依据: string
  撤回后剩余授权用途?: string[]
}

export type WithdrawalPreview = {
  ok: boolean
  message: string
  consent: EntryRow
  数据主体: string
  撤回处理目的: string
  同主体其他有效同意: ConsentBrief[]
  受影响交付: AffectedDelivery[]
  不受影响交付: AffectedDelivery[]
  可确认范围: string
}

export type WithdrawalReceipt = {
  id: number
  status: string
  回执编号: string
  数据主体: string
  撤回同意记录: string
  撤回处理目的: string
  撤回时间: string
  可确认范围: string
  停用交付数: number
  停用交付明细: string
  继续授权用途: string
  历史依据保留: string
}

export type DeliveryRow = EntryRow & {
  交付编号: string
  数据主体: string
  用途清单: string
  假名标识: string
  交付批次: string
  交付状态: string
  交付时间: string
  资格依据: string
  下载次数: number
  最近下载时间: string
  本次下载限定用途?: string
}

export type OverviewResult = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}
