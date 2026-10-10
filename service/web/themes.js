'use strict';
(() => {
 const definitions=[
  {id:'clean',name:'Clean White & Blue',dark:false,accent:'#1955c7',hi:'#2766d8',base:'#f0f4fa',solid:'#ffffff'},
  {id:'red',name:'Black & Red',dark:true,accent:'#ff7a89',hi:'#ffa6b0',base:'#100d11',solid:'#1d171d'},
  {id:'navy',name:'Midnight Navy & Cyan',dark:true,accent:'#4dd9ec',hi:'#8de8f4',base:'#091522',solid:'#122333'},
  {id:'graphite',name:'Graphite & Orange',dark:true,accent:'#ffb270',hi:'#ffd0a6',base:'#17191d',solid:'#25282e'},
  {id:'emerald',name:'Emerald Dark',dark:true,accent:'#54d9aa',hi:'#a0efd0',base:'#101b19',solid:'#1c2b27'},
  {id:'purple',name:'Royal Purple',dark:true,accent:'#c8a4ff',hi:'#e2caff',base:'#1b142b',solid:'#2b203d'},
  {id:'sand',name:'Warm Sand Light',dark:false,accent:'#963f24',hi:'#a84b2b',base:'#f4eee5',solid:'#fffaf3'}
 ];
 const palettes=Object.fromEntries(definitions.map(p=>[p.id,p]));
 function tokens(id,variant){const p=palettes[id]||palettes.clean;const dark=variant?variant==='dark':p.dark;const native=dark===p.dark;
  const accent=native?p.accent:(dark?'#8db9ff':({red:'#b3233e',navy:'#006575',graphite:'#934100',emerald:'#006c4b',purple:'#7134b5'}[id]||p.accent));
  return {'base':native?p.base:dark?'#111827':'#f3f5f8','solid':native?p.solid:dark?'#202a39':'#ffffff','ink':dark?'#f5f6fa':'#172334','sub':dark?'#c2c9d5':'#47546a','muted':dark?'#adb8c8':'#56647a','accent':accent,'accent-hi':native?p.hi:accent,'violet':accent,'success':dark?'#6ae4b3':'#006b4b','fail':dark?'#ff9aa7':'#ac2443','warning':dark?'#ffd08b':'#80520b','surface':native?p.solid:dark?'#202a39':'#ffffff','surface2':dark?'#273242':'#f3f5f8','mist':dark?'#303b4c':'#e8edf5','rim':dark?'#4a566b':'#d1d9e6','line':dark?'#3b4658':'#d3dbe7','line2':dark?'#526077':'#a9b7cc','rshadow':dark?'0 12px 30px #00000035':'0 12px 30px #15233a12','mdshadow':dark?'0 5px 15px #00000025':'0 5px 15px #15233a0d','on-accent':dark?'#10202c':'#ffffff'};
 }
 function apply(id,variant){const root=document.documentElement;const p=palettes[id]||palettes.clean;const dark=variant?variant==='dark':p.dark;root.dataset.palette=p.id;root.dataset.theme=dark?'dark':'light';const t=tokens(p.id,dark?'dark':'light');for(const [k,v] of Object.entries(t))root.style.setProperty('--'+k,v);root.style.colorScheme=dark?'dark':'light';return t;}
 window.FrameGrabThemes={definitions,palettes,tokens,apply};
})();
