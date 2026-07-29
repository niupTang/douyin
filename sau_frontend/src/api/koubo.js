import { http } from '@/utils/request'

export const kouboApi = {
  listProjects() {
    return http.get('/api/koubo/projects')
  },
  createProject(payload) {
    return http.post('/api/koubo/projects', payload)
  },
  updateScript(projectId, script) {
    return http.put(`/api/koubo/projects/${projectId}/script`, { script })
  },
  createBindingCode(type = 'mobile') {
    return http.post('/api/koubo/devices/binding-code', { type })
  },
  listDevices() {
    return http.get('/api/koubo/devices')
  },
  revokeDevice(deviceId) {
    return http.delete(`/api/koubo/devices/${deviceId}`)
  },
  createEditJob(projectId, template, overrides = {}) {
    return http.post(`/api/koubo/projects/${projectId}/edit-jobs`, { template, overrides })
  },
  listAssets(projectId) {
    return http.get(`/api/koubo/projects/${projectId}/assets`)
  },
  createCover(projectId, payload) {
    return http.post(`/api/koubo/projects/${projectId}/cover`, payload)
  },
  uploadPortrait(projectId, file) {
    const form = new FormData()
    form.append('file', file)
    return http.post(`/api/koubo/projects/${projectId}/portrait`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  approveProject(projectId) {
    return http.post(`/api/koubo/projects/${projectId}/approve`, {})
  },
  markPublished(projectId, payload) {
    return http.post(`/api/koubo/projects/${projectId}/publish-result`, payload)
  }
}
