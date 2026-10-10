'use strict';
const path=require('node:path'),os=require('node:os');
module.exports=function(){try{return require('playwright');}catch(error){const bundled=process.env.FRAMEGRAB_PLAYWRIGHT_PATH||path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');try{return require(bundled);}catch{throw Error('UI verification needs Playwright. Install it as a test tool or set FRAMEGRAB_PLAYWRIGHT_PATH.');}}};
