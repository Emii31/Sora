const fs = require('fs');
const path = require('path');

const htmlPath = path.join(__dirname, '../templates/index.html');
const html = fs.readFileSync(htmlPath, 'utf8');

const elements = {};
function getElement(id) {
    if (!elements[id]) {
        elements[id] = {
            textContent: '',
            innerHTML: '',
            classList: { add: () => {}, remove: () => {}, toggle: () => {} },
            addEventListener: () => {},
            focus: () => {}
        };
    }
    return elements[id];
}

global.document = {
    getElementById: getElement,
    querySelectorAll: () => []
};

// Extract _obQuestions, _obRender, _obQuestions array and functions
// Let's execute the functions by extracting them between known markers
const startIdx = html.indexOf('var _obQuestions = [');
const endIdx = html.indexOf('function _obSelect(key, value)');
const obCode = html.substring(startIdx, endIdx);

const renderFnMatch = html.match(/function _obRender\(\) \{[\s\S]*?\n\}/);
const nextFnMatch = html.match(/function _obNext\(skip\) \{[\s\S]*?\n\}/);

let codeToRun = obCode + '\n' + renderFnMatch[0];

try {
    eval(codeToRun);
    _obStep = 0;
    _obRender();
    const step0_text = document.getElementById('obNext').textContent;
    const step0_q = document.getElementById('obQuestion').textContent;

    _obStep = _obQuestions.length - 1;
    _obRender();
    const last_text = document.getElementById('obNext').textContent;

    console.log(JSON.stringify({ step0_text, step0_q, last_text }));
} catch (e) {
    console.error("ERROR:", e);
    process.exit(1);
}
