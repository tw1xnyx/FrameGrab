'use strict';
(() => {
 const keys=['background','sidebar','surface','text','mutedText','border','primary','secondary','tertiary','accent4','accent5','success','warning','error'];
 // Exact user-supplied values, in the key order above. Never mutate these palettes.
 const rows=[
 ['prismatic','Prismatic Studio',false,24,
 ['#F7F8FC','#EDF0F8','#FFFFFF','#18213B','#68748C','#E0E5F0','#465EF5','#9C5CFF','#08BFA9','#F46C94','#F4AB46','#0A9879','#B87613','#DE4767'],
 ['#0C1020','#121A2E','#1C2539','#F2F5FF','#9EAAC2','#2D3850','#7991FF','#BE92FF','#42DBC6','#FF8BAB','#FFCB70','#41D9AC','#F5BE5C','#FF708B']],
 ['neon','Neon Graphite',true,20,
 ['#F5F6F8','#E9ECF1','#FFFFFF','#191B25','#68707D','#DDE1E8','#5548E8','#0B929B','#D94F92','#977423','#3885CF','#138A68','#A46D0B','#CE4661'],
 ['#0B0C11','#14171D','#1E222C','#F6F7FA','#A5ACBB','#343944','#B6FF5C','#A384FF','#FF779C','#4BD9E8','#FFB869','#50D6A3','#F7C25E','#FC758A']],
 ['aurora','Aurora Mesh',true,24,
 ['#F3F8FB','#E8F0F6','#FFFFFF','#14243B','#60778F','#D8E6ED','#136CD6','#1B9D9B','#8951DC','#D54F99','#C78A20','#14966D','#A96F12','#D94B66'],
 ['#071623','#102334','#193044','#EEF9FF','#A3BDD0','#2B4657','#50CFFF','#68E4C5','#B69BFF','#FF8DBF','#FFD477','#53DDB0','#FFCB6F','#FF7D90']],
 ['rose','Rose Quartz OS',false,28,
 ['#FCF7F6','#F4ECEF','#FFFFFF','#35232D','#86737D','#ECDFE5','#AD477F','#7263CE','#C16A44','#438C84','#BF902B','#248D72','#AE7219','#CA4962'],
 ['#181116','#271B25','#322330','#FFF3F5','#C1A9B7','#493542','#F18BB8','#B5A0FF','#FFAD8B','#76D6C3','#F4CE81','#6CD5A8','#F3BF60','#FF8497']],
 ['tangerine','Neo Tangerine',false,18,
 ['#FCFAF6','#F3F0E8','#FFFFFF','#27242D','#7C7581','#EAE3DD','#DA6731','#7157DC','#148E9E','#D65185','#6D8C32','#188869','#B17D15','#CE4660'],
 ['#14131A','#211F2A','#2D2936','#FFF7F1','#BBB2C3','#403A4A','#FF995B','#AA91FF','#56D8E3','#FF81B1','#C7E879','#53D6A8','#F5C46B','#FF788B']],
 ['matcha','Matcha & Cobalt',false,26,
 ['#F8F9F3','#EAF0E7','#FFFFFF','#222D27','#728077','#DCE6DB','#3062D5','#298C77','#9A65C5','#CA7752','#B18831','#198C67','#AA7611','#CE4A5C'],
 ['#0E1815','#17251F','#203029','#F4F9F1','#A8BDB0','#34493F','#81A5FF','#75DEC0','#CA9CF5','#FFB08C','#E5CB79','#67D8AA','#F6C56C','#FF8293']],
 ['titanium','Holographic Titanium',true,22,
 ['#F6F8FA','#E9EDF2','#FFFFFF','#192433','#697A90','#DAE2E9','#365FEB','#0B9BAE','#9655D7','#E26991','#BE8A2E','#118B74','#AA7416','#D44762'],
 ['#0B1018','#151D28','#202B38','#F0F7FF','#A7B8CA','#334354','#66C9FF','#B295FF','#65EAD5','#FF94C5','#F5C76B','#4DDAAD','#F2C269','#FF7B91']]
 ];
 const object=a=>Object.freeze(Object.fromEntries(keys.map((k,i)=>[k,a[i]])));
 const definitions=rows.map(([id,name,dark,radius,light,night])=>{const variants=Object.freeze({light:object(light),dark:object(night)}),p=variants[dark?'dark':'light'];return Object.freeze({id,name,dark,radius,variants,accent:p.primary,hi:p.secondary,base:p.background,solid:p.surface});});
 const palettes=Object.freeze(Object.fromEntries(definitions.map(p=>[p.id,p])));
 const legacy=Object.freeze({clean:'prismatic',red:'neon',navy:'aurora',graphite:'tangerine',emerald:'matcha',purple:'titanium',sand:'rose'});
 const normalize=id=>palettes[id]?id:legacy[id]||'prismatic';
 const rgb=h=>h.slice(1).match(/../g).map(x=>parseInt(x,16));
 const hex=a=>'#'+a.map(x=>Math.round(x).toString(16).padStart(2,'0')).join('').toUpperCase();
 const mix=(a,b,t)=>hex(rgb(a).map((n,i)=>n*(1-t)+rgb(b)[i]*t));
 const luminance=h=>rgb(h).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
 const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
 function readable(raw,backgrounds,text){if(backgrounds.every(b=>contrast(raw,b)>=4.8))return raw;for(let n=1;n<=100;n++){const value=mix(raw,text,n/100);if(backgrounds.every(b=>contrast(value,b)>=4.8))return value;}return text;}
 function tokens(id,variant){const p=palettes[normalize(id)],dark=variant?variant==='dark':p.dark,v=p.variants[dark?'dark':'light'];
  const surface2=mix(v.surface,v.sidebar,.65),surface3=mix(v.surface,v.border,.65),backgrounds=[v.background,v.sidebar,v.surface,surface2,surface3];
  const sub=readable(v.mutedText,backgrounds,v.text),accent=readable(v.primary,backgrounds,v.text);
  let buttonInk=[v.text,v.background,v.surface].sort((a,b)=>contrast(b,v.primary)-contrast(a,v.primary))[0];if(contrast(buttonInk,v.primary)<4.8)buttonInk=readable(buttonInk,[v.primary],'#000000');
  const heroInk=[v.text,v.background,v.surface].sort((a,b)=>Math.min(contrast(b,v.primary),contrast(b,v.secondary))-Math.min(contrast(a,v.primary),contrast(a,v.secondary)))[0];
  return {background:v.background,sidebar:v.sidebar,surface:v.surface,text:v.text,'muted-text':v.mutedText,border:v.border,primary:v.primary,secondary:v.secondary,tertiary:v.tertiary,accent4:v.accent4,accent5:v.accent5,success:v.success,warning:v.warning,error:v.error,
   base:v.background,solid:v.surface,surface2,surface3,input:surface2,rail:v.sidebar,ink:v.text,sub,muted:sub,accent,'accent-hi':accent,violet:v.secondary,action:v.primary,'action-hi':v.primary,'button-ink':buttonInk,'on-accent':buttonInk,'hero-ink':heroInk,
   'success-ink':readable(v.success,backgrounds,v.text),'fail-ink':readable(v.error,backgrounds,v.text),'warning-ink':readable(v.warning,backgrounds,v.text),fail:v.error,
   mist:surface2,rim:v.border,line:v.border,line2:v.border,'card-radius':p.radius+'px','control-radius':Math.max(11,p.radius-10)+'px',shade:dark?'#00000040':'#25375515',rshadow:dark?'0 16px 40px #00000035':'0 16px 40px #25375512',mdshadow:dark?'0 5px 18px #00000025':'0 5px 18px #2537550c',
   'media-surface':dark?v.background:v.text,'media-ink':dark?v.text:v.surface,'switch-knob':dark?v.text:v.surface,'disabled-ink':sub,'disabled-surface':surface3,overlay:dark?'#03070FC2':'#172A466E','hero-a':v.primary,'hero-b':v.secondary};
 }
 function apply(id,variant){const root=document.documentElement,p=palettes[normalize(id)],dark=variant?variant==='dark':p.dark,t=tokens(p.id,dark?'dark':'light');root.dataset.palette=p.id;root.dataset.theme=dark?'dark':'light';for(const [k,v] of Object.entries(t))root.style.setProperty('--'+k,v);root.style.colorScheme=dark?'dark':'light';window.FrameGrabAmbient?.set({colors:[t.background,t.primary,t.tertiary]});return t;}
 const api={definitions,palettes,legacy,normalize,tokens,apply,contrast};if(typeof window!=='undefined')window.FrameGrabThemes=api;if(typeof module!=='undefined')module.exports=api;
})();
