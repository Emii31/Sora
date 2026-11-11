const fs = require('fs');
const vm = require('vm');

const htmlContent = fs.readFileSync('templates/index.html', 'utf8');

const sandbox = {
  window: {
    devicePixelRatio: 1,
    CHARACTER: { name: 'Sora' },
    MiruAndroid: {
      getDeviceName: () => ''
    }
  },
  document: {
    createElement: (tag) => ({
      id: '',
      style: {},
      innerHTML: '',
      removed: false,
      remove() { this.removed = true; }
    }),
    body: {
      appendChild: (el) => {
        sandbox._appendedElements = sandbox._appendedElements || [];
        sandbox._appendedElements.push(el);
      }
    },
    getElementById: (id) => {
      if (sandbox._elements && sandbox._elements[id]) return sandbox._elements[id];
      if (sandbox._appendedElements) {
        return sandbox._appendedElements.find(el => el.id === id) || null;
      }
      return null;
    }
  },
  setTimeout: (fn) => fn(),
  localStorage: {
    _store: {},
    getItem(k) { return this._store[k] || null; },
    setItem(k, v) { this._store[k] = String(v); },
    removeItem(k) { delete this._store[k]; }
  },
  escapeHtml: (str) => {
    if (!str) return '';
    return String(str).replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>');
  }
};

vm.createContext(sandbox);

function extractSnippet(startStr, endStr) {
  const start = htmlContent.indexOf(startStr);
  if (start === -1) throw new Error('Start not found: ' + startStr);
  let depth = 0;
  let started = false;
  for (let i = start; i < htmlContent.length; i++) {
    if (htmlContent[i] === '{') {
      depth++;
      started = true;
    } else if (htmlContent[i] === '}') {
      depth--;
    }
    if (started && depth === 0) {
      return htmlContent.slice(start, i + 1);
    }
  }
  throw new Error('Unterminated snippet starting with: ' + startStr);
}

// Load _onApkUpdateProgress
console.log('Extracting _onApkUpdateProgress...');
const progressFn = extractSnippet("window._onApkUpdateProgress = function", "function _initBootstrap");
vm.runInContext(progressFn, sandbox);
console.log('Progress callback loaded');

function runProgressTest(state, expectedLabel, expectedBtnText, expectedBtnDisabled) {
  const label = { id: 'apkUpdateLabel', textContent: '' };
  const btn = { id: 'apkUpdateBtn', textContent: '', disabled: false };
  sandbox._elements = { apkUpdateLabel: label, apkUpdateBtn: btn };
  sandbox.window._onApkUpdateProgress({ state: state, pct: 50, downloaded: 500, total: 1000 });

  const okLabel = label.textContent === expectedLabel;
  const okBtn = btn.textContent === expectedBtnText;
  const okDisabled = btn.disabled === expectedBtnDisabled;
  console.log(`  state=${state}: label="${label.textContent}" btn="${btn.textContent}" disabled=${btn.disabled}`);
  if (!okLabel) { console.error(`FAIL: label mismatch (expected "${expectedLabel}")`); process.exit(1); }
  if (!okBtn) { console.error(`FAIL: button text mismatch (expected "${expectedBtnText}")`); process.exit(1); }
  if (!okDisabled) { console.error(`FAIL: button disabled state mismatch (expected ${expectedBtnDisabled})`); process.exit(1); }
  console.log(`  PASS: ${state}`);
}

console.log('\n--- Progress callback tests ---');
runProgressTest('running', 'Downloading… 50%', 'Downloading', true);
runProgressTest('done', 'Download finished, preparing to install…', 'Downloaded', false);
runProgressTest('error', 'Download failed, please retry', 'Retry', false);

// Verify _checkAppUpdate returns early and makes no fetch call
console.log('\n--- _checkAppUpdate no-metadata-request test ---');
const checkFn = extractSnippet("function _checkAppUpdate", "window._onApkUpdateProgress");
let fetchCalled = false;
sandbox.fetch = () => { fetchCalled = true; return Promise.resolve({}); };
sandbox.window.MiruAndroid = { getAppVersionCode: () => 99 };
vm.runInContext(checkFn, sandbox);
sandbox._checkAppUpdate();
if (fetchCalled) {
  console.error('FAIL: _checkAppUpdate made a metadata request despite the early return');
  process.exit(1);
}
console.log('PASS: _checkAppUpdate returns early, no fetch call');

// Verify no mixed Chinese labels remain in the translated regions
console.log('\n--- Mixed-language label scan ---');
const regions = [
  htmlContent.slice(htmlContent.indexOf("window._handleApkUpdateClick"), htmlContent.indexOf("function _initBootstrap")),
];
const chinesePattern = /[一-鿿]/;
let found = false;
for (let i = 0; i < regions.length; i++) {
  if (chinesePattern.test(regions[i])) {
    console.error('FAIL: Chinese characters found in APK update region ' + i);
    found = true;
  }
}
if (found) process.exit(1);
console.log('PASS: No Chinese characters in APK update region');

console.log('\nAll Phase 2B.21 APK update DOM assertions passed successfully.');