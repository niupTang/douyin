// Share one recovery across requests that fail during the same session expiry.
export function createSessionRecovery({ getDesktop, saveSession }) {
  let pending = null
  return function recoverSession({ refreshLicense = false } = {}) {
    if (pending) return pending
    pending = Promise.resolve().then(async () => {
      const desktop = getDesktop()
      const method = refreshLicense ? desktop?.refreshLicense : desktop?.licenseStatus
      if (typeof method !== 'function') return null
      const session = await method.call(desktop)
      if (!session?.token || !session?.user || !session?.license?.valid) {
        throw new Error(session?.license?.message || session?.message || '本机授权恢复失败，请重新验证授权')
      }
      saveSession(session)
      return session
    }).finally(() => { pending = null })
    return pending
  }
}
