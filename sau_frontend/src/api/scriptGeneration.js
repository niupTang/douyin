import { http } from '@/utils/request'

export const scriptGenerationApi = {
  createIdentityScript(identityProfile, radarResult, benchmarkAnalysis = {}) {
    return http.post('/script-generation/identity', {
      identityProfile,
      radarResult,
      benchmarkAnalysis
    })
  }
}
