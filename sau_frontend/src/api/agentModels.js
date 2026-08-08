import { http } from '@/utils/request'

export const agentModelsApi = {
  getHermesSettings: () => http.get('/settings/hermes'),
  saveHermesSettings: (data) => http.put('/settings/hermes', data),
  testHermes: () => http.post('/settings/hermes/test'),
  discoverModels: (refresh = false) => http.get('/settings/hermes/models', { refresh: refresh ? 1 : 0 }),
  getAgentModels: () => http.get('/settings/agent-models'),
  createAgentModel: (data) => http.post('/settings/agent-models', data),
  updateAgentModel: (id, data) => http.put(`/settings/agent-models/${id}`, data),
  deleteAgentModel: (id) => http.delete(`/settings/agent-models/${id}`),
  testAgentModel: (id) => http.post(`/settings/agent-models/${id}/test`),
  saveTaskModels: (data) => http.put('/settings/task-models', data)
}
