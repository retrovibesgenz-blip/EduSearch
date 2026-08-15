const $ = id => document.getElementById(id);
const home = $('home'), browser = $('browser'), bar = $('bar');
const frame = $('frame'), toolbar = $('toolbar'), loadbar = $('loadbar');
const fsx = $('fsx'), fsbtn = $('fsbtn'), qInput = $('q');
const tabsScroll = $('tabsScroll');

let tabs = [{url:'', hist:[], title:'New Tab'}];
let cur = 0;
let fs = false;

function renderTabs() {
  tabsScroll.innerHTML = '';
  tabs.forEach((t, i) => {
    const d = document.createElement('div');
    d.className = 'tab' + (i === cur ? ' active' : '');
    d.innerHTML = `<span class="tab-title">${t.title}</span><span class="tab-x" data-i="${i}">×</span>`;
    d.addEventListener('click', e => {
      if (e.target.dataset.i !== undefined) { closeTab(+e.target.dataset.i); return; }
      switchTab(i);
    });
    tabsScroll.appendChild(d);
  });
  tabsScroll.children[cur]?.scrollIntoView({inline:'nearest',block:'nearest'});
}

function switchTab(i) {
  cur = i;
  const t = tabs[cur];
  bar.value = t.url;
  loadbar.className = 'load-bar';
  if (t.url) {
    frame.src = '/proxy?url=' + encodeURIComponent(t.url);
    home.classList.add('hidden');
    browser.classList.add('active');
  } else {
    frame.src = 'about:blank';
    goHome();
  }
  renderTabs();
}

function newTab() {
  tabs.push({url:'', hist:[], title:'New Tab'});
  cur = tabs.length - 1;
  frame.src = 'about:blank';
  bar.value = '';
  home.classList.remove('hidden');
  browser.classList.add('active');
  qInput.value = '';
  qInput.focus();
  renderTabs();
}

function closeTab(i) {
  if (tabs.length === 1) { goHome(); return; }
  tabs.splice(i, 1);
  if (cur >= tabs.length) cur = tabs.length - 1;
  switchTab(cur);
}

function isUrl(s) { return /\.\w{2,}/.test(s) || /^https?:\/\//.test(s); }

function nav(url) {
  if (!url) return;
  if (!/^https?:\/\//.test(url)) url = 'https://' + url;
  tabs[cur].url = url;
  tabs[cur].hist.push(url);
  bar.value = url;
  loadbar.className = 'load-bar go';
  frame.src = '/proxy?url=' + encodeURIComponent(url);
  home.classList.add('hidden');
  browser.classList.add('active');
  updateTabTitle(url);
  renderTabs();
}

function updateTabTitle(url) {
  try {
    const h = new URL(url).hostname.replace('www.', '');
    tabs[cur].title = h;
  } catch(e) {}
}

function search(q) { nav('https://html.duckduckgo.com/html/?q=' + encodeURIComponent(q)); }

function homeGo() {
  const v = qInput.value.trim();
  if (!v) return;
  isUrl(v) ? nav(v) : search(v);
}

function barGo() {
  const v = bar.value.trim();
  if (!v) return;
  isUrl(v) ? nav(v) : search(v);
}

function go(url) { nav(url); }

function goHome() {
  if (fs) exitFs();
  const allBlank = tabs.every(t => !t.url);
  if (!allBlank || tabs[cur].url) {
    tabs[cur] = {url:'', hist:[], title:'New Tab'};
  }
  browser.classList.remove('active');
  home.classList.remove('hidden');
  bar.value = '';
  qInput.value = '';
  qInput.focus();
  frame.src = 'about:blank';
  renderTabs();
}

function goBack() {
  const h = tabs[cur].hist;
  if (h.length > 1) {
    h.pop();
    const prev = h[h.length - 1];
    tabs[cur].url = prev;
    bar.value = prev;
    updateTabTitle(prev);
    loadbar.className = 'load-bar go';
    frame.src = '/proxy?url=' + encodeURIComponent(prev);
    renderTabs();
  }
}

function reload() {
  const u = tabs[cur].url;
  if (u) {
    loadbar.className = 'load-bar go';
    frame.src = '/proxy?url=' + encodeURIComponent(u);
  }
}

frame.addEventListener('load', () => {
  loadbar.className = 'load-bar done';
  setTimeout(() => { loadbar.className = 'load-bar'; }, 400);
});

window.addEventListener('message', e => {
  if (!e.data || e.data.t !== 'nav' || !e.data.url) return;
  const url = e.data.url;
  if (/^(about:|javascript:|data:|blob:)/.test(url)) return;
  if (url.includes('/proxy?url=')) return;
  if (url === tabs[cur].url) return;
  tabs[cur].url = url;
  tabs[cur].hist.push(url);
  bar.value = url;
  updateTabTitle(url);
  loadbar.className = 'load-bar go';
  frame.src = '/proxy?url=' + encodeURIComponent(url);
  renderTabs();
});

function toggleFs() { fs ? exitFs() : enterFs(); }
function enterFs() {
  fs = true;
  toolbar.classList.add('hidden');
  fsx.classList.add('show');
  fsbtn.classList.add('on');
}
function exitFs() {
  fs = false;
  toolbar.classList.remove('hidden');
  fsx.classList.remove('show');
  fsbtn.classList.remove('on');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (fs) exitFs();
    else if (browser.classList.contains('active')) goHome();
  }
  if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); goBack(); }
  if (e.altKey && e.key === 'f') { e.preventDefault(); toggleFs(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
    e.preventDefault();
    if (browser.classList.contains('active')) { bar.focus(); bar.select(); }
    else { qInput.focus(); qInput.select(); }
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'r' && browser.classList.contains('active')) {
    e.preventDefault(); reload();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 't') { e.preventDefault(); newTab(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'w') { e.preventDefault(); closeTab(cur); }
});

renderTabs();
qInput.focus();
