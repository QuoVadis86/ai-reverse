/**
 * Load bdms.js in Node.js with browser API polyfills.
 * bdms will self-initialize and we can call its init/export.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const bdmsCode = fs.readFileSync('/tmp/bdms.js', 'utf8');

const dom = new JSDOM('<!DOCTYPE html><html><head></head><body></body></html>', {
    url: 'https://www.douyin.com/jingxuan',
    referrer: 'https://www.douyin.com/',
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    pretendToBeVisual: true,
    runScripts: 'dangerously',
    resources: 'usable',
});

const w = dom.window;
const globals = ['document','navigator','location','crypto','fetch',
    'XMLHttpRequest','URL','URLSearchParams','Headers','Request','Response',
    'setTimeout','clearTimeout','setInterval','clearInterval',
    'performance','Blob','File','FileReader','FormData','MutationObserver','WebSocket'];
for (const g of globals) { globalThis[g] = w[g]; }
globalThis.window = w;

const captured = [];
const origO = w.XMLHttpRequest.prototype.open;
w.XMLHttpRequest.prototype.open = function(m, u) {
    this._u = String(u);
    return origO.call(this, m, u);
};
w.XMLHttpRequest.prototype.send = function(b) {
    const u = this._u || '';
    if (u.includes('a_bogus')) {
        captured.push({ u, t: Date.now() });
        console.log('\n>>> a_bogus <<<');
        console.log(u.substring(0, 300));
    }
    return w.XMLHttpRequest.prototype.__proto__.send.call(this, b);
};

console.log('Loading bdms.js...');
try {
    w.eval(bdmsCode);
    console.log('OK');
} catch(e) {
    console.error('Error:', e.message);
}

if (w.bdms) {
    console.log('bdms.init type:', typeof w.bdms.init);
    try { w.bdms.init(); console.log('init OK'); } catch(e) { console.error('init:', e.message); }
    
    const xhr = new w.XMLHttpRequest();
    xhr.open('GET', 'https://www.douyin.com/aweme/v2/web/module/feed/?device_platform=webapp&aid=6383&channel=channel_pc_web');
    xhr.send();
    
    console.log('Captured:', captured.length);
    if (captured.length > 0) {
        const p = new w.URLSearchParams(captured[0].u.split('?')[1] || '');
        console.log('a_bogus:', p.get('a_bogus'));
    }
} else {
    console.log('bdms not found');
    for (const k of Object.keys(w)) {
        if (k.includes('bdms') || k.includes('BDMS')) console.log('  found:', k, typeof w[k]);
    }
}
