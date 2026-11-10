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
    return String(str).replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>').replace(/"/g, '"');
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

// Load the function
console.log('Extracting function...');
const fnCode = extractSnippet("function _showBgKeepAliveGuide", "function ");
console.log('Running function in context...');
vm.runInContext(fnCode, sandbox);
console.log('Function loaded successfully');

function runTest(deviceName, expectedBrand, expectedTextSnippets) {
  sandbox._appendedElements = [];
  sandbox.localStorage._store = {}; // Reset localStorage for each test
  sandbox.window.MiruAndroid.getDeviceName = () => deviceName;

  console.log(`Running test for ${deviceName} (brand=${expectedBrand})...`);
  sandbox._showBgKeepAliveGuide();

  const overlay = sandbox._appendedElements.find(el => el.id === 'bgKeepAliveOverlay');
  if (!overlay) {
    console.error(`FAIL: ${deviceName} - No overlay rendered`);
    process.exit(1);
  }

  for (const snippet of expectedTextSnippets) {
    if (!overlay.innerHTML.includes(snippet)) {
      console.error(`FAIL: ${deviceName} - Missing text: "${snippet}"`);
      console.error(`InnerHTML: ${overlay.innerHTML}`);
      process.exit(1);
    }
  }
  console.log(`PASS: ${deviceName} (brand=${expectedBrand})`);
}

function runSuppressionTest() {
  sandbox._appendedElements = [];
  sandbox.localStorage._store = { 'miru_bg_guide_shown': '1' };
  sandbox.window.MiruAndroid.getDeviceName = () => 'Samsung SM-G991B'; // Samsung

  sandbox._showBgKeepAliveGuide();

  const overlay = sandbox._appendedElements.find(el => el.id === 'bgKeepAliveOverlay');
  if (overlay) {
    console.error('FAIL: Suppression test - Overlay was rendered on second call');
    process.exit(1);
  }
  console.log('PASS: Suppression on second call');
}

// Test Samsung
runTest('Samsung SM-G991B', 'samsung', [
  'Background activity settings',
  'To ensure Miru can continuously observe the screen, please complete the following settings:',
  'Settings → Battery → Background usage restrictions → Never sleeping apps → Add Miru',
  'Got it'
]);

// Test Xiaomi
runTest('Xiaomi 13', 'xiaomi', [
  'Background activity settings',
  'To ensure Miru can continuously observe the screen, please complete the following settings:',
  'Settings → Apps → App management → Miru → Battery saver → Unrestricted',
  'Recents → long-press Miru → lock',
  'Got it'
]);

// Test vivo
runTest('vivo X90', 'vivo', [
  'Background activity settings',
  'To ensure Miru can continuously observe the screen, please complete the following settings:',
  'Settings → Battery → Background power management → find Miru → Allow background activity',
  'Recents → swipe down the Miru card → tap the lock',
  'Got it'
]);

// Test OPPO/OnePlus/Realme
runTest('OnePlus 11', 'oppo', [
  'Background activity settings',
  'To ensure Miru can continuously observe the screen, please complete the following settings:',
  'Settings → Battery → Auto-start management → find Miru → Allow',
  'Recents → swipe down the Miru card → lock',
  'Got it'
]);

// Test Huawei/Honor
runTest('HONOR Magic5', 'huawei', [
  'Background activity settings',
  'To ensure Miru can continuously observe the screen, please complete the following settings:',
  'Settings → Battery → Launch management → Miru → Manual management → Allow all',
  'Recents → swipe down the Miru card → lock',
  'Got it'
]);

// Test generic fallback (unknown brand)
runTest('Google Pixel 8', 'other', [
  'Background activity settings',
  'To ensure Miru can continuously observe the screen, please complete the following settings:',
  'Settings → Battery/App management → find Miru → Allow background activity',
  'Recents → lock Miru',
  'Got it'
]);

// Test suppression on second call
runSuppressionTest();

console.log('\nAll Phase 2B.20 Android background guide DOM assertions passed successfully.');