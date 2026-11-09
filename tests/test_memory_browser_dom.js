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
    CHARACTER: { name: 'Sora' }
};
global.CHARACTER = global.window.CHARACTER;

global.document = {
    getElementById: getElement,
    querySelectorAll: () => []
};

global.escapeHtml = function(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
};
global._renderMarkdown = function(str) { return str; };
global._journalFormatDate = function(dateStr) { return { day: '1', monthYear: '2026年11月', weekday: '周一' }; };
global._journalEntriesCache = [];
global._isMobile = false;

// Extract functions and variables
const startIdx = html.indexOf('var _DOMAIN_LABELS = {');
const endIdx = html.indexOf('function buildMemoryBrowserHtml(');
const codeSnippet = html.substring(startIdx, endIdx);

const buildBrowserMatch = html.match(/function buildMemoryBrowserHtml\(tree, slots\) \{[\s\S]*?\n\}/);
const detailRenderMatch = html.match(/function _renderSlotDetailHtml\(domain, slot, mainMd, relatedDdls\) \{[\s\S]*?\n\}/);
const coreMemoryMatch = html.match(/function _renderCoreMemoryHtml\(data\) \{[\s\S]*?\n\}/);
const coreBlockMatch = html.match(/function _renderCoreMemoryBlock\(title, content, chars\) \{[\s\S]*?\n\}/);
const journalListMatch = html.match(/function buildJournalListHtml\(entries\) \{[\s\S]*?\n\}/);
const journalBookMatch = html.match(/function buildJournalBookHtml\(journal\) \{[\s\S]*?\n\}/);

let codeToRun = codeSnippet + '\n' +
    (detailRenderMatch ? detailRenderMatch[0] : '') + '\n' +
    (buildBrowserMatch ? buildBrowserMatch[0] : '') + '\n' +
    (coreBlockMatch ? coreBlockMatch[0] : '') + '\n' +
    (coreMemoryMatch ? coreMemoryMatch[0] : '') + '\n' +
    (journalListMatch ? journalListMatch[0] : '') + '\n' +
    (journalBookMatch ? journalBookMatch[0] : '');

try {
    eval(codeToRun);

    const domainLabels = _DOMAIN_LABELS;

    const syntheticSlots = {
        project: {
            active: [
                { id: 'p1', title: 'Sora App', summary: 'Build companion app', last_active: '2026-11-10T12:00:00Z', created: '2026-11-01', status: 'active', pinned: true, aliases: ['app', 'sora'] },
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
    const detailHtml = _renderSlotDetailHtml('project', syntheticSlots.project.active[0], '# Hello\n- Test item', ['DDL 1: 2026-12-31']);
    const coreHtml = _renderCoreMemoryHtml({ blocks: { human: { content: 'User profile', chars: 12 }, persona: { content: 'Relationship profile', chars: 20 } } });
    const journalListHtml = buildJournalListHtml([{ date: '2026-11-09', title: 'Day 1', has_json: true, mood: { emoji: '🌟', label: 'Happy' } }]);
    const journalBookHtml = buildJournalBookHtml({ date: '2026-11-09', title: 'Day 1', narrative: 'Had a great day coding.', highlights: [{ time: '10:00', text: 'Started task' }], stats: { first_active: '09:00', last_active: '18:00', chat_count: 42 } });

    console.log(JSON.stringify({
        domainLabels,
        hasCorePortrait: browserHtml.includes('Core Portrait'),
        hasJournal: browserHtml.includes('Sora\'s Journal'),
        hasDDLs: browserHtml.includes('DDLs & Commitments'),
        hasProjectsTab: browserHtml.includes('Projects'),
        hasPeopleTab: browserHtml.includes('People'),
        emptyStateText: emptyGroupHtml,
        archivedSummaryText: groupHtml.includes('Archived (2)'),
        lastActiveText: groupHtml.includes('Last active: 2026-11-10'),
        pinnedTooltip: groupHtml.includes('title="Pinned"'),
        pausedTooltip: groupHtml.includes('title="Paused"'),
        archivedTooltip: groupHtml.includes('title="Archived"'),
        activeTooltip: groupHtml.includes('title="Active"'),
        detailActiveStatus: detailHtml.includes('Active'),
        detailSummary: detailHtml.includes('Summary:'),
        detailAliases: detailHtml.includes('Aliases:'),
        detailCreated: detailHtml.includes('Created: 2026-11-01'),
        detailLastActive: detailHtml.includes('Last active: 2026-11-10'),
        detailDeleteBtn: detailHtml.includes('Delete'),
        detailRelatedDdl: detailHtml.includes('Related DDL'),
        detailContentHeader: detailHtml.includes('Content'),
        coreTitle: coreHtml.includes('Core Portrait'),
        coreStatus: coreHtml.includes('Always injected into main chat and AttentionEngine'),
        coreBlock1: coreHtml.includes('My understanding of you'),
        coreBlock2: coreHtml.includes('My relationship with you'),
        journalListTitle: journalListHtml.includes('Sora\'s Journal'),
        journalListSubtitle: journalListHtml.includes('Watching over your days silently'),
        journalBookMemories: journalBookHtml.includes('Memories of the Day'),
        journalBookStats: journalBookHtml.includes('First active 09:00')
    }));
} catch (e) {
    console.error("ERROR:", e);
    process.exit(1);
}
