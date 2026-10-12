const fs = require('node:fs');
const esbuild = require('../node_modules/esbuild');
const vm = require('node:vm');
const compiled = esbuild.transformSync(fs.readFileSync('frontend/apps/extension/src/html-capture.ts', 'utf8'), { loader: 'ts', format: 'cjs' }).code;
const sandbox = { module: { exports: {} } }; vm.runInNewContext(compiled, sandbox);
const capture = sandbox.module.exports.capturePublicHtml.toString();
const product = fs.readFileSync('frontend/tests/fixtures/1688-offer-1027322610455.html', 'utf8')
  // Original sanitized fixture omitted href; restore the observed operator-saved supplier link.
  .replace('class="shop-company-name v-flex"', 'class="shop-company-name v-flex" href="https://shop3e1674729h322.1688.com/"')
  .replace('</body>', '<div id="description">Extra washing instructions <span hidden>PRIVATE_HIDDEN_SENTINEL</span><script>PRIVATE_SCRIPT_SENTINEL</script><button>PRIVATE_CONTROL_SENTINEL</button></div></body>');
const drawer = fs.readFileSync('frontend/tests/fixtures/1688-review-drawer.html', 'utf8');
const pages = [
  { page: 'PRODUCT', source_url: 'https://detail.1688.com/offer/1027322610455.html', html: product.replace('</body>', drawer + '</body>') },
  { page: 'SHOP', source_url: 'https://shop3e1674729h322.1688.com/', html: fs.readFileSync('frontend/tests/fixtures/1688-shop-linked.html', 'utf8') },
  { page: 'FACTORY', source_url: 'https://www.1688.com/factory/b2b-222030383828763a1d.html', html: fs.readFileSync('frontend/tests/fixtures/1688-factory-linked.html', 'utf8') },
];
const script = `
document.getElementById('run').onclick = () => {
  const frame = document.getElementById('fixture'), pages = ${JSON.stringify(pages).replace(/</g, '\\u003c')}, outputs = [];
  let index = 0;
  frame.onload = () => {
    try {
      const w = frame.contentWindow, page = pages[index];
      const result = (function(document, location, getComputedStyle, Node) { return (${capture})(page.page, page.source_url); })
        (w.document, new URL(page.source_url), w.getComputedStyle.bind(w), w.Node);
      if (!result) throw new Error('No HTML for ' + page.page);
      outputs.push(result);
      if (++index < pages.length) { frame.srcdoc = pages[index].html; return; }
      const json = JSON.stringify(outputs);
      const checks = { threeSnapshots: outputs.length === 3,
        sourceIdentity: outputs.every((x,i) => x.source_url === pages[i].source_url),
        noPrivateSentinels: !/PRIVATE_(HIDDEN|SCRIPT|CONTROL|BUYER)_SENTINEL/.test(json),
        noExecutableTags: outputs.every(x => !/<(script|iframe|input|button|form)\\b/i.test(x.html)),
        noRemoteAssets: outputs.every(x => !/<(img|video|source|style)\\b/i.test(x.html)),
        extraProductText: outputs[0].html.includes('Extra washing instructions'),
        tenReviewBodies: (outputs[0].html.match(/class="review-item"/g) || []).length === 10,
        companyModule: outputs[1].html.includes('Company introduction'),
        factoryClaims: outputs[2].html.includes('2025.07.14'),
        bounded: outputs.every(x => new TextEncoder().encode(x.html).length <= 2000000),
      };
      document.getElementById('status').textContent = Object.values(checks).every(Boolean) ? 'PASS: 10 HTML capture checks' : 'FAIL: ' + JSON.stringify(checks);
      document.getElementById('summary').textContent = outputs.map(x => x.page + ': ' + new TextEncoder().encode(x.html).length + ' HTML bytes').join(' · ');
      document.getElementById('output').textContent = JSON.stringify(outputs);
    } catch (e) { document.getElementById('status').textContent = 'ERROR: ' + e.message; }
  };
  frame.srcdoc = pages[0].html;
};`;
fs.writeFileSync('tmp/html-capture-harness.html', '<!doctype html><meta charset="utf-8"><h1>Automatic HTML capture regression</h1><button id="run">Run HTML capture</button><p id="status">Not run</p><p id="summary"></p><pre id="output" hidden></pre><iframe id="fixture" style="width:1200px;height:700px"></iframe><script>' + script + '</script>');
