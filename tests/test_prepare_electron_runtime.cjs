const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const prepare = require('../scripts/prepare-electron-runtime.cjs')

test('stage Electron without old app resources and remove stale staged files', async () => {
  const cache = path.resolve(__dirname, '../.sau-cache')
  fs.mkdirSync(cache, { recursive: true })
  const root = fs.mkdtempSync(path.join(cache, 'electron-package-test-'))
  try {
    const source = path.join(root, 'node_modules/electron/dist')
    fs.mkdirSync(path.join(source, 'resources/backend-runtime'), { recursive: true })
    fs.writeFileSync(path.join(source, 'electron.exe'), 'runtime')
    fs.writeFileSync(path.join(source, 'resources/default_app.asar'), 'default app')
    fs.writeFileSync(path.join(source, 'resources/app.asar.release-backup'), 'old app')
    fs.writeFileSync(path.join(source, 'resources/backend-runtime/database.db'), 'private data')
    const context = { packager: { projectDir: root } }
    await assert.rejects(prepare(context), /Whisper base model is missing/)
    const modelRepo = path.join(root, 'build-resources/huggingface/hub/models--Systran--faster-whisper-base')
    const revision = 'a'.repeat(40)
    fs.mkdirSync(path.join(modelRepo, 'refs'), { recursive: true })
    fs.writeFileSync(path.join(modelRepo, 'refs/main'), revision)
    const snapshot = path.join(modelRepo, 'snapshots', revision)
    fs.mkdirSync(snapshot, { recursive: true })
    for (const name of ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']) {
      fs.writeFileSync(path.join(snapshot, name), 'model file')
    }
    await prepare(context)
    const target = path.join(root, 'build-resources/electron-runtime')
    assert.equal(fs.readFileSync(path.join(target, 'electron.exe'), 'utf8'), 'runtime')
    assert.deepEqual(fs.readdirSync(path.join(target, 'resources')), ['default_app.asar'])
    fs.writeFileSync(path.join(target, 'stale.txt'), 'stale')
    await prepare(context)
    assert.equal(fs.existsSync(path.join(target, 'stale.txt')), false)
    fs.writeFileSync(path.join(snapshot, 'model.bin'), '')
    await assert.rejects(prepare(context), /Whisper model is incomplete/)
  } finally {
    assert.ok(root.startsWith(cache + path.sep))
    fs.rmSync(root, { recursive: true, force: true })
  }
})
