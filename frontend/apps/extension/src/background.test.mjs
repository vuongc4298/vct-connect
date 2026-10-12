import assert from 'node:assert/strict';
import test from 'node:test';
import { transformSync } from 'esbuild';
import { readFileSync } from 'node:fs';
import Module from 'node:module';
import { resolve } from 'node:path';

const source = 'https://detail.1688.com/offer/1027322610455.html';
const shop = 'https://shopabcdef123.1688.com/';
const factory = 'https://www.1688.com/factory/b2b-abcdef123.html';

function setup({ permission = true, navigation = false } = {}) {
  const stored = {}, tabs = new Map([[1, { id: 1, url: source, status: 'complete' }]]);
  const created = [], removed = [], requests = [], downloads = [], cues = [], listeners = new Set();
  let updated;
  let message, nextId = 10;
  let currentOwner = "user_one";
  globalThis.chrome = {
    runtime: { id: 'test-extension', onMessage: { addListener: fn => { message = fn; } } },
    storage: { local: { get: async () => stored, set: async values => Object.assign(stored, values) } },
    permissions: { contains: async () => permission },
    downloads: { download: async options => { downloads.push(options); return downloads.length; } },
    tabs: {
      get: async id => tabs.get(id),
      create: async options => { const tab = { id: nextId++, ...options, status: 'complete' }; tabs.set(tab.id, tab); created.push(tab); return tab; },
      remove: async id => { removed.push(id); tabs.delete(id); },
      onUpdated: { addListener: fn => { updated = fn; } },
      onCreated: { addListener: fn => listeners.add(fn), removeListener: fn => listeners.delete(fn) },
    },
    scripting: { executeScript: async ({ target, func, args }) => {
      assert.ok(tabs.has(target.tabId));
      // Chrome rejects undefined args instead of coercing them to JSON null.
      if (args) assert.ok(args.every(value => value !== undefined), 'Injection arguments must be serializable');
      const mode = args?.[0];
      if (func.name === 'capturePublicHtml') return [{ result: { page: args[0], source_url: args[1], html: '<div>public fixture</div>' } }];
      if (func.name === 'showCompanyGuidance') { cues.push({tabId:target.tabId,args}); return [{ result: true }]; }
      if (func.name === 'captureSelectedDom') return [{ result: { source_url: source, offer_id: '1027322610455', fields: { product_title: 'Shirt' } } }];
      if (mode === 'PRODUCT_LINK') { assert.equal(args[1], source); return [{ result: shop }]; }
      if (mode === 'SHOP') return [{ result: { source_url: shop, credit_url: shop + 'page/creditdetail.html', ...(!navigation ? { factory_url: factory } : {}) } }];
      if (mode === 'OPEN_FACTORY') {
        const tab = { id: nextId++, openerTabId: target.tabId, url: factory, status: 'complete' };
        tabs.set(tab.id, tab); created.push(tab); for (const fn of listeners) fn(tab);
        return [{ result: 'CLICKED' }];
      }
      if (mode === 'FACTORY') return [{ result: { source_url: factory, canonical_url: factory, shop_url: shop, claims: [{ name: '成立时间', value: '2025.07.14' }] } }];
      throw new Error('Unexpected injection');
    } },
  };
  globalThis.fetch = async (url, options) => {
    assert.equal(options.headers.Authorization, 'Bearer short-lived-test-token');
    requests.push({ url, bundle: JSON.parse(options.body) }); return Response.json({});
  };
  const file = resolve('apps/extension/src/background.ts');
  const loaded = new Module(file); loaded.filename = file; loaded.paths = Module._nodeModulePaths(resolve('.'));
  const original = loaded.require.bind(loaded);
  loaded.require = name => name === '@clerk/chrome-extension/background' ? {
    createClerkClient: async () => ({ user: { id: currentOwner }, session: { getToken: async () => 'short-lived-test-token' } }),
  } : original(name);
  loaded._compile(transformSync(readFileSync(file, 'utf8'), { loader: 'ts', format: 'cjs', define: {
    VCT_WEB_ORIGIN: JSON.stringify('https://vct.example'), VCT_CLERK_PUBLISHABLE_KEY: JSON.stringify('test'), VCT_CLERK_SYNC_HOST: JSON.stringify('vct.example'),
  } }).code, file);
  return { stored, requests, created, removed, downloads, cues, listeners, tabs,
    update: tabId => updated(tabId, { status: "complete" }),
    owner: value => { currentOwner = value; },
    send: (type = 'START_COLLECTION', tabId = 1, sender = { id: 'test-extension', url: 'chrome-extension://test-extension/popup.html' }, ownerId = 'user_one') => new Promise(resolve => {
      const pending = message({ type, tabId, ownerId, sourceUrl: source }, sender, resolve);
      if (!pending) resolve(null);
    }) };

}

test('late supplier navigation still pauses for shop HTML instead of opening a report', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup();
    const execute = chrome.scripting.executeScript;
    let reads = 0;
    chrome.scripting.executeScript = async options => {
      if (options.args?.[0] === 'PRODUCT_LINK' && ++reads < 3) return [{ result: null }];
      return execute(options);
    };
    assert.ok((await h.send()).id);
    assert.equal(reads, 3);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_COMPANY');
    assert.equal(h.created.length, 0);
    assert.equal(h.requests.length, 1);
    assert.ok(h.cues.some(cue => cue.args[0] === 'SHOP'));
  } finally { globalThis.fetch = original; }
});

test('missing shop link shows actionable error without submitting or opening a product-only report', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup();
    const execute = chrome.scripting.executeScript;
    chrome.scripting.executeScript = async options => options.args?.[0] === 'PRODUCT_LINK'
      ? [{ result: null }] : execute(options);
    const reply = await h.send();
    assert.match(reply.error, /supplier shop link.*No analysis was submitted/);
    assert.equal(h.requests.length, 0);
    assert.equal(h.created.length, 0);
    assert.equal(h.downloads.length, 0);
    assert.equal(h.stored.guidedCollection, undefined);
  } finally { globalThis.fetch = original; }
});

test('guided product capture pauses, survives popup closure and finishes company under the same reservation', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup();
    const first = await h.send(); assert.ok(first.id);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_COMPANY');
    assert.equal(h.requests.length, 1); assert.ok(h.requests[0].bundle.guided);
    assert.equal(h.created.length, 0); // No automatic supplier navigation.
    assert.equal(h.downloads.length, 1);
    assert.ok((await h.send()).error); assert.equal(h.requests.length, 1);
    h.tabs.set(2, { id: 2, url: shop, status: 'complete' });
    const second = await h.send('CONTINUE_GUIDED', 2);
    assert.equal(second.id, first.id); assert.equal(h.stored.collectionJob.stage, 'WAITING_FACTORY');
    assert.equal(h.requests.length, 1); assert.equal(h.downloads.length, 2);
    h.tabs.set(3, { id: 3, url: factory, status: 'complete' });
    assert.equal((await h.send('CONTINUE_GUIDED', 3)).id, first.id);
    assert.equal(h.stored.collectionJob.stage, 'ASSESSING');
    assert.equal(h.requests.length, 2);
    assert.equal(h.requests[1].bundle.job_id, first.id);
    assert.deepEqual(h.requests[1].bundle.html_sources.map(x => x.page), ['PRODUCT', 'SHOP', 'FACTORY']);
    assert.deepEqual(h.requests[1].bundle.outcomes.map(x => x.status), ['OK', 'OK']);
    assert.equal(h.downloads.length, 3); assert.equal(h.removed.length, 0);
    assert.equal(h.created.length, 1); assert.ok(h.created[0].url.includes(first.id));
    assert.ok(!JSON.stringify(h.stored).includes('short-lived-test-token'));
  } finally { globalThis.fetch = original; }
});

test('named shop follows product, shop and factory capture under one reservation', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup();
    const named = 'https://hztxsy.1688.com/';
    const execute = chrome.scripting.executeScript;
    chrome.scripting.executeScript = async options => JSON.parse(JSON.stringify(await execute(options)).replaceAll(shop, named));
    const first = await h.send();
    assert.ok(first.id);
    assert.equal(h.stored.collectionJob.companyUrl, named);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_COMPANY');
    h.tabs.set(2, { id: 2, url: named + '?offerId=778418840629', status: 'complete' });
    assert.equal((await h.send('CONTINUE_GUIDED', 2)).id, first.id);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_FACTORY');
    h.tabs.set(3, { id: 3, url: factory, status: 'complete' });
    assert.equal((await h.send('CONTINUE_GUIDED', 3)).id, first.id);
    assert.equal(h.requests.length, 2);
    assert.equal(h.requests[1].bundle.shop_url, named);
    assert.deepEqual(h.requests[1].bundle.html_sources.map(item => item.page), ['PRODUCT', 'SHOP', 'FACTORY']);
  } finally { globalThis.fetch = original; }
});

test('wrong supplier and login challenge remain retryable without another quota reservation', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup(); await h.send();
    h.tabs.set(2, { id: 2, url: 'https://login.1688.com/', status: 'complete' });
    assert.ok((await h.send('CONTINUE_GUIDED', 2)).error);
    h.tabs.get(2).url = 'https://shopdifferent123.1688.com/';
    assert.ok((await h.send('CONTINUE_GUIDED', 2)).error);
    h.tabs.get(2).url = shop;
    const execute = chrome.scripting.executeScript;
    chrome.scripting.executeScript = async options => options.args?.[0] === 'SHOP' ? [{ result: null }] : execute(options);
    assert.match((await h.send('CONTINUE_GUIDED', 2)).error, /No supported supplier header/);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_COMPANY'); assert.equal(h.requests.length, 1);
    chrome.scripting.executeScript = execute;
    assert.ok((await h.send('CONTINUE_GUIDED', 2)).id);
    assert.equal(h.requests.length, 1);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_FACTORY');
  } finally { globalThis.fetch = original; }
});

test('guided capture rejects foreign callers and account switching; product-only finish remains available', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup({ permission: false });
    assert.equal(await h.send('START_COLLECTION', 1, { id: 'foreign', url: 'https://evil.example/popup.html' }), null);
    await h.send(); h.owner('user_two');
    assert.ok((await h.send('FINISH_GUIDED')).error);
    assert.ok((await h.send('CONTINUE_GUIDED', 1, undefined, 'user_two')).error);
    assert.equal(h.requests.length, 1);
    h.owner('user_one');
    assert.ok((await h.send('FINISH_GUIDED')).id);
    assert.equal(h.requests.length, 2); assert.equal(h.requests[1].bundle.outcomes[0].status, 'UNAVAILABLE');
  } finally { globalThis.fetch = original; }
});

test('lost committed begin responses retry the identical durable reservation without a new ID', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup();
    const ids = [];
    globalThis.fetch = async (url, options) => {
      if (String(url).endsWith('/begin')) { ids.push(JSON.parse(options.body).job_id); if (ids.length <= 2) throw new TypeError('response lost'); return Response.json({ id: ids[0] }); }
      return Response.json({ id: ids[0], status: 'PROCESSING' });
    };
    const failed = await h.send(); assert.ok(failed.error);
    assert.equal(ids.length, 2); assert.equal(ids[0], ids[1]);
    assert.equal(h.stored.collectionJob.reservationUncertain, true);
    const recovered = await h.send(); assert.equal(recovered.id, ids[0]);
    assert.equal(ids.length, 3); assert.equal(ids[2], ids[0]);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_COMPANY');
  } finally { globalThis.fetch = original; }
});

test('navigation between product and supplier-link capture cannot reserve mismatched evidence', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup();
    const execute = globalThis.chrome.scripting.executeScript;
    globalThis.chrome.scripting.executeScript = async options => {
      if (options.args?.[0] === 'PRODUCT_LINK') h.tabs.get(1).url = 'https://detail.1688.com/offer/999999999.html';
      return execute(options);
    };
    assert.ok((await h.send()).error);
    assert.equal(h.requests.length, 0);
  } finally { globalThis.fetch = original; }
});

test('second Analyze can capture a user-opened factory with a matching company backlink', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup(); const first = await h.send();
    h.tabs.set(2, { id: 2, url: factory, status: 'complete' });
    const execute = chrome.scripting.executeScript;
    chrome.scripting.executeScript = async options => {
      const result = await execute(options);
      if (options.args?.[0] === 'FACTORY' && options.func.name === 'captureLinkedDom') result[0].result.shop_url = 'https://shopwrong123.1688.com/';
      return result;
    };
    assert.ok((await h.send('CONTINUE_GUIDED', 2)).error);
    assert.equal(h.requests.length, 1);
    chrome.scripting.executeScript = execute;
    assert.equal((await h.send('CONTINUE_GUIDED', 2)).id, first.id);
    assert.equal(h.requests[1].bundle.factory.shop_url, shop);
    assert.deepEqual(h.requests[1].bundle.html_sources.map(x => x.page), ['PRODUCT', 'FACTORY']);
    assert.ok(!h.requests[1].bundle.shop); // Never invent a shop capture.
  } finally { globalThis.fetch = original; }
});

test('lost finish response retries saved evidence without recapturing a changed company', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup(); await h.send();
    h.tabs.set(2, { id: 2, url: shop, status: 'complete' });
    assert.ok((await h.send('CONTINUE_GUIDED', 2)).id);
    const bodies = [];
    globalThis.fetch = async (url, options) => {
      assert.ok(String(url).endsWith('/finish'));
      bodies.push(options.body);
      if (bodies.length <= 2) throw new TypeError('response lost');
      return Response.json({});
    };
    assert.ok((await h.send('FINISH_GUIDED', 2)).error);
    assert.equal(h.stored.collectionJob.stage, 'FINISHING');
    chrome.scripting.executeScript = async () => { throw new Error('Do not recapture'); };
    assert.ok((await h.send('FINISH_GUIDED', 2)).id);
    assert.equal(bodies.length, 3); assert.ok(bodies.every(body => body === bodies[0]));
    assert.equal(h.stored.collectionJob.stage, 'ASSESSING');
    assert.equal(h.downloads.length, 2);
  } finally { globalThis.fetch = original; }
});

test('definitive 422 clears rejected evidence; retry makes a fresh capture instead of replaying it forever', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup();
    globalThis.fetch = async () => Response.json({ detail: 'Invalid evidence' }, { status: 422 });
    assert.match((await h.send()).error, /capture fresh evidence/);
    assert.equal(h.stored.guidedCollection, null);
    assert.equal(h.stored.collectionJob.reservationUncertain, false);
    const rejectedId = h.stored.collectionJob.id;
    globalThis.fetch = async (url, options) => {
      h.requests.push({ url, bundle: JSON.parse(options.body) }); return Response.json({});
    };
    const retried = await h.send(); assert.ok(retried.id); assert.notEqual(retried.id, rejectedId);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_COMPANY');
    assert.equal(h.requests.length, 1);
  } finally { globalThis.fetch = original; }
});

test('an old cached rejected reservation recaptures automatically after a definitive 422', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup();
    globalThis.fetch = async () => { throw new TypeError('old response lost'); };
    await h.send();
    const oldId = h.stored.collectionJob.id;
    const ids = [];
    globalThis.fetch = async (_url, options) => {
      ids.push(JSON.parse(options.body).job_id);
      return ids.length === 1 ? Response.json({}, { status: 422 }) : Response.json({});
    };
    const fresh = await h.send();
    assert.ok(fresh.id); assert.notEqual(fresh.id, oldId);
    assert.deepEqual(ids, [oldId, fresh.id]);
    assert.equal(h.stored.collectionJob.stage, 'WAITING_COMPANY');
  } finally { globalThis.fetch = original; }
});


test('shop HTML stays recoverable until explicit product-shop finish, without requiring CAPTCHA solving', async () => {
  const original = globalThis.fetch;
  try {
    const h = setup(); const first = await h.send();
    h.tabs.set(2, {id:2,url:shop,status:'complete'});
    await h.send('CONTINUE_GUIDED',2);
    assert.equal(h.stored.guidedCollection.bundle.html_sources.length,2);
    assert.equal(h.stored.collectionJob.factoryUrl,factory);
    assert.equal(h.requests.length,1);
    assert.ok(h.cues.some(c => c.args[0] === 'FACTORY'));
    await h.send('SHOW_GUIDANCE',2);
    assert.equal(h.cues.at(-1).args[0],'FACTORY');
    assert.equal((await h.send('FINISH_GUIDED',2)).id,first.id);
    assert.deepEqual(h.requests[1].bundle.html_sources.map(x=>x.page),['PRODUCT','SHOP']);
    assert.deepEqual(h.requests[1].bundle.outcomes.map(x=>x.status),['OK','UNAVAILABLE']);
  } finally {globalThis.fetch=original;}
});

test('missing visible company HTML does not claim success; download failures retain uploadable evidence', async () => {
  const original=globalThis.fetch;
  try {
    const h=setup();await h.send();h.tabs.set(2,{id:2,url:shop,status:'complete'});
    const execute=chrome.scripting.executeScript;
    chrome.scripting.executeScript=async o=>o.func.name==='capturePublicHtml' && o.args[0]==='SHOP' ? [{result:null}] : execute(o);
    assert.match((await h.send('CONTINUE_GUIDED',2)).error,/No usable shop HTML/);
    assert.equal(h.stored.collectionJob.stage,'WAITING_COMPANY');assert.equal(h.requests.length,1);
    chrome.scripting.executeScript=execute;
    chrome.downloads.download=async()=>{throw new Error('download denied');};
    await h.send('CONTINUE_GUIDED',2);
    assert.equal(h.stored.collectionJob.stage,'WAITING_FACTORY');
    assert.match(h.stored.collectionJob.error,/download did not start/);
    assert.equal(h.stored.guidedCollection.bundle.html_sources.length,2);
  } finally {globalThis.fetch=original;}
});

test('landing cues never capture, download or submit and ignore unrelated shops and expired sessions', async () => {
  const original=globalThis.fetch;
  try {
    const h=setup();await h.send();h.tabs.set(2,{id:2,url:shop,status:'complete'});
    await h.send('SHOW_GUIDANCE',2);
    assert.equal(h.cues.at(-1).args[0],'SHOP_CAPTURE');
    assert.equal(h.requests.length,1);assert.equal(h.downloads.length,1);
    const count=h.cues.length;h.tabs.get(2).url='https://shopwrong123.1688.com/';
    await h.send('SHOW_GUIDANCE',2);assert.equal(h.cues.length,count);
    h.tabs.get(2).url=shop;h.stored.guidedCollection.job.expiresAt=Date.now()-1;
    await h.send('SHOW_GUIDANCE',2);assert.equal(h.cues.length,count);
  } finally {globalThis.fetch=original;}
});


test('visible header-only shop can be saved without a company-introduction credit link', async () => {
  const original=globalThis.fetch;
  try {
    const h=setup();await h.send();h.tabs.set(2,{id:2,url:shop,status:'complete'});
    const execute=chrome.scripting.executeScript;
    chrome.scripting.executeScript=async o=>o.func.name==='captureLinkedDom' && o.args?.[0]==='SHOP'
      ? [{result:{source_url:shop,company_name:'Visible supplier header'}}] : execute(o);
    assert.ok((await h.send('CONTINUE_GUIDED',2)).id);
    assert.equal(h.stored.collectionJob.stage,'WAITING_FACTORY');
    assert.equal(h.stored.guidedCollection.bundle.shop.credit_url,undefined);
    assert.equal(h.stored.guidedCollection.bundle.html_sources.length,2);
    await h.send('FINISH_GUIDED',2);
    assert.equal(h.requests[1].bundle.shop.company_name,'Visible supplier header');
  } finally {globalThis.fetch=original;}
});
