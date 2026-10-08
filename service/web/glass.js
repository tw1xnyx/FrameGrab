/* Progressive enhancement: edge-biased SVG displacement of the *live* backdrop in Chromium.
   Unsupported engines use profile-aware blur/saturation, never a broken filter. */
(() => {
 'use strict';
 const isChromium = /Chrome\/|Chromium\/|Edg\//.test(navigator.userAgent) && !/Firefox\/|OPR\//.test(navigator.userAgent);
 const supported = isChromium && CSS.supports('backdrop-filter','url(#sample)');
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('aria-hidden','true');svg.setAttribute('width','0');svg.setAttribute('height','0');svg.style.cssText='position:absolute;pointer-events:none;width:0;height:0;overflow:hidden';const defs=document.createElementNS(svg.namespaceURI,'defs');svg.append(defs);document.body.append(svg);
 let intensity=58,enabled=true, seq=0;const registered=new WeakMap(),elements=new Set(),cache=new Map();let scheduleId=0;
 const mx=(a,b,t)=>a+(b-a)*t;
 function smooth(t){return t*t*(3-2*t);}
 function mapFor(w,h){const cw=Math.max(24,Math.min(320,Math.round(w*.45))),ch=Math.max(20,Math.min(175,Math.round(h*.45)));const key=`${cw}:${ch}`;if(cache.has(key))return cache.get(key);const c=document.createElement('canvas');c.width=cw;c.height=ch;const ctx=c.getContext('2d',{willReadFrequently:true});const im=ctx.createImageData(cw,ch);
  for(let y=0;y<ch;y++)for(let x=0;x<cw;x++){
   const nx=(x+.5)/cw,ny=(y+.5)/ch;const ex=Math.min(nx,1-nx),ey=Math.min(ny,1-ny);const band=.28;
   const fx=1-smooth(Math.min(1,ex/band)),fy=1-smooth(Math.min(1,ey/band));
   const corner=Math.min(1,Math.sqrt((ex/.14)**2+(ey/.14)**2));const taper=.65+.35*smooth(corner);
   const dx=(nx<.5?-1:1)*fx*taper,dy=(ny<.5?-1:1)*fy*taper;
   const p=(y*cw+x)*4;im.data[p]=Math.round(128+116*dx);im.data[p+1]=Math.round(128+116*dy);im.data[p+2]=Math.round(170+85*Math.max(fx,fy));im.data[p+3]=255;
  }ctx.putImageData(im,0,0);const url=c.toDataURL('image/png');cache.set(key,url);if(cache.size>25)cache.delete(cache.keys().next().value);return url;}
 function makeNS(tag){return document.createElementNS(svg.namespaceURI,tag);}
 function update(el){if(!supported||!enabled||!el.isConnected)return;const box=el.getBoundingClientRect();if(box.width<30||box.height<25)return;const prev=registered.get(el);const w=Math.round(box.width),h=Math.round(box.height);if(prev&&prev.w===w&&prev.h===h&&prev.intensity===intensity)return;
  const id=prev?.id||`fg-lens-${++seq}`;if(prev?.node)prev.node.remove();const filter=makeNS('filter');filter.id=id;filter.setAttribute('x','0');filter.setAttribute('y','0');filter.setAttribute('width','100%');filter.setAttribute('height','100%');filter.setAttribute('filterUnits','objectBoundingBox');filter.setAttribute('color-interpolation-filters','sRGB');
  const image=makeNS('feImage');image.setAttribute('href',mapFor(w,h));image.setAttribute('result','lensmap');image.setAttribute('width','100%');image.setAttribute('height','100%');image.setAttribute('preserveAspectRatio','none');filter.append(image);
  const blur=makeNS('feGaussianBlur');blur.setAttribute('in','SourceGraphic');blur.setAttribute('stdDeviation',intensity>60?'1.15':'.75');blur.setAttribute('result','base');filter.append(blur);
  const warp=makeNS('feDisplacementMap');warp.setAttribute('in','base');warp.setAttribute('in2','lensmap');warp.setAttribute('scale',String(Math.round(intensity*.28)));warp.setAttribute('xChannelSelector','R');warp.setAttribute('yChannelSelector','G');filter.append(warp);defs.append(filter);
  registered.set(el,{id,node:filter,w,h,intensity});el.style.setProperty('--optical-filter',`url("#${id}") blur(.65px) saturate(110%)`);el.classList.add('optical-active');
 }
 function refresh(){scheduleId=0;for(const el of elements)if(el.isConnected)update(el);}
 function schedule(){if(!scheduleId)scheduleId=requestAnimationFrame(refresh);}
 const ro=new ResizeObserver(schedule);
 function scan(root=document){root.querySelectorAll('[data-optical]').forEach(el=>{if(elements.has(el))return;elements.add(el);ro.observe(el);el.addEventListener('pointermove',e=>{const b=el.getBoundingClientRect();el.style.setProperty('--mx',`${(e.clientX-b.left)/b.width*100}%`);el.style.setProperty('--my',`${(e.clientY-b.top)/b.height*100}%`);},{passive:true});el.addEventListener('pointerleave',()=>{el.style.setProperty('--mx','50%');el.style.setProperty('--my','0%');});});schedule();}
 function toggle(on){enabled=!!on;for(const el of elements){el.classList.toggle('optics-off',!enabled);el.classList.toggle('optical-active',enabled&&supported);if(!enabled)el.style.removeProperty('--optical-filter');}if(enabled){for(const el of elements){const entry=registered.get(el);if(entry)entry.intensity=-1;}schedule();}}
 window.FrameGrabGlass={supported,scan,toggle,setIntensity(v){intensity=Number(v)||0;document.documentElement.style.setProperty('--glass-blur',`${Math.round(8+intensity*.17)}px`);for(const el of elements){const entry=registered.get(el);if(entry)entry.intensity=-1;}schedule();},quality:supported?'Chromium SVG live refraction':'CSS adaptive frost'};
 scan();
})();
