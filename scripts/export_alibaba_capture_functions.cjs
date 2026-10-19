// Export the actual independently serialized extension functions for browser verification.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { transformSync } = require('../frontend/node_modules/esbuild');
const root = path.resolve(__dirname, '..');
const context = { module: { exports: {} } };
const source = fs.readFileSync(path.join(root, 'frontend/apps/extension/src/alibaba-capture.ts'), 'utf8');
vm.runInNewContext(transformSync(source, { loader: 'ts', format: 'cjs' }).code, context);
const { captureAlibabaDom, captureAlibabaHtml } = context.module.exports;
fs.writeFileSync(process.argv[2], JSON.stringify({ dom: captureAlibabaDom.toString(), html: captureAlibabaHtml.toString() }));
