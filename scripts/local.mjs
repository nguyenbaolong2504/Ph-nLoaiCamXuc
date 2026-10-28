/** Run the Python app from npm without shell quoting or venv activation. */
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('..', import.meta.url));
const venvPython = join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const [command = 'help', ...args] = process.argv.slice(2);
const modules = { prepare: 'ai.prepare_fer2013', audit: 'ai.audit_dataset', train: 'ai.train', evaluate: 'ai.evaluate', compare: 'ai.compare_models' };

function isPython311(executable, prefix = []) {
  const probe = spawnSync(executable, [...prefix, '-c', 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'], {
    cwd: root, stdio: 'ignore', windowsHide: true, timeout: 10000,
  });
  return !probe.error && probe.status === 0;
}

function findPython() {
  const candidates = [
    ...(process.env.PYTHON ? [[process.env.PYTHON, []]] : []),
    ...(process.platform === 'win32' ? [['py', ['-3.11']]] : []),
    ['python3.11', []], ['python', []], ['python3', []],
  ];
  for (const [executable, prefix] of candidates) {
    if (isPython311(executable, prefix)) return { executable, prefix };
  }
  throw new Error('Can cai Python 3.11 (chon Add Python to PATH), sau do chay npm run setup lai.');
}

async function run(executable, parameters) {
  await new Promise((resolve, reject) => {
    const child = spawn(executable, parameters, { cwd: root, stdio: 'inherit', shell: false });
    const stop = signal => {
      // On Windows, Ctrl+C already reaches the Python console process.
      if (process.platform !== 'win32' || signal !== 'SIGINT') child.kill(signal);
    };
    const interrupt = () => stop('SIGINT');
    const terminate = () => stop('SIGTERM');
    process.once('SIGINT', interrupt); process.once('SIGTERM', terminate);
    const cleanup = () => {
      process.removeListener('SIGINT', interrupt); process.removeListener('SIGTERM', terminate);
    };
    child.once('error', error => { cleanup(); reject(error); });
    child.once('exit', (code, signal) => {
      cleanup();
      if (code === 0) resolve();
      else {
        const error = new Error(signal ? `Da dung (${signal}).` : `Lenh Python ket thuc voi ma ${code}.`);
        error.exitCode = code || 1; reject(error);
      }
    });
  });
}

function requireVenv() {
  if (!existsSync(venvPython)) throw new Error('Chua co moi truong Python. Trong thu muc backend, chay: npm run setup');
  if (!isPython311(venvPython)) throw new Error('.venv hien tai khong dung Python 3.11. Tao moi truong Python 3.11 truoc khi tiep tuc.');
}

try {
  if (command === 'setup') {
    if (!existsSync(venvPython)) {
      const python = findPython();
      console.log('Tao moi truong .venv voi Python 3.11...');
      await run(python.executable, [...python.prefix, '-m', 'venv', join(root, '.venv')]);
    }
    requireVenv();
    await run(venvPython, ['-m', 'pip', 'install', '--disable-pip-version-check', '--no-cache-dir', '-r', join(root, 'backend/requirements.txt')]);
    await run(venvPython, [join(root, 'scripts/setup.py')]);
    await run(venvPython, [join(root, 'scripts/download_models.py')]);
    console.log('\nDa cai backend. Dat MONGO_URI trong .env, bat MongoDB, roi chay npm run dev.');
    console.log('Tai khoan quan tri va mat khau khoi tao: xem file .env o thu muc goc.');
  } else if (command === 'help' || command === '--help' || command === '-h') {
    console.log('Trong backend: npm run setup | npm run dev | npm run models | npm run setup:ai');
    console.log('Train: npm run train -- --dataset data/datasets/fer2013 --model mobilenet_v3_small --output ai/runs/mobile-v1');
    console.log('Duong dan dataset/output tinh tu thu muc goc du an, ke ca khi go lenh trong backend.');
  } else if (command === 'models') {
    requireVenv();
    await run(venvPython, [join(root, 'scripts/download_models.py')]);
  } else if (command === 'setup-ai') {
    requireVenv();
    await run(venvPython, ['-m', 'pip', 'install', '--disable-pip-version-check', '--no-cache-dir', '-r', join(root, 'ai/requirements.txt')]);
  } else if (command === 'dev' || command === 'start') {
    requireVenv();
    await run(venvPython, [join(root, 'scripts/run_backend.py'), ...(command === 'dev' ? ['--reload'] : []), ...args]);
  } else if (command in modules) {
    requireVenv();
    await run(venvPython, ['-m', modules[command], ...args]);
  } else {
    throw new Error(`Khong co lenh "${command}". Chay node scripts/local.mjs --help de xem huong dan.`);
  }
} catch (error) {
  console.error(`\n${error.message}`);
  process.exitCode = error.exitCode || 1;
}
