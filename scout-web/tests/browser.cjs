const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true});
  for (const viewport of [{width:1280,height:900},{width:390,height:844}]) {
    const page = await browser.newPage({viewport,permissions:['clipboard-read','clipboard-write']});
    let job;
    let finish = false;
    await page.route('**/scout-api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let result;
      if (path.endsWith('/auth')) result={status:'ok'};
      else if (route.request().method()==='POST') {
        job={id:'a'.repeat(32),question:JSON.parse(route.request().postData()).question,status:'running',message:'Ищу в Telegram…',started_at:Date.now()/1000,elapsed:0,answer:''}; result=job;
      } else if (route.request().method()==='DELETE') {
        job={...job,status:'stopped',message:'Поиск остановлен',elapsed:1}; result=job;
      } else {
        if (finish) job={...job,status:'completed',message:'Готово',elapsed:42,
          answer:'**Редактируемые слои** — не live text.\n\n[Dan Kieft · 14:35](https://www.youtube.com/watch?v=qwGIwxZFc2I&t=875s) · `video_hub:123`. Ключи: `video_hub:456`\n\nСохраняй референс ([Пост](https://t.me/AcidCrunch/2511) · acidcrunch:2511). Это важное пояснение.\n\nЕщё совет: **[Разбор](https://www.youtube.com/watch?v=example)**. Не потерять текст после ссылки.\n\nКлюч: `cgevent:42`.\n\n<script>window.compromised=true</script><img src=x onerror="window.compromised=true">\n\n| Приём | Ограничение |\n|---|---|\n| Слои AE | Контуры букв ([Источник](https://t.me/cgevent/42)) |'};
        result=job;
      }
      await route.fulfill({json:result,headers:{'access-control-allow-origin':'*'}});
    });
    await page.goto(process.env.SCOUT_PAGE || 'http://127.0.0.1:8767');
    await page.locator('#password').fill('test-password');
    await page.locator('#login button').click();
    await page.locator('#question').fill('Как сохранить персонажа?');
    assert.equal(await page.locator('#question').evaluate(el=>getComputedStyle(el).outlineStyle),'none');
    assert.equal(await page.locator('#ask').evaluate(el=>getComputedStyle(el).borderTopColor),'rgb(217, 160, 91)');
    await page.locator('#action').click();
    await page.waitForFunction(()=>document.querySelector('#action').textContent==='Остановить');
    assert.match(await page.locator('#message').textContent(), /Telegram/);
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#action').textContent==='Остановить');
    finish=true;
    await page.waitForFunction(()=>document.querySelector('#message').textContent==='Готово');
    assert.equal(await page.evaluate(()=>Boolean(window.compromised)),false);
    assert.equal(await page.locator('#answer img').count(),0);
    assert.equal(await page.locator('#answer a').first().getAttribute('rel'),'noopener noreferrer');
    assert.equal(await page.locator('#answer table').count(),1);
    const sources = page.locator('#answer .source-toggle');
    assert.equal(await sources.count(),5);
    assert.equal(await page.locator('#answer a:visible').count(),0);
    assert.ok(!(await page.locator('#answer').innerText()).includes('video_hub:123'));
    assert.ok((await page.locator('#answer').innerText()).includes('Это важное пояснение.'));
    assert.ok((await page.locator('#answer').innerText()).includes('Не потерять текст после ссылки.'));
    assert.ok(!(await page.locator('#answer').innerText()).includes('((источники'));
    await sources.first().click();
    assert.equal(await sources.first().getAttribute('aria-expanded'),'true');
    assert.equal(await page.locator('#answer a:visible').count(),1);
    assert.ok((await page.locator('#answer').innerText()).includes('video_hub:123'));
    assert.ok((await page.locator('#answer').innerText()).includes('video_hub:456'));
    assert.equal(await sources.nth(1).getAttribute('aria-expanded'),'false');
    await sources.first().press('Enter');
    assert.equal(await sources.first().getAttribute('aria-expanded'),'false');
    assert.equal(await page.locator('#answer a:visible').count(),0);
    await page.locator('#copy').click();
    assert.ok((await page.evaluate(()=>navigator.clipboard.readText())).includes('video_hub:123'));

    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:`output/scout_web_checks/${viewport.width}.png`,fullPage:true});
    finish=false;
    await page.locator('#question').fill('Другой вопрос');
    await page.locator('#action').click();
    await page.waitForFunction(()=>document.querySelector('#action').textContent==='Остановить');
    await page.locator('#action').click();
    await page.waitForFunction(()=>document.querySelector('#message').textContent==='Поиск остановлен');
    await page.close();
    console.log(`PASS ${viewport.width}: login, submit, progress, reload, safe Markdown, folded sources, clipboard, layout, stop`);
  }
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
