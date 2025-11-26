// 시공간 스튜디오: 아이콘 클릭 시 자동으로 사이드패널 열기!

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((e) => console.error(e));
});

chrome.runtime.onStartup.addListener(() => {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((e) => console.error(e));
});