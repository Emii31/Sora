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

global.window = {
    CHARACTER: { name: 'Miru' }
};
global.CHARACTER = global.window.CHARACTER;

global.document = {
    getElementById: getElement,
    querySelectorAll: () => []
};

global.escapeHtml = function(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
};

// Extract functions and variables
const startIdx = html.indexOf('var _DOMAIN_LABELS = {');
const endIdx = html.indexOf('function viewSlotDetail(');
const codeSnippet = html.substring(startIdx, endIdx);

const buildBrowserMatch = html.match(/function buildMemoryBrowserHtml\(tree, slots\) \{[\s\S]*?\n\}/);

let codeToRun = codeSnippet + '\n' + buildBrowserMatch[0];

try {
    eval(codeToRun);

    const domainLabels = _DOMAIN_LABELS;

    const syntheticSlots = {
        project: {
            active: [
                { id: 'p1', title: 'Sora App', summary: 'Build companion app', last_active: '2026-11-10T12:00:00Z', status: 'active', pinned: true },
                { id: 'p5', title: 'Unpinned Active', summary: 'Active stuff', last_active: '2026-11-10', status: 'active', pinned: false }
            ],
            paused: [{ id: 'p2', title: 'Old project', summary: 'Paused stuff', last_active: '2026-10-01', status: 'paused' }],
            archived: [{ id: 'p3', title: 'Archived project', summary: 'Done', last_active: '2026-09-01', status: 'archived' }, { id: 'p4', title: 'Archived project 2', summary: 'Done 2', last_active: '2026-08-01', status: 'archived' }]
        },
        person: { active: [], paused: [], archived: [] },
        topic: { active: [], paused: [], archived: [] },
        self: { active: [], paused: [], archived: [] }
    };

    const browserHtml = buildMemoryBrowserHtml(null, syntheticSlots);
    const groupHtml = _buildSlotGroupHtml('project', syntheticSlots.project);
    const emptyGroupHtml = _buildSlotGroupHtml('person', syntheticSlots.person);

    console.log(JSON.stringify({
        domainLabels,
        hasCorePortrait: browserHtml.includes('Core Portrait'),
        hasJournal: browserHtml.includes('Miru\'s Journal'),
        hasDDLs: browserHtml.includes('DDLs & Commitments'),
        hasProjectsTab: browserHtml.includes('Projects'),
        hasPeopleTab: browserHtml.includes('People'),
        emptyStateText: emptyGroupHtml,
        archivedSummaryText: groupHtml.includes('Archived (2)'),
        lastActiveText: groupHtml.includes('Last active: 2026-11-10'),
        pinnedTooltip: groupHtml.includes('title="Pinned"'),
        pausedTooltip: groupHtml.includes('title="Paused"'),
        archivedTooltip: groupHtml.includes('title="Archived"'),
        activeTooltip: groupHtml.includes('title="Active"')
    }));
} catch (e) {
    console.error("ERROR:", e);
    process.exit(1);
}
