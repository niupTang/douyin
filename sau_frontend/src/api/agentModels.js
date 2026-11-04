import { http } from '@/utils/request'

export const agentModelsApi = {
  getMigrationStatus: () => http.get('/api/ai/migration-status'),
  getProviders: () => http.get('/api/ai/providers'),
  createProvider: (data) => http.post('/api/ai/providers', data),
  updateProvider: (id, data) => http.put(`/api/ai/providers/${id}`, data),
  deleteProvider: (id) => http.delete(`/api/ai/providers/${id}`),
  saveProviderCredential: (id, apiKey) => http.put(`/api/ai/providers/${id}/credential`, { apiKey }),
  clearProviderCredential: (id) => http.delete(`/api/ai/providers/${id}/credential`),
  testProvider: (id) => http.post(`/api/ai/providers/${id}/test`),
  createModelProfile: (data) => http.post('/api/ai/model-profiles', data),
  updateModelProfile: (id, data) => http.put(`/api/ai/model-profiles/${id}`, data),
  deleteModelProfile: (id) => http.delete(`/api/ai/model-profiles/${id}`),
  getHermesSettings: () => http.get('/settings/hermes'),
  saveHermesSettings: (data) => http.put('/settings/hermes', data),
  testHermes: (data) => http.post('/settings/hermes/test', data),
  discoverModels: (refresh = false) => http.get('/settings/hermes/models', { refresh: refresh ? 1 : 0 }),
  getAgentModels: () => http.get('/settings/agent-models'),
  createAgentModel: (data) => http.post('/settings/agent-models', data),
  updateAgentModel: (id, data) => http.put(`/settings/agent-models/${id}`, data),
  deleteAgentModel: (id) => http.delete(`/settings/agent-models/${id}`),
  testAgentModel: (id) => http.post(`/settings/agent-models/${id}/test`),
  saveTaskModels: (data) => http.put('/settings/task-models', data),
  getRuntimeModelProfiles: () => http.get('/api/ai/model-profiles'),
  getAgentProfiles: () => http.get('/api/ai/agent-profiles'),
  saveAgentProfile: (agentKey, data) => http.put(`/api/ai/agent-profiles/${agentKey}`, data)
}
