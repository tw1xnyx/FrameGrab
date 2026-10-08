/* FrameGrab Ambient: shared WebGL2 background; zero per-control render loops. */
(() => {
  'use strict';
  const canvas = document.getElementById('ambient');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const state = {preset:'aurora', theme:'light', motion:!reduced.matches, visible:!document.hidden};
  const gl = canvas.getContext('webgl2', {alpha:false,antialias:false,depth:false,stencil:false,powerPreference:'low-power',preserveDrawingBuffer:false});
  if (!gl) {canvas.style.display='none';window.FrameGrabAmbient={set(o){Object.assign(state,o);},available:false};return;}
  const vs = `#version 300 es
  in vec2 aPos;out vec2 uv;void main(){uv=(aPos+1.)*.5;gl_Position=vec4(aPos,0.,1.);}`;
  const fs = `#version 300 es
  precision highp float;in vec2 uv;out vec4 frag;uniform vec2 uSize;uniform float uTime;uniform vec2 uPointer;uniform float uTheme;uniform float uPreset;
  float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
  float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),f.x),f.y);}
  float fbm(vec2 p){float s=0.,a=.5;for(int i=0;i<4;i++){s+=a*noise(p);p=p*2.03+vec2(3.2,-1.1);a*=.5;}return s;}
  vec3 pal(float n){vec3 a=vec3(.84,.88,.98),b=vec3(.93,.81,.98),c=vec3(.69,.88,.92);
   if(uPreset>.5&&uPreset<1.5){a=vec3(.96,.83,.84);b=vec3(.79,.77,.94);c=vec3(.94,.89,.78);}
   if(uPreset>1.5){a=vec3(.72,.88,.86);b=vec3(.7,.8,.96);c=vec3(.8,.93,.97);}
   if(uTheme>.5){a=vec3(.047,.062,.14);b=vec3(.12,.09,.25);c=vec3(.07,.16,.23);
    if(uPreset>.5&&uPreset<1.5){a=vec3(.14,.06,.15);b=vec3(.11,.09,.22);c=vec3(.16,.1,.15);}
    if(uPreset>1.5){a=vec3(.04,.1,.15);b=vec3(.08,.14,.25);c=vec3(.06,.14,.17);}}
   return mix(mix(a,b,smoothstep(.18,.77,n)),c,smoothstep(.6,1.,n)*.53);
  }
  void main(){vec2 p=uv;p.x*=uSize.x/uSize.y;float tm=uTime*.08;vec2 x=p+vec2(sin(tm*.35),cos(tm*.4))*.06;
    float d=fbm(x*1.4+vec2(tm*.14,-tm*.09));
    float w=fbm((x+vec2(d,-d)) *1.3+vec2(-tm*.11,tm*.08));
    float f=.5+.28*sin((x.x+x.y*.55)*3.7 + w*3.2-tm*.8)+.22*d;
    vec3 color=pal(clamp(f,0.,1.));
    vec2 spot=uv-(uPointer*.09+vec2(.49,.55));float light=exp(-dot(spot,spot)*5.5);
    color+=light*vec3(.055,.06,.08)*(uTheme>.5?.7:1.);
    color=mix(color,vec3(1.),(1.-uTheme)*.05);
    frag=vec4(color,1.);
  }`;
  function shader(kind,source){const s=gl.createShader(kind);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
  let program;
  try {program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vs));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fs));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Shader link failed');}
  catch(err){console.warn('Ambient shader fallback',err);canvas.style.display='none';window.FrameGrabAmbient={set(o){Object.assign(state,o);},available:false};return;}
  const vao=gl.createVertexArray();gl.bindVertexArray(vao);const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);gl.useProgram(program);const pos=gl.getAttribLocation(program,'aPos');gl.enableVertexAttribArray(pos);gl.vertexAttribPointer(pos,2,gl.FLOAT,false,0,0);
  const loc={size:gl.getUniformLocation(program,'uSize'),time:gl.getUniformLocation(program,'uTime'),pointer:gl.getUniformLocation(program,'uPointer'),theme:gl.getUniformLocation(program,'uTheme'),preset:gl.getUniformLocation(program,'uPreset')};
  let width=0,height=0,raf=0,last=0,elapsed=0,pointer=[0,0],target=[0,0];
  function resize(){const dpr=Math.min(window.devicePixelRatio||1,window.innerWidth<800?1:1.25);const w=Math.max(1,Math.floor(innerWidth*dpr)),h=Math.max(1,Math.floor(innerHeight*dpr));if(width!==w||height!==h){width=w;height=h;canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}}
  function render(ts){raf=0;if(!state.visible||(!state.motion&&last))return;const interval=innerWidth<800?45:30;if(ts-last<interval){raf=requestAnimationFrame(render);return;}const dt=Math.min(ts-last,55);if(last&&state.motion)elapsed+=dt;last=ts;resize();pointer[0]+=(target[0]-pointer[0])*.08;pointer[1]+=(target[1]-pointer[1])*.08;gl.useProgram(program);gl.uniform2f(loc.size,width,height);gl.uniform1f(loc.time,elapsed/1000);gl.uniform2f(loc.pointer,...pointer);gl.uniform1f(loc.theme,state.theme==='dark'?1:0);gl.uniform1f(loc.preset,{aurora:0,silk:1,lagoon:2}[state.preset]??0);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);if(state.motion)raf=requestAnimationFrame(render);}
  function schedule(){if(!raf&&state.visible){last=0;raf=requestAnimationFrame(render);}}
  window.FrameGrabAmbient={available:true,set(o){Object.assign(state,o);schedule();}};
  document.addEventListener('visibilitychange',()=>{state.visible=!document.hidden;if(state.visible)schedule();else if(raf){cancelAnimationFrame(raf);raf=0;}});
  document.addEventListener('pointermove',e=>{target=[(e.clientX/Math.max(innerWidth,1)-0.5)*2,(e.clientY/Math.max(innerHeight,1)-.5)*2];},{passive:true});
  reduced.addEventListener?.('change',e=>{if(e.matches){state.motion=false;schedule();}});
  addEventListener('resize',schedule,{passive:true});schedule();
})();
