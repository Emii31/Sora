const fs = require('fs');
const html = fs.readFileSync('templates/index.html', 'utf8');

// Extract functions using regex or eval
// Since index.html has global functions, we can extract them or evaluate relevant snippets.
// Let's extract _miruLocalDateKey, escapeHtml, and _buildEmotionCalendarHtml.

function extractFunc(name) {
  const idx = html.indexOf('function ' + name);
  if (idx === -1) {
    const idx2 = html.indexOf('var ' + name);
    if (idx2 === -1) throw new Error('Function not found: ' + name);
    // extract var ...
    return extractVar(name, idx2);
  }
  let depth = 0;
  let started = false;
  for (let i = idx; i < html.length; i++) {
    if (html[i] === '{') {
      depth++;
      started = true;
    } else if (html[i] === '}') {
      depth--;
    }
    if (started && depth === 0) {
      return html.slice(idx, i + 1);
    }
  }
  throw new Error('Unterminated function: ' + name);
}

function extractVar(name, idx) {
  let depth = 0;
  let started = false;
  for (let i = idx; i < html.length; i++) {
    if (html[i] === '{') {
      depth++;
      started = true;
    } else if (html[i] === '}') {
      depth--;
    }
    if (started && depth === 0) {
      return html.slice(idx, i + 1);
    }
  }
  return html.slice(idx, idx + 500);
}

// Let's execute helper definitions
const miruLocalDateKeyFn = extractFunc('_miruLocalDateKey');
const escapeHtmlFn = extractFunc('escapeHtml');
const buildEmotionCalendarHtmlFn = extractFunc('_buildEmotionCalendarHtml');

eval(miruLocalDateKeyFn);
eval(escapeHtmlFn);
eval(buildEmotionCalendarHtmlFn);

// Mock MOOD_COLORS if needed
global.MOOD_COLORS = { grateful: '#98D8C8', focused: '#6C9BD2', neutral: '#AAAAAA' };

const sampleData = {
  "2026-11-01": { dominant_mood: "grateful", count: 3, avg_valence: 0.5 },
  "2026-11-02": { dominant_mood: "focused", count: 5, avg_valence: 0.8 },
  "2026-11-15": { dominant_mood: "neutral", count: 2, avg_valence: 0.0 }
};

const res = _buildEmotionCalendarHtml("2026-11", sampleData);

console.log("TEST_RESULTS:", JSON.stringify({
  hasEmotionCalendar: res.includes("Emotion Calendar"),
  hasNov2026Header: res.includes("Nov 2026"),
  hasMonthlyOverview: res.includes("Monthly Overview"),
  hasWeekdayMon: res.includes("Mon"),
  hasWeekdaySun: res.includes("Sun"),
  hasDayDetailHandler: res.includes("_emotionDayDetail('2026-11-01')"),
  hasCtaBtn: res.includes("View Today's Details"),
  hasEntriesTooltip: res.includes("3 entries")
}, null, 2));

if (!res.includes("Emotion Calendar") || !res.includes("Nov 2026") || !res.includes("Monthly Overview") || !res.includes("Mon") || !res.includes("Sun") || !res.includes("_emotionDayDetail('2026-11-01')") || !res.includes("View Today's Details") || !res.includes("3 entries")) {
  console.error("Assertion failed in test_emotion_calendar_dom.js");
  process.exit(1);
} else {
  console.log("All DOM calendar verification checks passed successfully.");
}
