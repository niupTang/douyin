import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createSessionRecovery } from '../sau_frontend/src/utils/sessionRecovery.js'

const validSession = { token: 'test-token', user: { id: 'test' }, license: { valid: true } }

test('expired authorization refreshes the desktop license before saving a new session', async () => {
  let saved
  const recover = createSessionRecovery({
    getDesktop: () => ({ licenseStatus: () => assert.fail('must refresh expired license'), refreshLicense: async () => validSession }),
    saveSession: session => { saved = session }
  })
  assert.equal(await recover({ refreshLicense: true }), validSession)
  assert.equal(saved, validSession)
})

test('concurrent unauthorized requests share one recovery and can recover again later', async () => {
  let calls = 0
  const recover = createSessionRecovery({
    getDesktop: () => ({ licenseStatus: async () => { calls++; return validSession } }),
    saveSession: () => {}
  })
  const results = await Promise.all([recover(), recover(), recover()])
  assert.equal(calls, 1)
  assert.ok(results.every(session => session === validSession))
  await recover()
  assert.equal(calls, 2)
})

test('rejected license remains invalid and never replaces the stored session', async () => {
  const recover = createSessionRecovery({
    getDesktop: () => ({ refreshLicense: async () => ({ license: { valid: false, message: '设备已解绑' } }) }),
    saveSession: () => assert.fail('invalid session must not be saved')
  })
  await assert.rejects(recover({ refreshLicense: true }), /设备已解绑/)
})

test('browser-only environment requires ordinary login instead of inventing a session', async () => {
  const recover = createSessionRecovery({ getDesktop: () => undefined, saveSession: () => assert.fail('no desktop session') })
  assert.equal(await recover(), null)
})
