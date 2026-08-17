const $ = id => document.getElementById(id);
const home = $('home'), browser = $('browser'), bar = $('bar');
const frame = $('frame'), toolbar = $('toolbar'), loadbar = $('loadbar');
const fsx = $('fsx'), fsbtn = $('fsbtn'), qInput = $('q');
const tabsScroll = $('tabsScroll');

let tabs = [{url:'', hist:[], title:'New Tab'}];
let cur = 0;
let fs = false;

function barDisplay(url) {
  if (!url) return '';
  if (url.startsWith('/search?q=')) {
    try { return decodeURIComponent(url.slice(10)).replace(/\+/g, ' '); } catch(e) { return url; }
  }
  return url;
}

function loadUrl(url) {
  if (!url) return;
  frame.src = url.startsWith('/search?q=') ? url : '/proxy?url=' + encodeURIComponent(url);
}

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
  bar.value = barDisplay(t.url);
  loadbar.className = 'load-bar';
  if (t.url) {
    loadUrl(t.url);
    home.classList.add('hidden');
    browser.classList.add('active');
  } else {
    frame.src = 'about:blank';
    browser.classList.add('active');
    home.classList.remove('hidden');
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

function search(q) {
  if (!q) return;
  const searchUrl = '/search?q=' + encodeURIComponent(q);
  tabs[cur].url = searchUrl;
  tabs[cur].hist.push(searchUrl);
  tabs[cur].title = q.length > 18 ? q.slice(0, 16) + '…' : q;
  bar.value = q;
  loadbar.className = 'load-bar go';
  frame.src = searchUrl;
  home.classList.add('hidden');
  browser.classList.add('active');
  renderTabs();
}

function updateTabTitle(url) {
  try {
    tabs[cur].title = new URL(url).hostname.replace('www.', '');
  } catch(e) {}
}

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
  tabs[cur] = {url:'', hist:[], title:'New Tab'};
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
    bar.value = barDisplay(prev);
    if (!prev.startsWith('/search?q=')) updateTabTitle(prev);
    loadbar.className = 'load-bar go';
    loadUrl(prev);
    renderTabs();
  }
}

function reload() {
  const u = tabs[cur].url;
  if (u) {
    loadbar.className = 'load-bar go';
    loadUrl(u);
  }
}

frame.addEventListener('load', () => {
  loadbar.className = 'load-bar done';
  setTimeout(() => { loadbar.className = 'load-bar'; }, 400);
});

window.addEventListener('message', e => {
  if (!e.data) return;
  if (e.data.t === 'home') { goHome(); return; }
  if (e.data.t === 'search' && e.data.q) { search(e.data.q); return; }
  if (e.data.t !== 'nav' || !e.data.url) return;
  const url = e.data.url;
  if (/^(about:|javascript:|data:|blob:)/.test(url)) return;
  if (url.includes('/proxy?url=')) return;
  if (url === tabs[cur].url) return;
  nav(url);
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
