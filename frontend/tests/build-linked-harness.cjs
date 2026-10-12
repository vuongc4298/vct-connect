// Selected, sanitized regions from operator-saved pages; no remote fetch or source scripts.
const fs = require('node:fs');
const esbuild = require('../node_modules/esbuild');
const vm = require('node:vm');
const compiled = esbuild.transformSync(fs.readFileSync('frontend/apps/extension/src/linked-capture.ts', 'utf8'), { loader: 'ts', format: 'cjs' }).code;
const sandbox = { module: { exports: {} } }; vm.runInNewContext(compiled, sandbox);
const capture = sandbox.module.exports.captureLinkedDom.toString();
const shop = fs.readFileSync('frontend/tests/fixtures/1688-shop-linked.html', 'utf8');
const factory = fs.readFileSync('frontend/tests/fixtures/1688-factory-linked.html', 'utf8');
const script = `
document.getElementById('run').onclick = () => {
  const frame = document.getElementById('fixture');
  const outputs = {};
  frame.onload = () => {
    try {
      const isShop = !outputs.shop;
      const w = frame.contentWindow;
      const result = (function(document, location, getComputedStyle, NodeFilter) {
        return (${capture})(isShop ? 'SHOP' : 'FACTORY');
      })(w.document, new URL(isShop ? 'https://shop3e1674729h322.1688.com/' : 'https://www.1688.com/factory/b2b-222030383828763a1d.html'), w.getComputedStyle.bind(w), w.NodeFilter);
      if (isShop) { outputs.shop = result; frame.srcdoc = ${JSON.stringify(factory)}; return; }
      outputs.factory = result;
      const checks = { ownShop: outputs.shop?.source_url === 'https://shop3e1674729h322.1688.com/',
        ownCredit: outputs.shop?.credit_url === 'https://shop3e1674729h322.1688.com/page/creditdetail.html',
        factoryBacklink: result?.shop_url === outputs.shop?.source_url,
        eightClaims: result?.claims?.length === 8,
        founding: result?.claims?.some(x => x.name === '成立时间' && x.value === '2025.07.14'),
        businessType: result?.description?.includes('经销批发'),
        noRecommendations: !JSON.stringify(result).includes('ISO'),
      };
      document.getElementById('status').textContent = Object.values(checks).every(Boolean) ? 'PASS: 7 linked saved-DOM checks' : 'FAIL: ' + JSON.stringify(checks);
      document.getElementById('output').textContent = JSON.stringify(outputs, null, 2);
    } catch (e) { document.getElementById('status').textContent = 'ERROR: ' + e.message; }
  };
  frame.srcdoc = ${JSON.stringify(shop)};
};`;
fs.writeFileSync('tmp/linked-capture-harness.html', '<!doctype html><meta charset="utf-8"><h1>Linked supplier capture regression</h1><button id="run">Run linked capture</button><p id="status">Not run</p><pre id="output"></pre><iframe id="fixture" style="width:1200px;height:700px"></iframe><script>' + script + '</script>');
