'use strict';
let nodes=[],edges=[],index=new Map(),running=false,iteration=0,timer=null;
function targetDistance(weight){return 35+145/Math.sqrt(Math.max(1,weight));}
function step(){
 const cells=new Map(),cellSize=120;
 nodes.forEach(n=>{n.fx=-n.x*.0007;n.fy=-n.y*.0007;const key=Math.floor(n.x/cellSize)+','+Math.floor(n.y/cellSize);if(!cells.has(key))cells.set(key,[]);cells.get(key).push(n);});
 nodes.forEach(n=>{const cx=Math.floor(n.x/cellSize),cy=Math.floor(n.y/cellSize);for(let x=cx-1;x<=cx+1;x++)for(let y=cy-1;y<=cy+1;y++){
  const near=cells.get(x+','+y)||[];for(const m of near){if(m===n)continue;let dx=n.x-m.x,dy=n.y-m.y;const d2=Math.max(25,dx*dx+dy*dy);if(d2>40000)continue;if(dx===0&&dy===0){dx=.5;dy=.3;}const force=250/d2;n.fx+=dx*force;n.fy+=dy*force;}
 }});
 edges.forEach(e=>{const a=index.get(e.source),b=index.get(e.target);if(!a||!b)return;let dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy));const f=(d-targetDistance(e.weight))*.012;dx=dx/d*f;dy=dy/d*f;a.fx+=dx;a.fy+=dy;b.fx-=dx;b.fy-=dy;});
 nodes.forEach(n=>{if(n.fixed){n.vx=0;n.vy=0;return;}n.vx=(n.vx+Math.max(-8,Math.min(8,n.fx)))*.75;n.vy=(n.vy+Math.max(-8,Math.min(8,n.fy)))*.75;n.x+=n.vx;n.y+=n.vy;});
}
function tick(){if(!running)return;step();iteration++;if(iteration%4===0||iteration>=400)self.postMessage({positions:nodes.map(n=>[n.id,{x:n.x,y:n.y}]),done:iteration>=400});if(iteration>=400){running=false;return;}timer=setTimeout(tick,16);}
self.onmessage=e=>{const m=e.data;if(m.type==='start'){clearTimeout(timer);nodes=m.nodes.map(n=>({...n,vx:0,vy:0}));edges=m.edges;index=new Map(nodes.map(n=>[n.id,n]));iteration=0;running=true;tick();}else if(m.type==='pin'){const n=index.get(m.id);if(n){n.fixed=true;n.x=m.x;n.y=m.y;}}else if(m.type==='pause'){running=false;clearTimeout(timer);self.postMessage({positions:nodes.map(n=>[n.id,{x:n.x,y:n.y}]),done:true});}};
