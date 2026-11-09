const fs = require('fs');
const vm = require('vm');

const htmlContent = fs.readFileSync('templates/index.html', 'utf8');

// Mock DOM environment & globals needed by buildEmotionCurveHtml
const sandbox = {
  window: { devicePixelRatio: 1 },
  document: {
    getElementById: (id) => ({
      clientWidth: 600,
      offsetWidth: 600,
      getContext: () => ({
        setTransform: () => {},
        clearRect: () => {},
        fillStyle: '',
        font: '',
        textAlign: '',
        textBaseline: '',
        fillText: () => {},
        strokeStyle: '',
        setLineDash: () => {},
        beginPath: () => {},
        moveTo: () => {},
        lineTo: () => {},
        stroke: () => {},
        fill: () => {},
        arc: () => {},
      }),
      style: {}
    })
  },
  setTimeout: (fn) => fn(),
  MOOD_COLORS: {
    happy: '#FFD700',
    grateful: '#98D8C8'
  },
  _miruLocalDateKey: () => '2026-11-10',
  _compactEmotionEntries: (e) => e,
  _smoothSeriesCenter: (s) => s,
  _userValenceColor: (v) => '#fff',
  escapeHtml: (str) => {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
  drawMoodRiver: () => {},
  attachMoodRiverHover: (cv, cb) => {
    sandbox._capturedHoverCb = cb;
  },
  attachMoodRiverResize: () => {}
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

const glyphsStart = htmlContent.indexOf("const _EMO_SOURCE_GLYPHS =");
const glyphsEnd = htmlContent.indexOf("};", glyphsStart) + 2;
const sourceGlyphs = htmlContent.slice(glyphsStart, glyphsEnd);
vm.runInContext(sourceGlyphs, sandbox);

const buildFn = extractSnippet("function buildEmotionCurveHtml", "} // ===== Miru Emotion Visualization =====");
vm.runInContext(buildFn, sandbox);

// 1. Test empty view for today
const emptyToday = sandbox.buildEmotionCurveHtml([], '2026-11-10');
if (!emptyToday.includes('Emotion River · Today') || !emptyToday.includes('No emotion records for today')) {
  console.error('Failed empty today check:', emptyToday);
  process.exit(1);
}

// 2. Test empty view for past date
const emptyPast = sandbox.buildEmotionCurveHtml([], '2026-11-05');
if (!emptyPast.includes('Emotion River · 2026-11-05') || !emptyPast.includes('No emotion records for 2026-11-05')) {
  console.error('Failed empty past check:', emptyPast);
  process.exit(1);
}

// 3. Test populated view with 1 record (singular "1 record" check)
const singleRecord = [{
  mood: 'happy',
  valence: 0.8,
  intensity: 0.9,
  timestamp: '2026-11-10 10:15:00',
  source_type: 'chat',
  source: 'User chat input'
}];
const populatedSingle = sandbox.buildEmotionCurveHtml(singleRecord, '2026-11-10');
if (!populatedSingle.includes('1 record') || populatedSingle.includes('1 records')) {
  console.error('Failed singular record count check:', populatedSingle);
  process.exit(1);
}

// 4. Test populated view with multiple records
const multiRecords = [
  { mood: 'happy', valence: 0.8, intensity: 0.9, timestamp: '2026-11-10 10:15:00', source_type: 'chat', source: 'Chat 1' },
  { mood: 'grateful', valence: 0.5, intensity: 0.4, timestamp: '2026-11-10 12:30:00', source_type: 'auto_screenshot', source: 'Screenshot 2' }
];
const populatedMulti = sandbox.buildEmotionCurveHtml(multiRecords, '2026-11-10');
if (!populatedMulti.includes('2 records') || !populatedMulti.includes('Emotion Log') || !populatedMulti.includes('Sources')) {
  console.error('Failed multi record populated check:', populatedMulti);
  process.exit(1);
}

// 5. Test hover callback invocation and check English source label, timestamp, valence, and intensity
if (typeof sandbox._capturedHoverCb === 'function') {
  const rawPoint = {
    timestamp: '2026-11-10 10:15:00',
    source_type: 'chat',
    mood: 'happy',
    rawValence: 0.8,
    rawIntensity: 0.9,
    _repeatCount: 1
  };
  const tooltipHtml = sandbox._capturedHoverCb(rawPoint);
  console.log('Tooltip HTML:', tooltipHtml);
  if (!tooltipHtml.includes('Chat') || !tooltipHtml.includes('10:15:00') || !tooltipHtml.includes('+0.80') || !tooltipHtml.includes('0.90')) {
    console.error('Failed tooltip content check:', tooltipHtml);
    process.exit(1);
  }
} else {
  console.error('Hover callback was not captured');
  process.exit(1);
}

console.log('All Emotion River real-renderer DOM assertions passed successfully.');
