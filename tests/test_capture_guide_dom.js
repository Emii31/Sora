const fs = require('fs');
const vm = require('vm');

const htmlContent = fs.readFileSync('templates/index.html', 'utf8');

const sandbox = {
  window: {
    devicePixelRatio: 1,
    __MIRU_CLIENT_MODE__: true,
    __MIRU_DESKTOP_PLATFORM__: 'macos'
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
  CHARACTER: { name: 'Sora' },
  localStorage: {
    _store: {},
    getItem(k) { return this._store[k] || null; },
    setItem(k, v) { this._store[k] = String(v); },
    removeItem(k) { delete this._store[k]; }
  },
  _quickToggleScreenCapture: () => { sandbox._quickToggleCalled = true; },
  _startSensorHealthWatch: () => { sandbox._healthWatchCalled = true; },
  escapeHtml: (str) => {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
  _persistScreenCaptureSettings: (p) => { sandbox._persisted = p; }
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

// Load necessary functions
const functionsToLoad = [
  "function _showCaptureGuide",
  "function _acceptCaptureGuide",
  "function _dismissCaptureGuide",
  "function _showDesktopScreenshotGuide",
  "function _showClientScreenRecordingModal",
  "async function _permModalEnableWindows",
  "function _permModalDismissWithoutEnable",
  "function _permModalRetryNow",
  "function _permModalOpenSettings",
  "function _permModalDismiss",
  "function _acceptDesktopScreenshotGuide",
  "function _dismissDesktopScreenshotGuide"
];

for (const fnName of functionsToLoad) {
  try {
    const fnCode = extractSnippet(fnName, "function ");
    vm.runInContext(fnCode, sandbox);
  } catch (e) {
    // try fallback or extract until end of file if next function not found
    const start = htmlContent.indexOf(fnName);
    if (start !== -1) {
      // grab a chunk
      vm.runInContext(htmlContent.slice(start, start + 3000), sandbox);
    }
  }
}

// Test 1: macOS First Launch Modal
sandbox._appendedElements = [];
sandbox._showClientScreenRecordingModal(false, 'first', 'macos');
const macModal = sandbox._appendedElements.find(el => el.id === 'permModalOverlay');
if (!macModal || !macModal.innerHTML.includes('Let Sora accompany you') || !macModal.innerHTML.includes('Open System Settings → Screen Recording')) {
  console.error('Failed macOS first launch modal test:', macModal ? macModal.innerHTML : 'not found');
  process.exit(1);
}

// Test 2: Windows Disabled / Recovery Modal
sandbox._appendedElements = [];
sandbox._showClientScreenRecordingModal(false, 'disabled', 'windows');
const winModal = sandbox._appendedElements.find(el => el.id === 'permModalOverlay');
if (!winModal || !winModal.innerHTML.includes('Screen observation temporarily interrupted') || !winModal.innerHTML.includes('Retest Screen Capture')) {
  console.error('Failed Windows recovery modal test:', winModal ? winModal.innerHTML : 'not found');
  process.exit(1);
}

// Test 3: Linux First Launch Modal
sandbox._appendedElements = [];
sandbox._showClientScreenRecordingModal(false, 'first', 'linux');
const linuxModal = sandbox._appendedElements.find(el => el.id === 'permModalOverlay');
if (!linuxModal || !linuxModal.innerHTML.includes('Linux preview supports X11 desktops') || !linuxModal.innerHTML.includes('Test and Enable Screen Observation')) {
  console.error('Failed Linux modal test:', linuxModal ? linuxModal.innerHTML : 'not found');
  process.exit(1);
}

console.log('All Phase 2B.19 capture guide DOM assertions passed successfully.');
