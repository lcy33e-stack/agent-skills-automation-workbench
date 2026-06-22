const generatedAt = document.getElementById('generatedAt');
const analysisStatus = document.getElementById('analysisStatus');
const refreshButton = document.getElementById('refreshButton');
const configButton = document.getElementById('configButton');
const externalButton = document.getElementById('externalButton');
const folderButton = document.getElementById('folderButton');
const runStatus = document.getElementById('runStatus');
const reportFrame = document.getElementById('reportFrame');
const reportPane = document.querySelector('.report-pane');

function cleanStatus(value) {
  if (!value) return 'unknown';
  return value.length > 130 ? `${value.slice(0, 130)}...` : value;
}

async function loadReportInfo() {
  const info = await window.hotspotApp.reportInfo();
  generatedAt.textContent = info.generatedAt || '尚未生成';
  analysisStatus.textContent = cleanStatus(info.analysisStatus);
  if (info.reportExists) {
    reportPane.classList.remove('is-empty');
    reportFrame.src = `${info.reportUrl}?t=${Date.now()}`;
  } else {
    reportPane.classList.add('is-empty');
  }
}

window.hotspotApp.onReportStatus((payload) => {
  refreshButton.disabled = Boolean(payload.running);
  runStatus.textContent = cleanStatus(payload.message || '运行中...');
  if (!payload.running) {
    loadReportInfo();
  }
});

refreshButton.addEventListener('click', async () => {
  refreshButton.disabled = true;
  runStatus.textContent = '正在刷新报告...';
  await window.hotspotApp.runReport();
});

configButton.addEventListener('click', () => window.hotspotApp.openConfig());
externalButton.addEventListener('click', () => window.hotspotApp.openReportExternal());
folderButton.addEventListener('click', () => window.hotspotApp.openFolder());

loadReportInfo();

