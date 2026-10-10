'use strict';
const {EventEmitter}=require('node:events');
const PROVIDER=Object.freeze({provider:'github',owner:'tw1xnyx',repo:'FrameGrab-Updates',private:false,releaseType:'release'});
class ReleaseUpdater extends EventEmitter {
 constructor({engine=null}={}){super();this.engine=engine||require('electron-updater').autoUpdater;this.engine.autoDownload=false;this.engine.autoInstallOnAppQuit=false;this.engine.allowDowngrade=false;this.engine.disableDifferentialDownload=false;
  for(const name of ['checking-for-update','update-not-available','update-available','download-progress','update-downloaded','error'])this.engine.on(name,data=>this.emit(name,data));
  this.engine.setFeedURL(PROVIDER);
 }
 setFeedURL(options){this.engine.setFeedURL(options?.provider==='github'?PROVIDER:options);}
 checkForUpdates(){return this.engine.checkForUpdates();}
 downloadUpdate(){return this.engine.downloadUpdate();}
 quitAndInstall(){return this.engine.quitAndInstall(false,true);}
}
module.exports={ReleaseUpdater,PROVIDER};
