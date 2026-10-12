const fs=require('node:fs'),esbuild=require('../node_modules/esbuild'),vm=require('node:vm');
function exported(path,name){const sandbox={module:{exports:{}}};vm.runInNewContext(esbuild.transformSync(fs.readFileSync(path,'utf8'),{loader:'ts',format:'cjs'}).code,sandbox);return sandbox.module.exports[name].toString();}
const linked=exported('frontend/apps/extension/src/linked-capture.ts','captureLinkedDom');
const html=exported('frontend/apps/extension/src/html-capture.ts','capturePublicHtml');
const cue=exported('frontend/apps/extension/src/company-guidance.ts','showCompanyGuidance');
const company='https://shop3e1674729h322.1688.com/',factory='https://www.1688.com/factory/b2b-222030383828763a1d.html';
const pages=['shop','factory'].map(kind=>fs.readFileSync(`frontend/tests/fixtures/1688-${kind}-linked.html`,'utf8'));
const script=`
let index=0,headerOnly=false; const outputs=[];const frame=document.getElementById('fixture');
const pages=${JSON.stringify(pages).replace(/</g,'\\u003c')};
function guidance(mode){const w=frame.contentWindow;return (function(document){return (${cue})(mode,${JSON.stringify(company)});})(w.document);}
function load(){frame.onload=()=>{if(headerOnly&&!index)frame.contentWindow.document.getElementById('bd_2_container_0')?.remove();guidance(index?'FACTORY_CAPTURE':'SHOP_CAPTURE');const w=frame.contentWindow;const overlay=w.document.createElement('div');overlay.id='captcha-fixture';overlay.style.cssText='position:fixed;bottom:10px;right:10px;background:#fff;padding:18px;border:2px solid #c66;z-index:2147483647';overlay.textContent='Synthetic CAPTCHA overlay (no challenge solution needed) ';const x=w.document.createElement('button');x.textContent='X';x.onclick=()=>overlay.remove();overlay.append(x);w.document.body.append(overlay);document.getElementById('capture').textContent=index?'Save factory HTML & analyze':'Save shop HTML';};frame.srcdoc=pages[index];}
document.getElementById('capture').onclick=()=>{try{
const w=frame.contentWindow,source=index?${JSON.stringify(factory)}:${JSON.stringify(company)};
const selected=(function(document,location,getComputedStyle,NodeFilter){return (${linked})(index?'FACTORY':'SHOP');})(w.document,new URL(source),w.getComputedStyle.bind(w),w.NodeFilter);
const snapshot=(function(document,location,getComputedStyle,Node){return (${html})(index?'FACTORY':'SHOP',source);})(w.document,new URL(source),w.getComputedStyle.bind(w),w.Node);
if(!selected||!snapshot)throw new Error('No usable evidence');outputs[index]={selected,snapshot};
document.getElementById('output').value=JSON.stringify(outputs);
document.getElementById('status').textContent=index?'PASS: shop and factory HTML captured after closing overlays; canonical identity retained':'PASS: shop HTML captured; follow the highlighted factory link';
if(!index)guidance('FACTORY');
}catch(e){document.getElementById('status').textContent='FAIL: '+e.message;}};
document.getElementById('header').onclick=()=>{headerOnly=true;index=0;load();};
document.getElementById('next').onclick=()=>{index=1;load();};load();`;
fs.mkdirSync('tmp/guided-html-proof',{recursive:true});
fs.writeFileSync('tmp/guided-html-proof/index.html','<!doctype html><meta charset="utf-8"><title>Guided HTML capture fixture</title><style>body{font:16px Segoe UI;background:#f5f8f7;color:#173b32;margin:20px}button{padding:12px;margin-right:12px;border:0;border-radius:8px;background:#16765a;color:white}iframe{width:100%;height:570px;border:1px solid #cad9d1}textarea{width:100%;height:70px}</style><h1>Guided company HTML capture</h1><p>Offline saved-page fixture · no live 1688 access · close the synthetic overlay with X, then capture.</p><button id="capture">Save shop HTML</button><button id="next">Go to factory sample</button><button id="header">Header-only shop sample</button><p id="status">Ready</p><iframe id="fixture"></iframe><details><summary>Captured public fixture data</summary><label for="output">Capture output</label><textarea id="output"></textarea></details><script>'+script+'</script>');
