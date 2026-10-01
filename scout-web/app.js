'use strict';
const API = 'https://expa.beyondhorizon.dev/scout-api';
const $ = id => document.getElementById(id);
let password = sessionStorage.getItem('scout-password') || '';
let job = null;
let answer = '';
let timer = null;
let stoppedPolling = false;
const terminal = new Set(['completed', 'partial', 'error', 'stopped']);

function foldSources(root) {
  const key = /^[a-z][a-z0-9_]*:\d+$/i;
  // Plain source keys occur alongside Markdown links as well as inside code.
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const texts = [];
  while (walker.nextNode()) {
    if (!walker.currentNode.parentElement.closest('a,code,pre')) texts.push(walker.currentNode);
  }
  texts.forEach(node => {
    const parts = node.textContent.split(/(\b[a-z][a-z0-9_]*:\d+\b)/gi);
    if (parts.length === 1) return;
    const fragment = document.createDocumentFragment();
    parts.forEach(part => {
      if (key.test(part)) {
        const code = document.createElement('code'); code.textContent = part; fragment.append(code);
      } else fragment.append(document.createTextNode(part));
    });
    node.replaceWith(fragment);
  });
  const citation = node => node.nodeType === Node.ELEMENT_NODE &&
    (node.matches('a') || (node.matches('code') && key.test(node.textContent)));
  const separator = node => node.nodeType === Node.TEXT_NODE &&
    /^[\s.,;:·|()[\]—–-]*(?:(?:Ключи?|Источники?|source_keys?|Sources?)\s*:\s*)?[\s.,;:·|()[\]—–-]*$/i.test(node.textContent);
  function metadataAfter(node) {
    // A citation's author/date/time are one unit. Stop before ordinary prose.
    const siblings = [];
    for (let next = node.nextSibling; next; next = next.nextSibling) {
      if (next.nodeType !== Node.TEXT_NODE && !next.matches?.('strong,em,span,code')) break;
      siblings.push(next);
    }
    const text = siblings.map(item => item.textContent).join('');
    const match = text.match(/^[\s,;·—–-]+(?:[^,;\n().!?]{1,100},\s*)?(?:\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})(?:\s*[,·]\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*[–—-]\s*\d{1,2}:\d{2}(?::\d{2})?)?)?/);
    if (!match) return [];
    let remaining = match[0].length;
    const range = document.createRange(); range.setStartAfter(node);
    for (const sibling of siblings) {
      const walker = document.createTreeWalker(sibling, NodeFilter.SHOW_TEXT);
      let textNode = sibling.nodeType === Node.TEXT_NODE ? sibling : walker.nextNode();
      while (textNode) {
        if (remaining <= textNode.length) {
          range.setEnd(textNode, remaining);
          const fragment = range.extractContents();
          const parts = [...fragment.childNodes];
          node.after(fragment);
          return parts;
        }
        remaining -= textNode.length;
        textNode = walker.nextNode();
      }
    }
    return [];
  }
  let number = 0;
  const parents = new Set([...root.querySelectorAll('a,code')].filter(node => citation(node) && !node.closest('pre')).map(node => node.parentElement));
  parents.forEach(parent => {
    let node = parent.firstChild;
    while (node) {
      if (!citation(node)) { node = node.nextSibling; continue; }
      const nodes = [node];
      let end = node;
      const metadata = metadataAfter(end);
      if (metadata.length) { nodes.push(...metadata); end = metadata.at(-1); }
      while (end.nextSibling) {
        let next = end.nextSibling;
        const between = [];
        while (next && separator(next)) { between.push(next); next = next.nextSibling; }
        if (!next || !citation(next)) break;
        nodes.push(...between, next); end = next;
        const metadata = metadataAfter(end);
        if (metadata.length) { nodes.push(...metadata); end = metadata.at(-1); }
      }
      const before = node.previousSibling;
      const after = end.nextSibling;
      // Reuse existing parentheses rather than adding a second pair.
      const opening = before?.nodeType === Node.TEXT_NODE &&
        before.textContent.match(/\(\s*(?:(?:Источники?|Ключи?|Sources?|source_keys?)\s*:\s*)?$/i);
      if (opening && after?.nodeType === Node.TEXT_NODE && /^\s*\)/.test(after.textContent)) {
        before.textContent = before.textContent.slice(0, opening.index) + opening[0].replace(/^\(\s*/, '');
        after.textContent = after.textContent.replace(/^\s*\)/, '');
      }
      if (before?.nodeType === Node.TEXT_NODE) {
        const label = before.textContent.match(/(^|[\s(])(?:Источники?|Ключи?|Sources?|source_keys?)\s*:\s*$/i);
        if (label) {
          const suffix = before.splitText(label.index + label[1].length);
          nodes.unshift(suffix); node = suffix;
        }
      }
      const wrapper = document.createElement('span'); wrapper.className = 'sources';
      const toggle = document.createElement('button');
      toggle.type = 'button'; toggle.className = 'source-toggle'; toggle.textContent = 'источники';
      toggle.setAttribute('aria-expanded', 'false');
      const content = document.createElement('span'); content.hidden = true;
      content.id = `sources-${++number}`;
      toggle.setAttribute('aria-controls', content.id);
      toggle.setAttribute('aria-label', 'Показать источники');
      node.before(wrapper);
      content.append(': ', ...nodes);
      const label = document.createElement('span'); label.className = 'source-label';
      label.append('(', toggle);
      wrapper.append(label, content, ')');
      toggle.addEventListener('click', () => {
        content.hidden = !content.hidden;
        wrapper.classList.toggle('is-open', !content.hidden);
        toggle.setAttribute('aria-expanded', String(!content.hidden));
        toggle.setAttribute('aria-label', content.hidden ? 'Показать источники' : 'Свернуть источники');
      });
      node = wrapper.nextSibling;
    }
  });
}

function resizeQuestion() {
  const field = $('question');
  field.style.height = 'auto';
  field.style.height = `${Math.min(240, field.scrollHeight)}px`;
}

async function request(path, options = {}) {
  const response = await fetch(API + path, {...options, cache: 'no-store', headers: {
    'Content-Type': 'application/json', 'X-Scout-Password': password, ...options.headers
  }});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem('scout-password');
      $('login').hidden = false;
      $('ask').hidden = true;
    }
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось выполнить запрос.');
  }
  return data;
}

function display(data) {
  job = data;
  const running = !terminal.has(data.status);
  $('message').textContent = data.message;
  document.querySelector('.status').classList.toggle('running', running);
  $('action').textContent = running ? 'Остановить' : 'Спросить';
  $('question').readOnly = running;
  $('question').value = data.question;
  resizeQuestion();
  clearInterval(timer);
  const tick = () => {
    const seconds = running ? Math.max(0, Math.round(Date.now() / 1000 - data.started_at)) : data.elapsed;
    $('elapsed').textContent = `${String(Math.floor(seconds / 60)).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')}`;
  };
  tick();
  if (running) timer = setInterval(tick, 1000);
  answer = data.answer || '';
  $('answer').hidden = !answer;
  $('copy').hidden = !answer;
  if (answer) {
    $('answer').innerHTML = DOMPurify.sanitize(marked.parse(answer), {FORBID_TAGS: ['img', 'form', 'input', 'style']});
    $('answer').querySelectorAll('a').forEach(a => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
    foldSources($('answer'));
    $('answer').querySelectorAll('table').forEach(table => {
      const wrapper = document.createElement('div'); wrapper.className = 'table-wrap';
      table.before(wrapper); wrapper.append(table);
    });
  }
}

async function poll() {
  let failures = 0;
  const id = job.id;
  while (job && !terminal.has(job.status) && !stoppedPolling) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    try {
      const data = await request(`/jobs/${id}`);
      if (stoppedPolling || job.id !== id) return;
      display(data);
      failures = 0;
    } catch (error) {
      if (stoppedPolling || job.id !== id) return;
      $('message').textContent = 'Связь прервалась. Восстанавливаю…';
      if (++failures >= 5) {
        $('message').textContent = 'Связь прервалась. Обнови страницу: поиск сохранён.';
        clearInterval(timer);
        break;
      }
    }
  }
}

async function login() {
  await request('/auth');
  sessionStorage.setItem('scout-password', password);
  $('login').hidden = true;
  $('ask').hidden = false;
  $('question').focus();
  resizeQuestion();
  $('message').textContent = '';
  const id = localStorage.getItem('scout-job');
  if (id) {
    try { display(await request(`/jobs/${id}`)); poll(); }
    catch { localStorage.removeItem('scout-job'); }
  }
}

$('login').addEventListener('submit', async event => {
  event.preventDefault(); password = $('password').value;
  try { await login(); $('password').value = ''; }
  catch (error) { $('message').textContent = error.message; }
});
$('question').addEventListener('input', resizeQuestion);
window.addEventListener('resize', resizeQuestion);
$('ask').addEventListener('submit', async event => {
  event.preventDefault(); $('action').disabled = true;
  try {
    if (job && !terminal.has(job.status)) {
      stoppedPolling = true;
      display(await request(`/jobs/${job.id}`, {method: 'DELETE'}));
    } else {
      stoppedPolling = false;
      display(await request('/jobs', {method: 'POST', body: JSON.stringify({question: $('question').value})}));
      localStorage.setItem('scout-job', job.id);
      poll();
    }
  } catch (error) { $('message').textContent = error.message; }
  finally { $('action').disabled = false; }
});
$('copy').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(answer); $('copy').textContent = 'Скопировано'; }
  catch { $('copy').textContent = 'Выдели ответ и скопируй'; }
  setTimeout(() => { $('copy').textContent = 'Скопировать'; }, 2000);
});
if (password) login().catch(() => { $('message').textContent = 'Введи пароль Скаута'; });
