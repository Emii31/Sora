const fs = require('fs');
const vm = require('vm');

const htmlContent = fs.readFileSync('templates/index.html', 'utf8');

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
  _compactMiruEmotionEntries: (e) => e,
  _miruValenceColor: (v) => '#FFB7C5',
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

const riverFn = extractSnippet("function buildMiruEmotionRiver", "function _ddlViewMode");
vm.runInContext("var _ddlViewMode = 'list';\n" + riverFn, sandbox);

const htmlFn = extractSnippet("function buildMiruEmotionHtml", "function _miruValenceColor");
vm.runInContext(htmlFn, sandbox);

// 1. Test empty history view
const emptyCur = { current: { mood: 'Calm', valence: 0.0, arousal: 0.2 }, days_together: 0, first_meet_date: '2026-11-01' };
const emptyRes = sandbox.buildMiruEmotionHtml(emptyCur, []);
if (!emptyRes.includes('Mood Dashboard') || !emptyRes.includes('Day 1') || !emptyRes.includes('No mood records yet')) {
  console.error('Failed empty Miru emotion check:', emptyRes);
  process.exit(1);
}

// 2. Test populated history view (singular day vs plural days, singular entry vs plural entries)
const historyPopulated = [
  { mood: 'Warm', valence: 0.7, arousal: 0.5, timestamp: '2026-11-10 10:00:00', reason: 'Feeling close' },
  { mood: 'Tender', valence: 0.9, arousal: 0.6, timestamp: '2026-11-10 12:00:00', reason: 'Deep talk' }
];
const populatedRes = sandbox.buildMiruEmotionHtml(emptyCur, historyPopulated);
if (!populatedRes.includes('Mood River') || !populatedRes.includes('Mood Log') || !populatedRes.includes('2 entries') || !populatedRes.includes('Warm')) {
  console.error('Failed populated Miru emotion check:', populatedRes);
  process.exit(1);
}

// 3. Test hover callback
if (typeof sandbox._capturedHoverCb === 'function') {
  const rawPoint = {
    timestamp: '2026-11-10 10:00:00',
    mood: 'Warm',
    v: 0.7,
    arousal: 0.5,
    color: '#FFB7C5',
    reason: 'Feeling close',
    _repeatCount: 1
  };
  const tip = sandbox._capturedHoverCb(rawPoint);
  console.log('Miru Tooltip HTML:', tip);
  if (!tip.includes('Warm') || !tip.includes('+0.70') || !tip.includes('arousal 0.50') || !tip.includes('Feeling close')) {
    console.error('Failed Miru hover callback tooltip content check:', tip);
    process.exit(1);
  }
} else {
  console.error('Miru hover callback was not captured');
  process.exit(1);
}

console.log('All My Mood dashboard DOM assertions passed successfully.');
