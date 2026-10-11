const fs = require('node:fs');
const esbuild = require('../node_modules/esbuild');
const vm = require('node:vm');
const compiled = esbuild.transformSync(fs.readFileSync('frontend/apps/extension/src/capture.ts', 'utf8'), {loader:'ts',format:'cjs'}).code;
const sandbox = {module:{exports:{}}};
vm.runInNewContext(compiled, sandbox);
const capture = sandbox.module.exports.captureSelectedDom.toString();
const html = fs.readFileSync('frontend/tests/fixtures/1688-offer-1027322610455.html', 'utf8');
const drawer = process.argv.includes('--drawer') ? fs.readFileSync('frontend/tests/fixtures/1688-review-drawer.html', 'utf8') : '';
const script = `
document.getElementById('run').onclick = () => {
  try {
    const result = (function(location) { return (${capture})(); })(new URL('https://detail.1688.com/offer/1027322610455.html'));
    const f = result.fields;
    const checks = {
      supplier: f.supplier_name === "Dongguan chang'an haixiu garment factory",
      tenure: f.supplier_tenure?.includes('2'),
      business: f.main_business?.includes('t-shirt'),
      supplierMetrics: f.supplier_metrics?.length === 4,
      qualifiedPrices: f.price_details?.includes('0.10') && f.price_details?.includes('8.70') && f.price_details?.includes('After coupon'),
      stockAndSkuPrice: f.sku_options?.some(x => x.value.includes('8.7') && x.value.includes('790')),
      attributes: f.product_attributes?.length === 41 && f.product_attributes.some(x => x.name === 'Gram weight'),
      shipping: f.shipping_details?.some(x => x.value.includes('dongguan')),
      rating: f.rating === 4.6,
      approximateReviews: f.review_summary?.includes('40+'),
      reviewText: f.reviews?.some(x => x.text.includes('very thick')),
      consign: f.consign_metrics?.length === 9,
      size: new TextEncoder().encode(JSON.stringify(result)).length <= 16384,
      excludedHidden: !JSON.stringify(result).includes('PRIVATE_SENTINEL'),
      ${drawer ? `drawerCount: f.reviews?.length === 10,
      repeatedCards: f.reviews?.filter(x => x.text === 'The user thought the product was very good and gave it a five-star rating').length === 3,
      excludedBuyer: !JSON.stringify(result).includes('PRIVATE_BUYER_SENTINEL'),` : ''}
    };
    document.getElementById('status').textContent = Object.values(checks).every(Boolean) ? 'PASS: ' + Object.keys(checks).length + ' fixture checks' : 'FAIL: ' + JSON.stringify(checks);
    document.getElementById('capture-output').textContent = JSON.stringify(result, null, 2);
  } catch (error) { document.getElementById('status').textContent = 'ERROR: ' + error.message; }
};`;
const canary = '<div hidden><div id="shopNavigation"><h1 class="shop-company-name">PRIVATE_SENTINEL</h1></div><div id="productEvaluation"><div class="evaluation-content"><div class="content-text">PRIVATE_SENTINEL</div></div></div></div>';
const harness = html.replace('<body>', '<body><h1>1688 selected evidence regression</h1><button id="run">Run capture regression</button><p id="status">Not run</p><pre id="capture-output"></pre>' + canary + drawer).replace('</body>', '<script>' + script + '</script></body>');
fs.writeFileSync('tmp/1688-capture-harness.html', harness);
