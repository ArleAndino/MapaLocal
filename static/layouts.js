'use strict';
function gravityPositions(nodes){
 const groups=new Map();for(const n of nodes){const key=n.language+':'+n.folder;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(n);}
 const blocks=[];for(const group of groups.values()){
  const bins=new Map();for(const n of group){const weight=n.neighbors||0;if(!bins.has(weight))bins.set(weight,[]);bins.get(weight).push(n);}
  const columns=Math.max(3,Math.ceil(Math.sqrt(group.length))),points=[];let y=30;
  for(const weight of [...bins.keys()].sort((a,b)=>a-b)){const bin=bins.get(weight);bin.forEach((n,i)=>points.push([n.id,{x:30+(i%columns)*34,y:y+Math.floor(i/columns)*28}]));y+=Math.ceil(bin.length/columns)*28+35+Math.log1p(weight)*12;}
  blocks.push({points,w:columns*34+90,h:y+60});
 }
 const columns=Math.ceil(Math.sqrt(blocks.length)),width=Math.max(320,...blocks.map(b=>b.w)),height=Math.max(320,...blocks.map(b=>b.h)),result=new Map();
 blocks.forEach((b,i)=>b.points.forEach(([id,p])=>result.set(id,{x:p.x+(i%columns)*width,y:p.y+Math.floor(i/columns)*height})));return result;
}
let layoutMode='grid',layoutCache={},layoutWorker=null,magneticRunning=false,pinned=new Set();
function snapshotLayout(){return {positions:Object.fromEntries(positions),camera:{...camera},pinned:[...pinned]};}
function pauseMagnetism(){if(layoutWorker){layoutWorker.terminate();layoutWorker=null;}magneticRunning=false;if($('pauseLayout'))$('pauseLayout').textContent='▶ Reanudar';}
function startMagnetism(){
 pauseMagnetism();if(!graph.nodes.length)return;
 layoutWorker=new Worker('/layout-worker.js');magneticRunning=true;$('pauseLayout').textContent='Ⅱ Pausar';
 layoutWorker.onmessage=e=>{if(layoutMode!=='magnetism')return;for(const [id,p] of e.data.positions){if(drag&&drag.id===id)continue;positions.set(id,p);}draw();if(e.data.done){magneticRunning=false;$('pauseLayout').textContent='▶ Reanudar';}};
 layoutWorker.onerror=()=>{pauseMagnetism();status('No se pudo continuar la simulación. Se conserva la última posición.');};
 layoutWorker.postMessage({type:'start',nodes:graph.nodes.map(n=>({id:n.id,...positions.get(n.id),fixed:pinned.has(n.id)})),edges:graph.connections||[]});
}
function setLayout(mode){
 if(!['grid','gravity','magnetism'].includes(mode)||mode===layoutMode)return;
 layoutCache[layoutMode]=snapshotLayout();pauseMagnetism();layoutMode=mode;$('layoutMode').value=mode;
 const saved=layoutCache[mode];pinned=new Set(saved?saved.pinned||[]:[]);
 if(saved){positions=new Map(Object.entries(saved.positions));camera={...saved.camera};}
 else if(mode==='grid'){layout();fit();}
 else if(mode==='gravity'){positions=gravityPositions(graph.nodes);fit();}
 else{const radius=Math.max(180,Math.sqrt(graph.nodes.length)*35);graph.nodes.forEach((n,i)=>positions.set(n.id,{x:Math.cos(i*2.39996)*radius*Math.sqrt((i+1)/graph.nodes.length),y:Math.sin(i*2.39996)*radius*Math.sqrt((i+1)/graph.nodes.length)}));fit();}
 $('pauseLayout').hidden=mode!=='magnetism';$('unpinLayout').hidden=mode!=='magnetism';draw();
 if(mode==='magnetism'&&!saved)startMagnetism();
 status(mode==='gravity'?'Gravedad: más vecinos únicos → más abajo dentro de cada grupo.':mode==='magnetism'?'Magnetismo: conexiones de mayor peso atraen más. Arrastra un nodo para fijarlo.':'Cuadrícula original.');
}
function resetLayouts(view){pauseMagnetism();layoutMode=view&&view.layoutMode||'grid';layoutCache=view&&view.layouts||{};pinned=new Set(view&&view.pinned||[]);$('layoutMode').value=layoutMode;$('pauseLayout').hidden=layoutMode!=='magnetism';$('unpinLayout').hidden=layoutMode!=='magnetism';}
function pinNode(id){if(layoutMode!=='magnetism')return;pinned.add(id);if(layoutWorker)layoutWorker.postMessage({type:'pin',id,...positions.get(id)});}
