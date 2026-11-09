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
global._journalFormatDate = function(dateStr) { return { day: '1', monthYear: 'Mar 2026', weekday: 'Tue' }; };
global._journalEntriesCache = [];
global._isMobile = false;
global._ddlViewMode = 'list';
global._ddlCalendarMonth = null;

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

const ddlViewMatch = html.match(/function _buildDDLViewHTML\(items\) \{[\s\S]*?\n\}/);
const ddlStatBadgeMatch = html.match(/function _ddlStatBadge\(count, label, color\) \{[\s\S]*?\n\}/);
const ddlListMatch = html.match(/function _buildDDLListView\(active, completed\) \{[\s\S]*?\n\}/);
const ddlCardMatch = html.match(/function _ddlItemCard\(it, meta\) \{[\s\S]*?\n\}/);
const ddlCalendarMatch = html.match(/function _buildDDLCalendarView\(items\) \{[\s\S]*?\n\}/);

let codeToRun = codeSnippet + '\n' +
    (detailRenderMatch ? detailRenderMatch[0] : '') + '\n' +
    (buildBrowserMatch ? buildBrowserMatch[0] : '') + '\n' +
    (coreBlockMatch ? coreBlockMatch[0] : '') + '\n' +
    (coreMemoryMatch ? coreMemoryMatch[0] : '') + '\n' +
    (journalListMatch ? journalListMatch[0] : '') + '\n' +
    (journalBookMatch ? journalBookMatch[0] : '') + '\n' +
    (ddlViewMatch ? ddlViewMatch[0] : '') + '\n' +
    (ddlStatBadgeMatch ? ddlStatBadgeMatch[0] : '') + '\n' +
    (ddlListMatch ? ddlListMatch[0] : '') + '\n' +
    (ddlCardMatch ? ddlCardMatch[0] : '') + '\n' +
    (ddlCalendarMatch ? ddlCalendarMatch[0] : '');

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

    const syntheticCommitments = [
        { id: 'c1', title: 'Overdue Task', urgency: 'overdue', status: 'active', deadline: '2026-11-01', added: '2026-10-25T10:00:00Z' },
        { id: 'c2', title: 'Today Task', urgency: 'today', status: 'active', deadline: '2026-11-10', added: '2026-11-05T10:00:00Z' },
        { id: 'c3', title: 'Normal Task', urgency: 'normal', status: 'active', deadline: '2026-11-15', added: '2026-11-08T10:00:00Z' },
        { id: 'c4', title: 'Done Task', urgency: 'normal', status: 'completed', completed: '2026-11-09', added: '2026-11-01T10:00:00Z' }
    ];

    const browserHtml = buildMemoryBrowserHtml(null, syntheticSlots);
    const groupHtml = _buildSlotGroupHtml('project', syntheticSlots.project);
    const emptyGroupHtml = _buildSlotGroupHtml('person', syntheticSlots.person);
    const detailHtml = _renderSlotDetailHtml('project', syntheticSlots.project.active[0], '# Hello\n- Test item', ['DDL 1: 2026-12-31']);
    const coreHtml = _renderCoreMemoryHtml({ blocks: { human: { content: 'User profile', chars: 12 }, persona: { content: 'Relationship profile', chars: 20 } } });
    const journalListHtml = buildJournalListHtml([{ date: '2026-11-09', title: 'Day 1', has_json: true, mood: { emoji: '🌟', label: 'Happy' } }]);
    const journalBookHtml = buildJournalBookHtml({ date: '2026-11-09', title: 'Day 1', narrative: 'Had a great day coding.', highlights: [{ time: '10:00', text: 'Started task' }], stats: { first_active: '09:00', last_active: '18:00', chat_count: 42 } });

    const ddlViewHtml = _buildDDLViewHTML(syntheticCommitments);

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
        journalBookStats: journalBookHtml.includes('First active 09:00'),
        ddlHasCommitmentsHeader: ddlViewHtml.includes('Commitments'),
        ddlHasListBtn: ddlViewHtml.includes('List'),
        ddlHasCalendarBtn: ddlViewHtml.includes('Calendar'),
        ddlHasAddTitlePlaceholder: ddlViewHtml.includes('Commitment Title'),
        ddlHasActiveCount: ddlViewHtml.includes('Active') && ddlViewHtml.includes('3'),
        ddlHasOverdueCount: ddlViewHtml.includes('Overdue') && ddlViewHtml.includes('1'),
        ddlHasCompletedCount: ddlViewHtml.includes('Completed') && ddlViewHtml.includes('1'),
        ddlHasDueTodayLabel: ddlViewHtml.includes('Due Today'),
        ddlHasInprogressLabel: ddlViewHtml.includes('In Progress'),
        ddlHasCompletedSection: ddlViewHtml.includes('Completed (1)'),
        ddlNoChineseLabels: !ddlViewHtml.includes('DDL 追踪') && !ddlViewHtml.includes('进行中') && !ddlViewHtml.includes('逾期') && !ddlViewHtml.includes('已完成') && !ddlViewHtml.includes('承诺标题')
    }));
} catch (e) {
    console.error("ERROR:", e);
    process.exit(1);
}
