const workflowName = document.getElementById('workflowName');
const workflowGoal = document.getElementById('workflowGoal');
const generatedAt = document.getElementById('generatedAt');
const analysisStatus = document.getElementById('analysisStatus');
const totalItems = document.getElementById('totalItems');
const activeSources = document.getElementById('activeSources');
const keywordInput = document.getElementById('keywordInput');
const keywordChips = document.getElementById('keywordChips');
const signalGrid = document.getElementById('signalGrid');
const sourceList = document.getElementById('sourceList');
const itemList = document.getElementById('itemList');
const refreshButton = document.getElementById('refreshButton');
const saveKeywordsButton = document.getElementById('saveKeywordsButton');
const configButton = document.getElementById('configButton');
const externalButton = document.getElementById('externalButton');
const folderButton = document.getElementById('folderButton');
const promptButton = document.getElementById('promptButton');
const runStatus = document.getElementById('runStatus');

function cleanStatus(value) {
  if (!value) return 'unknown';
  return value.length > 120 ? `${value.slice(0, 120)}...` : value;
}

function splitKeywords(value) {
  return value
    .split(/[,，、\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderChips(keywords) {
  keywordChips.innerHTML = keywords.map((item) => `<span class="chip">${item}</span>`).join('');
}

function badgeClass(signal) {
  if (signal === '爆发') return 'badge hot';
  if (signal === '观察') return 'badge watch';
  return 'badge';
}

function renderSignals(trends = []) {
  signalGrid.innerHTML = trends.length
    ? trends.slice(0, 6).map((item) => `
      <article class="signal-card">
        <span class="${badgeClass(item.signal)}">${item.signal || '观察'}</span>
        <strong>${item.name || '未命名信号'}</strong>
        <p>${item.why || ''}</p>
      </article>
    `).join('')
    : '<p>还没有形成足够信号，先运行一次任务。</p>';
}

function renderSources(statuses = []) {
  sourceList.innerHTML = statuses.map((row) => `
    <div class="source-row">
      <div>
        <strong>${row.source}</strong>
        <span>${row.status}</span>
      </div>
      <strong>${row.count}</strong>
    </div>
  `).join('');
}

function renderItems(items = []) {
  itemList.innerHTML = items.slice(0, 12).map((item) => `
    <article class="item-row">
      <div>
        <strong><a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a></strong>
        <span>${item.source_name}${item.published_at ? ` · ${item.published_at.slice(0, 10)}` : ''}</span>
        <p>${item.summary || ''}</p>
      </div>
      <div class="score">${item.score}</div>
    </article>
  `).join('');
}

async function loadDashboard() {
  const data = await window.hotspotApp.dashboardData();
  if (!data) {
    workflowName.textContent = '尚未生成运行结果';
    workflowGoal.textContent = '点击“运行一次”开始抓取和分析。';
    generatedAt.textContent = '-';
    analysisStatus.textContent = '-';
    totalItems.textContent = '-';
    activeSources.textContent = '-';
    return;
  }

  const settings = data.settings || {};
  workflowName.textContent = settings.workflow_name || settings.report_title || 'Agent Skills 自动化工作台';
  workflowGoal.textContent = settings.workflow_goal || settings.report_subtitle || '自动运行并网页化展示结果。';
  generatedAt.textContent = data.generated_at || '-';
  analysisStatus.textContent = cleanStatus(data.stats?.analysis_status);
  totalItems.textContent = data.stats?.total_items ?? data.items?.length ?? 0;
  activeSources.textContent = data.stats?.active_sources ?? 0;

  const keywords = settings.keywords || [];
  keywordInput.value = keywords.join(', ');
  renderChips(keywords);
  renderSignals(data.analysis?.trend_radar || []);
  renderSources(data.statuses || []);
  renderItems(data.items || []);
}

window.hotspotApp.onReportStatus((payload) => {
  refreshButton.disabled = Boolean(payload.running);
  runStatus.textContent = cleanStatus(payload.message || '运行中...');
  if (!payload.running) {
    loadDashboard();
  }
});

refreshButton.addEventListener('click', async () => {
  refreshButton.disabled = true;
  runStatus.textContent = '正在运行任务...';
  await window.hotspotApp.runReport();
});

saveKeywordsButton.addEventListener('click', async () => {
  const keywords = splitKeywords(keywordInput.value);
  if (!keywords.length) {
    runStatus.textContent = '至少保留一个关键词。';
    return;
  }
  const result = await window.hotspotApp.saveKeywords(keywords);
  runStatus.textContent = result.message;
  if (result.ok) {
    renderChips(keywords);
  }
});

configButton.addEventListener('click', () => window.hotspotApp.openConfig());
externalButton.addEventListener('click', () => window.hotspotApp.openReportExternal());
folderButton.addEventListener('click', () => window.hotspotApp.openFolder());
promptButton.addEventListener('click', () => window.hotspotApp.openPromptDoc());

loadDashboard();
