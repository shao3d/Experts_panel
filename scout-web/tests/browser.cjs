const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
  for (const viewport of [{width:1280,height:900},{width:390,height:844},{width:320,height:740}]) {
    const page = await browser.newPage({viewport,permissions:['clipboard-read','clipboard-write']});
    await page.context().route(/https:\/\/(?:t\.me|www\.youtube\.com)\//, route => route.fulfill({contentType:'text/html',body:'<title>Source destination</title>'}));
    let job;
    let finish = false;
    let submissions = 0;
    await page.route('**/scout-api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let result;
      if (path.endsWith('/auth')) result={status:'ok'};
      else if (route.request().method()==='POST') {
        submissions++;
        job={id:'a'.repeat(32),question:JSON.parse(route.request().postData()).question,status:'running',message:'Ищу в Telegram…',started_at:Date.now()/1000,elapsed:0,answer:''}; result=job;
      } else if (route.request().method()==='DELETE') {
        job={...job,status:'stopped',message:'Поиск остановлен',elapsed:1}; result=job;
      } else {
        if (finish) job={...job,status:'completed',message:'Готово',elapsed:42,
          sources:{
            'video_hub:123':{url:'https://www.youtube.com/watch?v=qwGIwxZFc2I&t=875s',label:'Dan Kieft · AI workflow · 14:35'},
            'video_hub:456':{url:'https://www.youtube.com/watch?v=qwGIwxZFc2I&t=1086s',label:'Higgsfield AI · Длинное название видео с подробным объяснением · 18:06'},
            'video_hub:789':{url:'https://www.youtube.com/watch?v=qwGIwxZFc2I&t=263s',label:'Dan Kieft · AI workflow · 4:23'},
            'acidcrunch:2511':{url:'https://t.me/AcidCrunch/2511',label:'Acid Crunch · пост 2511'},
            'cgevent:42':{url:'https://t.me/cgevent/42',label:'CGEVENT · пост 42'}
          },
          answer:'**Редактируемые слои** — не live text.\n\n[Dan Kieft · 14:35](https://www.youtube.com/watch?v=qwGIwxZFc2I&t=875s) · `video_hub:123`, Higgsfield AI, 28.08.2026, 18:06. Ключи: `video_hub:456`\n\nСохраняй референс ([Пост](https://t.me/AcidCrunch/2511) · acidcrunch:2511, **Acid Crunch**, *26.06.2026*, 01:02–01:18). Это важное пояснение.\n\nЕщё совет: **[Разбор](https://www.youtube.com/watch?v=example)**. Не потерять текст после ссылки.\n\nПроверенный совет — важная деталь. — Dan Kieft, 01.09.2026, [04:23](https://www.youtube.com/watch?v=example&t=263s), `video_hub:789`.\n\nКлюч: `cgevent:42`.\n\n```\ncgevent:43\n```\n\n<script>window.compromised=true</script><img src=x onerror="window.compromised=true">\n\n| Приём | Ограничение |\n|---|---|\n| Слои AE | Контуры букв (Источник: [Источник](https://t.me/cgevent/42)) |'};
        result=job;
      }
      await route.fulfill({json:result,headers:{'access-control-allow-origin':'*'}});
    });
    await page.goto(process.env.SCOUT_PAGE || 'http://127.0.0.1:8767');
    await page.locator('#password').fill('test-password');
    await page.locator('#login button').click();
    await page.locator('#question').fill('Длинный вопрос\nсо второй строкой\nи третьей строкой\nи четвёртой строкой');
    assert.ok(await page.locator('#question').evaluate(el=>el.clientHeight>=el.scrollHeight));
    await page.locator('#question').fill('Как сохранить персонажа?');
    assert.equal(await page.locator('#question').evaluate(el=>getComputedStyle(el).outlineStyle),'none');
    assert.equal(await page.locator('#ask').evaluate(el=>getComputedStyle(el).borderTopColor),'rgb(217, 160, 91)');
    assert.equal(await page.locator('#elapsed').count(),0);
    assert.ok((await page.locator('#shortcut').innerText()).includes('Shift + Enter'));
    assert.equal(Math.round((await page.locator('#shortcut').boundingBox()).x+(await page.locator('#shortcut').boundingBox()).width), Math.round((await page.locator('#ask').boundingBox()).x+(await page.locator('#ask').boundingBox()).width));
    await page.locator('#question').press('Enter');
    assert.equal(submissions,0);
    assert.ok((await page.locator('#question').inputValue()).includes('\n'));
    const beforeSearch = await page.locator('#ask').boundingBox();
    await page.locator('#question').press('Shift+Enter');
    await page.waitForFunction(()=>document.querySelector('#action').textContent==='Остановить');
    assert.equal(submissions,1);
    await page.locator('#question').press('Shift+Enter');
    assert.equal(submissions,1);
    assert.match(await page.locator('#message').textContent(), /Telegram/);
    assert.equal((await page.locator('#ask').boundingBox()).y,beforeSearch.y);
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#action').textContent==='Остановить');
    finish=true;
    await page.waitForFunction(()=>document.querySelector('#message').textContent==='Готово');
    assert.equal(await page.evaluate(()=>Boolean(window.compromised)),false);
    assert.equal(await page.locator('#answer img').count(),0);
    assert.equal(await page.locator('#answer a').first().getAttribute('rel'),'noopener noreferrer');
    assert.equal(await page.locator('#answer table').count(),1);
    assert.equal((await page.locator('#answer pre').innerText()).trim(),'cgevent:43');
    const sources = page.locator('#answer .source-toggle');
    assert.equal(await sources.count(),6);
    assert.equal(await page.locator('#answer a:visible').count(),0);
    assert.ok(!(await page.locator('#answer').innerText()).includes('video_hub:123'));
    for (const metadata of ['Higgsfield AI', '28.08.2026', '18:06', 'Acid Crunch', '26.06.2026', '01:02', 'Dan Kieft, 01.09.2026']) assert.ok(!(await page.locator('#answer').innerText()).includes(metadata), metadata);
    assert.ok((await page.locator('#answer').innerText()).includes('Это важное пояснение.'));
    assert.ok((await page.locator('#answer').innerText()).includes('Проверенный совет — важная деталь.'));
    assert.ok((await page.locator('#answer').innerText()).includes('Не потерять текст после ссылки.'));
    assert.ok(!(await page.locator('#answer').innerText()).includes('((источники'));
    await sources.first().click();
    assert.equal(await sources.first().getAttribute('aria-expanded'),'true');
    assert.equal(await page.locator('#answer a:visible').count(),2);
    assert.equal(await page.locator('#answer a[title="video_hub:123"]').getAttribute('href'),'https://www.youtube.com/watch?v=qwGIwxZFc2I&t=875s');
    assert.ok((await page.locator('#answer').innerText()).includes('Higgsfield AI, 28.08.2026, 18:06'));
    assert.ok((await page.locator('#answer').innerText()).includes('Длинное название видео'));
    const videoPopup = await Promise.all([page.waitForEvent('popup'), page.locator('#answer a[title="video_hub:123"]').click()]);
    await videoPopup[0].waitForLoadState();
    assert.equal(videoPopup[0].url(),'https://www.youtube.com/watch?v=qwGIwxZFc2I&t=875s');
    await videoPopup[0].close();
    assert.equal(await sources.nth(1).getAttribute('aria-expanded'),'false');
    await sources.first().press('Enter');
    assert.equal(await sources.first().getAttribute('aria-expanded'),'false');
    assert.equal(await page.locator('#answer a:visible').count(),0);
    await sources.nth(1).click();
    assert.ok((await page.locator('#answer').innerText()).includes('Acid Crunch, 26.06.2026, 01:02–01:18'));
    const telegramPopup = await Promise.all([page.waitForEvent('popup'), page.locator('#answer a[title="acidcrunch:2511"]').click()]);
    await telegramPopup[0].waitForLoadState();
    assert.equal(telegramPopup[0].url(),'https://t.me/AcidCrunch/2511');
    await telegramPopup[0].close();
    await sources.nth(1).click();
    await sources.nth(3).click();
    assert.equal(await page.locator('#answer .sources').nth(3).locator('a').first().getAttribute('href'),'https://www.youtube.com/watch?v=qwGIwxZFc2I&t=263s');
    await sources.nth(3).click();
    await sources.first().click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:`output/scout_web_checks/sources-${viewport.width}.png`,fullPage:true});
    await sources.first().click();
    await page.locator('#copy').click();
    const copied = await page.evaluate(()=>navigator.clipboard.readText());
    assert.ok(copied.includes('video_hub:123'));
    assert.ok(copied.includes('Higgsfield AI, 28.08.2026, 18:06'));

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
