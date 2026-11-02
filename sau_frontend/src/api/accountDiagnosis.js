import { http } from '@/utils/request'

export const accountDiagnosisApi = {
  // 账号管理里的抖音账号（自有诊断的锚点）
  listAccounts: () => http.get('/account-diagnosis/accounts'),

  // 自有账号列表（含绑定状态）
  listOwnAccounts: () => http.get('/own/accounts'),

  // 绑定自有账号到账号管理里的抖音账号
  bindOwnAccount: (ownAccountId, userInfoId) =>
    http.post(`/own/accounts/${ownAccountId}/bind`, { userInfoId }),

  // 触发诊断报告
  diagnose: (targetType, targetId) =>
    http.post(`/account-diagnosis/${targetType}/${targetId}`),

  // 诊断事实卡（对话/调试共用）
  getFacts: (targetType, targetId) =>
    http.get(`/account-diagnosis/facts/${targetType}/${targetId}`),

  // 历史报告
  listReports: (targetType) =>
    http.get('/account-diagnosis/reports', { targetType }),

  getReport: (reportId) =>
    http.get(`/account-diagnosis/reports/${reportId}`)
}
