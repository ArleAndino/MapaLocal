'use strict';
let picking=null, busy=false;
const hideProgress=button('Ocultar',()=>{$('scanProgress').hidden=true;});hideProgress.id='hideProgress';$('scanProgress').append(hideProgress);
const routePickButton=button('Buscar recorrido A → B',()=>{
  if(picking){picking=null;routePickButton.textContent='Buscar recorrido A → B';status('Selección de recorrido cancelada.');return;}
  if(!graph.nodes.length){status('Analiza un repositorio primero.');return;}
  picking='A';routePickButton.textContent='Cancelar selección';status('Selecciona el punto A en el grafo o en la lista de archivos.');
});
const saveViewButton=button('Guardar vista',saveView);
const historyButton=button('Historial',showHistory);
const pngButton=button('Descargar PNG',downloadGraphImage);
const actions=element('div','');actions.className='graph-actions';actions.append(routePickButton,saveViewButton,historyButton,pngButton);
document.querySelector('.map').append(actions);
const swapButton=button('Intercambiar A ↔ B',()=>{const a=$('routeA').value;$('routeA').value=$('routeB').value;$('routeB').value=a;});$('findRoute').after(swapButton);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&picking){picking=null;routePickButton.textContent='Buscar recorrido A → B';status('Selección cancelada.');}});
function pickRoutePoint(id){
  if(busy||!picking)return;
  if(picking==='A'){$('routeA').value=id;picking='B';status('A: '+id+'. Ahora selecciona el punto B.');}
  else{$('routeB').value=id;picking=null;routePickButton.textContent='Buscar recorrido A → B';$('queryDialog').showModal();refreshQuerySummary();status('Puntos A y B seleccionados. Pulsa Buscar recorrido.');}
}
function setBusy(value){busy=value;if($('analyzeMenu'))$('analyzeMenu').disabled=value;if($('analysisMode'))$('analysisMode').disabled=value;if($('layoutMode'))$('layoutMode').disabled=value;$('scanButton').disabled=value;routePickButton.disabled=value;saveViewButton.disabled=value;historyButton.disabled=value;queryButton.disabled=value;$('export').disabled=value||!graph.nodes.length;pngButton.disabled=value;}
function progress(percent,phase,detail){$('scanProgress').hidden=false;hideProgress.hidden=percent<100;$('progressBar').value=percent;$('progressText').textContent=`${percent}% · ${phase}`;$('progressDetail').textContent=detail||'';}
function adoptGraph(data,view=null){
  resetLayouts(view);graph=data;updateBranch(data);refreshProjectInfo();$('analysisMode').value=data.analysis_mode||'normal';$('errorsOnly').checked=false;$('nodeScope').value='';selected=null;picking=null;routePickButton.textContent='Buscar recorrido A → B';positions=new Map();
  $('neighbors').checked=false;$('search').value='';$('language').value='';$('kind').value='';$('root').value=data.root;
  $('folder').replaceChildren(new Option('Todas las carpetas',''));[...new Set(graph.nodes.map(n=>n.folder))].sort().forEach(f=>$('folder').add(new Option(f,f)));
  $('stats').textContent=`${data.summary.files} archivos · ${data.summary.edges} enlaces`;$('export').disabled=false;$('empty').hidden=true;
  resetQueries();layout();
  if(view){
    for(const n of graph.nodes){const p=view.positions&&view.positions[n.id];if(p&&Number.isFinite(p.x)&&Number.isFinite(p.y))positions.set(n.id,{x:p.x,y:p.y});}
    for(const id of ['search','language','folder','kind','nodeScope'])if(view.filters&&typeof view.filters[id]==='string')$(id).value=view.filters[id];
    $('neighbors').checked=Boolean(view.filters&&view.filters.neighbors);$('errorsOnly').checked=Boolean(view.filters&&view.filters.errorsOnly);
    selected=graph.nodes.some(n=>n.id===view.selected)?view.selected:null;
    if(view.route&&Array.isArray(view.route.nodes)&&Array.isArray(view.route.steps))routeResult=view.route;
    $('routeA').value=view.routeA||'';$('routeB').value=view.routeB||'';$('routeDirection').value=view.routeDirection||'directed';
    $('sql').value=view.sql||sqlExamples.weight;
  }
  filter();fit();
  if(view&&view.camera&&Number.isFinite(view.camera.k)&&view.camera.k>=.01&&view.camera.k<=12){camera={...view.camera};if(view.viewport){camera.x+=(width-view.viewport.width)/2;camera.y+=(height-view.viewport.height)/2;}draw();}
  inspect();refreshQuerySummary();
}
$('scan').onsubmit=async e=>{
  e.preventDefault();if(busy)return;pauseMagnetism();setBusy(true);picking=null;routePickButton.textContent='Buscar recorrido A → B';progress(0,'Iniciando análisis','El porcentaje se calcula por fases; no es una estimación de tiempo.');
  try{
    const job=await postQuery('/api/scan/start',{root:$('root').value,mode:$('analysisMode').value,excludes:$('excludes').value.split(',').map(x=>x.trim()).filter(Boolean)});
    let state;
    do{
      state=await api('/api/progress?id='+encodeURIComponent(job.id));
      if(state.state==='error')throw Error(state.error);
      progress(Math.min(state.percent,99),state.phase,state.detail);
      if(state.state==='running')await new Promise(resolve=>setTimeout(resolve,300));
    }while(state.state==='running');
    progress(99,'Dibujando grafo','Preparando nodos y conexiones…');
    const data=await api('/api/graph?id='+encodeURIComponent(job.id));adoptGraph(data);
    progress(100,'Análisis completado y guardado en JSON',`${data.summary.files} archivos · ${data.nodes.length} nodos · ${data.edges.length} aristas`);
    status(`Guardado en el historial local · ${data.summary.unresolved} imports sin resolver · ${data.warnings.length} avisos. ${data.warnings.slice(0,3).join(' | ')}`);showCoverage();
  }catch(error){hideProgress.hidden=false;$('progressText').textContent='No se completó el análisis';$('progressDetail').textContent=error.message;status(error.message);}
  finally{setBusy(false);}
};
function currentView(){pauseMagnetism();layoutCache[layoutMode]=snapshotLayout();return {layoutMode,layouts:layoutCache,pinned:[...pinned],positions:Object.fromEntries(positions),camera:{...camera},viewport:{width,height},selected,
  filters:{search:$('search').value,language:$('language').value,folder:$('folder').value,kind:$('kind').value,neighbors:$('neighbors').checked,nodeScope:$('nodeScope').value,errorsOnly:$('errorsOnly').checked},
  route:routeResult,routeA:$('routeA').value,routeB:$('routeB').value,routeDirection:$('routeDirection').value,sql:$('sql').value};}
async function saveView(){
  if(!graph.analysis_id){status('Analiza un repositorio antes de guardar la vista.');return;}
  saveViewButton.disabled=true;
  try{await postQuery('/api/history/save',{analysis_id:graph.analysis_id,view:currentView(),label:'Vista del grafo'});status('Vista guardada en JSON: posiciones, zoom, filtros, selección y recorrido. Puedes reabrirla desde Historial.');}
  catch(error){status(error.message);}finally{saveViewButton.disabled=false;}
}
async function showHistory(){
  $('historyDialog').showModal();$('historyItems').textContent='Cargando historial…';
  try{const data=await api('/api/history');$('historyDirectory').textContent='Carpeta local: '+data.directory;$('historyItems').replaceChildren();
    if(!data.items.length)$('historyItems').textContent='Todavía no hay análisis guardados.';
    data.items.forEach(item=>{const row=element('article','');row.append(element('strong',item.label+' · '+new Date(item.created_at).toLocaleString()));
      row.append(element('p',item.root));if(item.git)row.append(element('p',item.git.repository?(item.git.branch||('HEAD separado · '+(item.git.commit||'').slice(0,8))):'Sin repositorio Git'));row.append(element('p',`${item.summary.nodes} nodos · ${item.summary.edges} aristas${item.has_view?' · con vista guardada':''}`));
      row.append(button('Abrir análisis',async()=>{setBusy(true);try{const snapshot=await postQuery('/api/history/load',{id:item.id});adoptGraph(snapshot.graph,snapshot.view);$('historyDialog').close();$('scanProgress').hidden=true;status('Análisis histórico cargado. El visor de código lee los archivos actuales, si todavía existen.');}catch(error){$('historyDirectory').textContent=error.message;}finally{setBusy(false);}}));$('historyItems').append(row);
    });
  }catch(error){$('historyItems').textContent=error.message;}
}
$('closeHistory').onclick=()=>$('historyDialog').close();
function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export').onclick=()=>downloadBlob(new Blob([JSON.stringify({format:'mapalocal',version:1,created_at:new Date().toISOString(),graph,view:currentView()},null,2)],{type:'application/json'}),'mapa-local.json');
function downloadGraphImage(){
  if(!graph.nodes.length){status('Analiza un repositorio primero.');return;}
  const output=document.createElement('canvas');output.width=canvas.width;output.height=canvas.height;const context=output.getContext('2d');context.fillStyle=themeColor('background');context.fillRect(0,0,output.width,output.height);context.drawImage(canvas,0,0);
  output.toBlob(blob=>{if(blob){downloadBlob(blob,'mapa-local.png');status('Imagen PNG descargada: muestra el encuadre y los filtros actuales.');}else status('No se pudo crear la imagen.');},'image/png');
}

