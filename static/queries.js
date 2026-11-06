'use strict';
// Called after both scripts are loaded, so initial scans can use query controls.

let routeResult=null;
const queryButton=button('Consultar grafo',()=>{$('queryDialog').showModal();refreshQuerySummary();});
$('export').before(queryButton);
for(const language of ['CSS','SCSS','Sass','Less'])$('language').add(new Option(language,language));
$('kind').add(new Option('Hojas de estilo','style'));
Object.assign(colors,{CSS:'#fb91c5',SCSS:'#e96eae',Sass:'#d95ea0',Less:'#88dce6'});
const styleLegend=element('span','● CSS / SCSS');styleLegend.className='style-legend';document.querySelector('.legend').append(styleLegend);
function resetQueries(){
  routeResult=null;$('queryResults').replaceChildren();$('routeResults').replaceChildren();
  $('routeA').value='';$('routeB').value='';$('nodeOptions').replaceChildren();
  graph.nodes.forEach(n=>$('nodeOptions').append(new Option(n.id,n.id)));
  refreshQuerySummary();
}
function refreshQuerySummary(){
  const summary=graph.summary;
  $('graphTotals').textContent=summary?`Repositorio completo: ${summary.nodes} nodos · ${summary.edges} aristas (referencias) · ${summary.connections} conexiones dirigidas únicas · ${summary.isolated} aislados.`:'Analiza un repositorio primero.';
  const pairs=new Set(links.map(e=>JSON.stringify([e.source,e.target])));
  $('visibleTotals').textContent=`Vista filtrada: ${visible.length} nodos · ${links.length} aristas · ${pairs.size} conexiones únicas.`;
}
function addQueryInspector(n,box){
  box.append(element('p',`${n.neighbors} vecinos únicos · ${n.in_degree} conexiones entrantes · ${n.out_degree} salientes · ${n.references_in} aristas entrantes · ${n.references_out} salientes · peso ${n.weight}.`));
  box.append(button('Usar como punto A',()=>{$('routeA').value=n.id;status('Punto A: '+n.id);}));
  box.append(button('Usar como punto B y consultar',()=>{$('routeB').value=n.id;$('queryDialog').showModal();refreshQuerySummary();}));
}
async function postQuery(url,data){return api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});}
$('closeQueries').onclick=()=>$('queryDialog').close();
$('clearRoute').onclick=()=>{routeResult=null;$('routeResults').replaceChildren();draw();};
$('findRoute').onclick=async()=>{
  const action=$('findRoute');action.disabled=true;$('routeResults').textContent='Buscando recorrido…';
  try{
    const result=await postQuery('/api/path',{start:$('routeA').value,end:$('routeB').value,direction:$('routeDirection').value,kind:$('routeKind').value});
    routeResult=result;$('routeResults').replaceChildren();
    if(!result.found){$('routeResults').textContent='No existe un recorrido con esta dirección y tipo de enlace.';draw();return;}
    $('routeResults').append(element('p',`${result.hops} saltos · ${result.nodes.length} nodos. Recorrido mínimo por número de aristas; no representa tráfico de red.`));
    const list=element('ol','');result.nodes.forEach((id,i)=>{
      const item=element('li','');item.append(button(id,()=>{$('queryDialog').close();revealNode(id);}));
      if(i){const step=result.steps[i-1];if(step.edge.file){const file=graph.nodes.find(n=>n.id===step.edge.file);if(file)item.append(button('Ver referencia L'+step.edge.line,()=>showSource(file,step.edge.line||1)));}item.append(element('small',`${step.reversed?'← Recorrida en sentido inverso':'→'} ${step.edge.kind} · ${step.edge.confidence||'referencia'} · ${step.edge.file||''}:${step.edge.line||''}: ${step.edge.detail}`));}
      list.append(item);
    });$('routeResults').append(list);
    $('routeResults').append(button('Ver recorrido en el grafo',()=>{
      $('search').value='';$('language').value='';$('folder').value='';$('kind').value='';$('neighbors').checked=false;$('nodeScope').value='';$('errorsOnly').checked=false;pauseMagnetism();
      filter();const original=visible;visible=graph.nodes.filter(n=>result.nodes.includes(n.id));fit();visible=original;draw();$('queryDialog').close();
      status('Recorrido resaltado en naranja. Usa Consultar grafo → Quitar recorrido para volver a la vista normal.');
    }));draw();
  }catch(error){routeResult=null;$('routeResults').textContent=error.message;draw();}finally{action.disabled=false;}
};
function paintRoute(){
  if(!routeResult||!routeResult.found)return;
  const ids=new Set(visible.map(n=>n.id));ctx.save();ctx.globalAlpha=1;ctx.strokeStyle=themeColor('route');ctx.fillStyle=themeColor('routeFill');ctx.lineWidth=3/camera.k;ctx.setLineDash([]);
  routeResult.steps.forEach(step=>{if(!ids.has(step.from)||!ids.has(step.to))return;const a=positions.get(step.from),b=positions.get(step.to);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();const angle=Math.atan2(b.y-a.y,b.x-a.x),x=(a.x+b.x)/2,y=(a.y+b.y)/2;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x-Math.cos(angle-.5)*12/camera.k,y-Math.sin(angle-.5)*12/camera.k);ctx.lineTo(x-Math.cos(angle+.5)*12/camera.k,y-Math.sin(angle+.5)*12/camera.k);ctx.closePath();ctx.fill();});
  routeResult.nodes.forEach((id,i)=>{if(!ids.has(id))return;const p=positions.get(id);ctx.beginPath();ctx.arc(p.x,p.y,9/camera.k,0,Math.PI*2);ctx.stroke();ctx.font=`bold ${12/camera.k}px Segoe UI`;ctx.fillText(String(i+1),p.x+12/camera.k,p.y-10/camera.k);});ctx.restore();
}
const sqlExamples={
  weight:'SELECT id, language, weight, neighbors, in_degree, out_degree FROM nodes ORDER BY weight DESC, id LIMIT 30',
  incoming:'SELECT id, in_degree, references_in FROM nodes ORDER BY in_degree DESC, id LIMIT 30',
  outgoing:'SELECT id, out_degree, references_out FROM nodes ORDER BY out_degree DESC, id LIMIT 30',
  isolated:'SELECT id, language FROM nodes WHERE neighbors = 0 ORDER BY id',
  totals:'SELECT (SELECT COUNT(*) FROM nodes) AS nodos, (SELECT COUNT(*) FROM edges) AS aristas, (SELECT COUNT(*) FROM connections) AS conexiones',
  languages:'SELECT language, COUNT(*) AS archivos, SUM(weight) AS incidencias FROM nodes GROUP BY language ORDER BY archivos DESC',
  strongest:'SELECT source, target, weight FROM connections ORDER BY weight DESC, source LIMIT 30',
  styles:"SELECT id, language, in_degree FROM nodes WHERE language IN ('CSS','SCSS','Sass','Less') ORDER BY in_degree DESC, id"
};
$('sqlPreset').onchange=()=>{$('sql').value=sqlExamples[$('sqlPreset').value];};$('sql').value=sqlExamples.weight;
$('runSql').onclick=async()=>{
  $('runSql').disabled=true;$('queryResults').textContent='Consultando…';
  try{const result=await postQuery('/api/query',{sql:$('sql').value});$('queryResults').replaceChildren();
    $('queryResults').append(element('p',`${result.rows.length} filas${result.truncated?' · resultado truncado a 500; usa WHERE o LIMIT':''}. Consulta sobre todo el repositorio.`));
    const table=element('table',''),head=element('thead',''),header=element('tr','');result.columns.forEach(c=>header.append(element('th',c)));head.append(header);table.append(head);
    const ids=new Set(graph.nodes.map(n=>n.id)),body=element('tbody','');result.rows.forEach(row=>{const tr=element('tr','');row.forEach(value=>{const cell=element('td','');if(typeof value==='string'&&ids.has(value))cell.append(button(value,()=>{$('queryDialog').close();revealNode(value);}));else cell.textContent=value===null?'NULL':String(value);tr.append(cell);});body.append(tr);});table.append(body);$('queryResults').append(table);
  }catch(error){$('queryResults').textContent=error.message;}finally{$('runSql').disabled=false;}
};
