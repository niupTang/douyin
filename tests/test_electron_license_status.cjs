const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const source = fs.readFileSync(path.join(__dirname, '../electron/main.cjs'), 'utf8')
const statusFunction = source.slice(source.indexOf('async function getLicenseStatus()'), source.indexOf('async function deactivateLicense()'))

function statusReader(overrides) {
  const context = {
    loadLicenseState: () => ({ license: {}, deviceId: 'test-device', refreshToken: 'test-refresh' }),
    ...overrides
  }
  vm.createContext(context)
  vm.runInContext(statusFunction, context)
  return context.getLicenseStatus
}

test('a valid local session does not require an online refresh', async () => {
  const session = { token: 'test-session', license: { valid: true } }
  const read = statusReader({
    installLicenseIntoBackend: async () => session,
    refreshLicense: async () => assert.fail('valid offline session must remain usable')
  })
  assert.equal(await read(), session)
})

test('an expired offline grace period recovers an existing activated session online', async () => {
  const session = { token: 'renewed-session', license: { valid: true } }
  let refreshed = 0
  const read = statusReader({
    installLicenseIntoBackend: async () => { throw Object.assign(new Error('offline grace expired'), { reasonCode: 'OFFLINE_GRACE_EXPIRED' }) },
    refreshLicense: async () => { refreshed++; return session }
  })
  assert.equal(await read(), session)
  assert.equal(refreshed, 1)
})

test('a rejected cloud refresh remains invalid and exposes its reason', async () => {
  const read = statusReader({
    installLicenseIntoBackend: async () => { throw Object.assign(new Error('offline grace expired'), { reasonCode: 'OFFLINE_GRACE_EXPIRED' }) },
    refreshLicense: async () => { throw Object.assign(new Error('device revoked'), { reasonCode: 'DEVICE_REVOKED' }) }
  })
  const result = await read()
  assert.equal(result.license.valid, false)
  assert.equal(result.license.reasonCode, 'DEVICE_REVOKED')
})

test('an invalid signature is not recovered as an offline timeout', async () => {
  const read = statusReader({
    installLicenseIntoBackend: async () => { throw Object.assign(new Error('invalid signature'), { reasonCode: 'LICENSE_SIGNATURE_INVALID' }) },
    refreshLicense: async () => assert.fail('signature failures must not be treated as offline expiry')
  })
  assert.equal((await read()).license.reasonCode, 'LICENSE_SIGNATURE_INVALID')
})
