'use strict';
const API = 'https://expa.beyondhorizon.dev/scout-api';
const $ = id => document.getElementById(id);
let password = sessionStorage.getItem('scout-password') || '';
let job = null;
let answer = '';
let timer = null;
let stoppedPolling = false;
const terminal = new Set(['completed', 'partial', 'error', 'stopped']);

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
  document.body.classList.add('has-result');
  const running = !terminal.has(data.status);
  $('message').textContent = data.message;
  document.querySelector('.status').classList.toggle('running', running);
  $('action').textContent = running ? 'Остановить' : 'Спросить';
  $('question').readOnly = running;
  $('question').value = data.question;
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
