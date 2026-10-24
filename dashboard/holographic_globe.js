const THREE_URL='https://cdn.jsdelivr.net/npm/three@0.150.1/build/three.min.js';
const instances=new WeakMap();
let loading;
function loadThree(){
  if(window.THREE)return Promise.resolve(window.THREE);
  if(!loading) loading=new Promise((resolve,reject)=>{
    const tag=document.createElement('script');tag.src=THREE_URL;
    tag.onload=()=>resolve(window.THREE);tag.onerror=()=>{loading=null;tag.remove();reject(new Error('Unable to load 3D library'));};
    document.head.appendChild(tag);
  });return loading;
}
function makeScene(T,root,data,emit){
  const host=root.querySelector('.viewport'),svg=root.querySelector('.labels'),fallback=root.querySelector('.fallback');
  const renderer=new T.WebGLRenderer({alpha:true,antialias:true});renderer.setClearAlpha(0);renderer.setPixelRatio(Math.min(devicePixelRatio,2));host.appendChild(renderer.domElement);
  const scene=new T.Scene(), camera=new T.PerspectiveCamera(40,1,.1,100);camera.position.z=3.8;
  const earth=new T.Group();scene.add(earth);
  const sphere=new T.Mesh(new T.SphereGeometry(1,64,48),new T.ShaderMaterial({
    uniforms:{base:{value:new T.Color('#5980a6')},rim:{value:new T.Color('#cfe4f5')}},transparent:true,depthWrite:false,
    vertexShader:'varying vec3 n;varying vec3 v;void main(){vec4 p=modelViewMatrix*vec4(position,1.);n=normalize(normalMatrix*normal);v=normalize(-p.xyz);gl_Position=projectionMatrix*p;}',
    fragmentShader:'uniform vec3 base;uniform vec3 rim;varying vec3 n;varying vec3 v;void main(){float f=pow(1.-abs(dot(normalize(n),normalize(v))),3.);gl_FragColor=vec4(mix(base,rim,f),.07+f*.55);}'
  }));earth.add(sphere);
  function xyz(lat,lon,r=1.006){let a=lat*Math.PI/180,b=lon*Math.PI/180;return new T.Vector3(r*Math.cos(a)*Math.sin(b),r*Math.sin(a),r*Math.cos(a)*Math.cos(b));}
  const land=[],lines=[];
  for(const ring of data.rings){for(let i=0;i<ring.length;i++){
    const p=xyz(ring[i][1],ring[i][0]);land.push(p.x,p.y,p.z);
    if(i){const q=xyz(ring[i-1][1],ring[i-1][0]);lines.push(q.x,q.y,q.z,p.x,p.y,p.z);}
  }}
  const coast=new T.LineSegments(new T.BufferGeometry().setAttribute('position',new T.Float32BufferAttribute(lines,3)),new T.LineBasicMaterial({color:'#9dc2e0',transparent:true,opacity:.42}));earth.add(coast);
  const sparks=new T.Points(new T.BufferGeometry().setAttribute('position',new T.Float32BufferAttribute(land,3)),new T.ShaderMaterial({
    uniforms:{time:{value:0},active:{value:new T.Vector3(0,0,0)},motion:{value:1}},transparent:true,depthWrite:false,blending:T.AdditiveBlending,
    vertexShader:'uniform float time;uniform float motion;uniform vec3 active;varying float glow;void main(){float hot=exp(-12.*distance(position,active));glow=.35+.25*sin(time*1.3+position.y*37.+position.x*21.)*motion+hot;vec4 p=modelViewMatrix*vec4(position,1.);gl_PointSize=(1.4+hot*3.)*3./(-p.z);gl_Position=projectionMatrix*p;}',
    fragmentShader:'varying float glow;void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;gl_FragColor=vec4(.62,.79,.94,(1.-d*2.)*glow);}'
  }));earth.add(sparks);
  // Sparse latitude lines support depth without a photographic surface.
  for(let lat=-60;lat<=60;lat+=30){const points=[];for(let lon=-180;lon<=180;lon+=3)points.push(xyz(lat,lon,.998));earth.add(new T.Line(new T.BufferGeometry().setFromPoints(points),new T.LineBasicMaterial({color:'#5980a6',transparent:true,opacity:.13})));}
  const state={renderer,scene,camera,earth,points:[],selected:null,hover:null,paused:!data.rotate,visible:true,disposed:false,emit,raf:0,drag:null,rotationTarget:null};
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  const ray=new T.Raycaster(),pointer=new T.Vector2(9,9);
  const ns='http://www.w3.org/2000/svg';
  function element(tag,attrs){const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el;}
  state.update=(next,trigger)=>{
    state.emit=trigger;
    for(const item of state.points){earth.remove(item.mesh);item.mesh.geometry.dispose();item.mesh.material.dispose();item.label.remove();}
    state.points=[];root.querySelector('.events').replaceChildren();
    for(const item of next.points){
      const mesh=new T.Mesh(new T.SphereGeometry(.022,16,12),new T.MeshBasicMaterial({color:item.color,transparent:true}));mesh.position.copy(xyz(item.lat,item.lng,1.025));earth.add(mesh);
      const label=element('g',{}),path=element('path',{fill:'none',stroke:item.color,'stroke-width':'1'}),dot=element('circle',{r:3,fill:item.color}),text=element('text',{fill:'#cfe4f5','font-size':'11','font-family':'sans-serif'});
      text.textContent=item.label;label.append(path,dot,text);svg.appendChild(label);
      const button=document.createElement('button');button.type='button';button.textContent=item.label;button.setAttribute('aria-pressed',String(item.anomaly_id===next.selected));button.onclick=()=>state.emit('selected',item.anomaly_id);root.querySelector('.events').appendChild(button);
      state.points.push({item,mesh,label,path,dot,text,heat:0});
    }
    if(state.selected!==next.selected){
      state.selected=next.selected;const active=next.points.find(p=>p.anomaly_id===next.selected);
      if(active){state.rotationTarget={x:active.lat*Math.PI/180,y:-active.lng*Math.PI/180};}
    }
  };
  state.update(data,emit);
  const motion=root.querySelector('.motion');
  function motionLabel(){motion.textContent=media.matches?'Reduced motion enabled':state.paused?'Resume rotation':'Pause rotation';motion.disabled=media.matches;}
  motion.onclick=()=>{state.paused=!state.paused;motionLabel();};motionLabel();
  const mediaChange=()=>motionLabel();media.addEventListener('change',mediaChange);
  function resize(){const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.position.z=w<460?4.5:3.8;camera.updateProjectionMatrix();svg.setAttribute('viewBox',`0 0 ${w} ${h}`);}
  const observer=new ResizeObserver(resize);observer.observe(host);resize();
  const visibility=new IntersectionObserver(([e])=>{state.visible=e.isIntersecting;});visibility.observe(host);
  host.onpointerdown=e=>{state.drag={x:e.clientX,y:e.clientY,lastX:e.clientX,lastY:e.clientY,moved:0};state.rotationTarget=null;host.setPointerCapture(e.pointerId);};
  host.onpointermove=e=>{
    const r=host.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);
    if(state.drag){const d=state.drag;d.moved=Math.max(d.moved,Math.hypot(e.clientX-d.x,e.clientY-d.y));earth.rotation.y+=(e.clientX-d.lastX)*.006;earth.rotation.x=Math.max(-1.4,Math.min(1.4,earth.rotation.x+(e.clientY-d.lastY)*.006));d.lastX=e.clientX;d.lastY=e.clientY;}
  };
  function hovered(){ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects(state.points.map(p=>p.mesh))[0];if(!hit)return null;const p=state.points.find(p=>p.mesh===hit.object);const pos=p.mesh.getWorldPosition(new T.Vector3());return pos.dot(camera.position.clone().sub(pos))>0?p:null;}
  host.onpointerup=e=>{const d=state.drag;state.drag=null;if(d&&d.moved<5){const r=host.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);const hit=hovered();if(hit)state.emit('selected',hit.item.anomaly_id);}};
  host.onpointercancel=()=>{state.drag=null;};host.onpointerleave=()=>pointer.set(9,9);
  const contextLost=e=>{e.preventDefault();fallback.textContent='3D view unavailable. Select an event using the buttons below.';fallback.style.display='grid';};renderer.domElement.addEventListener('webglcontextlost',contextLost);
  let last=performance.now(),elapsed=0;
  function frame(now){
    if(state.disposed)return;state.raf=requestAnimationFrame(frame);const dt=Math.min((now-last)/1000,.05);last=now;
    if(!state.visible)return;
    if(!media.matches)elapsed+=dt;
    if(state.rotationTarget){const t=state.rotationTarget,k=media.matches?1:Math.min(1,dt*5.5);earth.rotation.x+=(t.x-earth.rotation.x)*k;const dy=Math.atan2(Math.sin(t.y-earth.rotation.y),Math.cos(t.y-earth.rotation.y));earth.rotation.y+=dy*k;if(Math.abs(dy)<.002&&Math.abs(t.x-earth.rotation.x)<.002)state.rotationTarget=null;}
    else if(!state.drag&&!state.paused&&!media.matches)earth.rotation.y+=dt*.08;
    earth.position.y=media.matches?0:Math.sin(elapsed*.55)*.018;
    earth.updateMatrixWorld(true);state.hover=hovered();host.style.cursor=state.drag?'grabbing':state.hover?'pointer':'grab';
    sparks.material.uniforms.time.value=elapsed;sparks.material.uniforms.motion.value=media.matches?0:1;
    const active=state.hover||state.points.find(p=>p.item.anomaly_id===state.selected);
    sparks.material.uniforms.active.value.copy(active?active.mesh.position:new T.Vector3(0,0,0));
    const w=host.clientWidth,h=host.clientHeight;
    for(const p of state.points){
      const hot=p===active?1:0;p.heat+=(hot-p.heat)*Math.min(1,dt*5.5);p.mesh.scale.setScalar(1+p.heat*.8);p.mesh.material.opacity=active?.item.anomaly_id===p.item.anomaly_id?1:.55;
      const world=p.mesh.getWorldPosition(new T.Vector3()),front=world.dot(camera.position.clone().sub(world))>.10;
      p.label.style.opacity=front?(active&&active!==p?.valueOf()?.valueOf()?(.3+.7*p.heat):1):0;
      const v=world.clone().project(camera),x=(v.x+1)*w/2,y=(1-v.y)*h/2,side=x>w/2?1:-1;
      const endX=Math.max(12,Math.min(w-12,x+side*68)),endY=Math.max(65,Math.min(h-55,y+(y-h/2)*.22));
      p.path.setAttribute('d',`M${x},${y} L${endX},${endY} l${side*12},0`);p.dot.setAttribute('cx',x);p.dot.setAttribute('cy',y);
      p.text.setAttribute('x',endX);p.text.setAttribute('y',endY-7);p.text.setAttribute('text-anchor',side>0?'end':'start');
    }
    renderer.render(scene,camera);
  }
  fallback.style.display='none';state.raf=requestAnimationFrame(frame);
  state.dispose=()=>{state.disposed=true;cancelAnimationFrame(state.raf);observer.disconnect();visibility.disconnect();media.removeEventListener('change',mediaChange);renderer.domElement.removeEventListener('webglcontextlost',contextLost);scene.traverse(obj=>{obj.geometry?.dispose();if(obj.material)obj.material.dispose();});renderer.dispose();renderer.domElement.remove();svg.replaceChildren();host.onpointerdown=host.onpointermove=host.onpointerup=host.onpointercancel=host.onpointerleave=null;};
  return state;
}
export default function({parentElement,data,setTriggerValue}){
  let cancelled=false;
  const existing=instances.get(parentElement);
  if(existing)existing.update(data,setTriggerValue);
  else loadThree().then(T=>{
    if(cancelled||!parentElement.isConnected)return;
    try{const state=makeScene(T,parentElement,data,setTriggerValue);instances.set(parentElement,state);}
    catch(error){const f=parentElement.querySelector('.fallback');f.textContent='3D view unavailable. Use the location selector to open event history.';f.style.display='grid';}
  }).catch(()=>{if(!cancelled)parentElement.querySelector('.fallback').textContent='3D library unavailable. Use the location selector below.';});
  return ()=>{cancelled=true;instances.get(parentElement)?.dispose();instances.delete(parentElement);};
}
