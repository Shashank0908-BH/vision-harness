from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent.parent
URL=(ROOT/'vision-harness-study-guide.html').as_uri()
OUT=ROOT/'research'/'guide-checks'
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.goto(URL)
    page.wait_for_selector('.page:not([hidden]) h1')
    assert page.locator('.page').count()==36
    assert page.locator('.model-card').count()==50
    assert page.locator('.glossary-list article').count()==136
    assert page.locator('.page:not([hidden])').count()==1
    page.screenshot(path=str(OUT/'desktop-start.png'),full_page=False)
    page.locator('#next').click()
    assert page.locator('.page:not([hidden])').get_attribute('id')=='big-picture'
    page.locator('#prev').click()
    page.locator('#search').fill('Cellpose')
    assert page.locator('[data-result]').count()>0
    page.locator('[data-result="catalog-8"]').click()
    assert page.locator('.page:not([hidden])').get_attribute('id')=='catalog-8'
    assert page.locator('#full-route').get_attribute('aria-pressed')=='true'
    page.locator('#page-select').select_option('ml-basics')
    page.locator('#ml-basics .term').first.click()
    assert page.locator('#definition').evaluate('(e)=>e.open')
    page.keyboard.press('Escape')
    page.locator('#note-ml-basics').fill('QA: model versus library')
    page.locator('[data-done="ml-basics"]').check()
    page.reload()
    assert page.locator('#note-ml-basics').input_value()=='QA: model versus library'
    assert page.locator('[data-done="ml-basics"]').is_checked()
    with page.expect_download() as dl:
        page.locator('#export').click()
    assert dl.value.suggested_filename.endswith('.md')
    page.locator('#page-select').select_option('compute')
    page.locator('#params').fill('7')
    page.locator('#bits').select_option('16')
    assert '14 GB' in page.locator('#memory-result').inner_text()
    page.locator('#bits').select_option('4')
    assert '3.5 GB' in page.locator('#memory-result').inner_text()
    page.locator('#params').fill('-1')
    assert page.locator('#memory-result [role="alert"]').count()==1
    page.locator('#params').fill('7')
    page.locator('#page-select').select_option('evaluation')
    assert '80.0%' in page.locator('#metric-result').inner_text()
    page.locator('#tp').fill('0');page.locator('#fp').fill('0');page.locator('#fn').fill('0')
    assert 'undefined' in page.locator('#metric-result').inner_text()
    page.locator('#tp').fill('8');page.locator('#fp').fill('2');page.locator('#fn').fill('2')
    page.locator('#page-select').select_option('loop')
    page.locator('[data-step="6"]').click()
    assert 'Answer or inspect again' in page.locator('#step-panel').inner_text()
    page.locator('[data-step="0"]').click()
    page.screenshot(path=str(OUT/'desktop-loop.png'),full_page=True)
    ids=page.locator('.page').evaluate_all('(els)=>els.map(e=>e.id)')
    overflow=[]
    for width in [1440,768,390,320]:
        page.set_viewport_size({'width':width,'height':900})
        for pid in ids:
            page.evaluate('(id)=>show(id,false)',pid)
            if page.evaluate('document.documentElement.scrollWidth > innerWidth+1'):
                overflow.append({'width':width,'page':pid,'actual':page.evaluate('document.documentElement.scrollWidth')})
        if width==390:
            page.evaluate('show("loop",true)')
            page.screenshot(path=str(OUT/'mobile-loop.png'),full_page=True)
            page.locator('#menu').click()
            assert page.locator('#sidebar').is_visible()
            page.locator('#menu').click()
            page.evaluate('show("medical-data",true)')
            page.locator('#medical-data .visual').screenshot(path=str(OUT/'mobile-volume.png'))
    page.set_viewport_size({'width':1440,'height':1000})
    page.evaluate('show("big-picture",false)')
    page.locator('#theme').click()
    page.screenshot(path=str(OUT/'desktop-dark.png'),full_page=True)
    page.locator('#theme').click()
    page.emulate_media(media='print')
    assert page.locator('.page:visible').count()==36
    report={'pages':len(ids),'catalog_entries':page.locator('.model-card').count(),'glossary_terms':136,'js_errors':errors,'horizontal_overflow':overflow,'viewports_checked':[1440,768,390,320],'checks':['pagination','search across routes','glossary dialog','notes persistence','completion persistence','export download','memory calculator','metric calculator','step-through','mobile menu','theme','all-page print']}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    browser.close()
    assert not errors,errors
    assert not overflow,overflow
