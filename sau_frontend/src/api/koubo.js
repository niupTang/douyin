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
  createBindingCode() {
    return http.post('/api/koubo/devices/binding-code', {})
  },
  createEditJob(projectId, template) {
    return http.post(`/api/koubo/projects/${projectId}/edit-jobs`, { template })
  },
  listAssets(projectId) {
    return http.get(`/api/koubo/projects/${projectId}/assets`)
  },
  createCover(projectId, payload) {
    return http.post(`/api/koubo/projects/${projectId}/cover`, payload)
  },
  approveProject(projectId) {
    return http.post(`/api/koubo/projects/${projectId}/approve`, {})
  }
}
