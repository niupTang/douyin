const fs = require('node:fs')
const path = require('node:path')

module.exports = async function prepareElectronRuntime(context) {
  const root = path.resolve(context.packager.projectDir)
  const modelRepo = path.join(root, 'build-resources', 'huggingface', 'hub', 'models--Systran--faster-whisper-base')
  const reference = path.join(modelRepo, 'refs', 'main')
  if (!fs.existsSync(reference)) throw new Error('Bundled Whisper base model is missing; run npm run whisper:bundle')
  const revision = fs.readFileSync(reference, 'utf8').trim()
  if (!/^[a-f0-9]{40,64}$/i.test(revision)) throw new Error('Bundled Whisper model revision is invalid')
  for (const name of ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt']) {
    const filename = path.join(modelRepo, 'snapshots', revision, name)
    if (!fs.existsSync(filename) || !fs.statSync(filename).isFile() || fs.statSync(filename).size === 0) {
      throw new Error(`Bundled Whisper model is incomplete: ${name}`)
    }
  }
  const source = path.join(root, 'node_modules', 'electron', 'dist')
  const target = path.join(root, 'build-resources', 'electron-runtime')
  if (!fs.existsSync(path.join(source, 'electron.exe'))) {
    throw new Error('Install Electron before building the desktop app')
  }
  if (!target.startsWith(root + path.sep) || !/^e:[\\/]/i.test(target)) {
    throw new Error('Electron staging must stay inside the E drive project')
  }
  fs.rmSync(target, { recursive: true, force: true })
  fs.cpSync(source, target, {
    recursive: true,
    filter(filename) {
      const relative = path.relative(source, filename).split(path.sep).join('/')
      return !relative.startsWith('resources/') || relative === 'resources/default_app.asar'
    }
  })
}
