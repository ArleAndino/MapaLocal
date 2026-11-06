'use strict';
const palettes={dark:{background:'#0b111e',edge:'#344864',active:'#72dec1',label:'#a6b7d0',selected:'#fff',outline:'#eafff9',route:'#ffb454',routeFill:'#ffce87'},light:{background:'#f2f6fc',edge:'#8a9bb5',active:'#087b66',label:'#354662',selected:'#142439',outline:'#24435b',route:'#a95300',routeFill:'#814100'}};
function themeColor(name){return palettes[document.documentElement.dataset.theme==='light'?'light':'dark'][name];}
const themeButton=button('Tema claro',()=>setTheme(document.documentElement.dataset.theme==='light'?'dark':'light'));
themeButton.id='themeToggle';document.querySelector('header').append(themeButton);
const branchBadge=element('span','Rama: pendiente de análisis');branchBadge.id='branchBadge';document.querySelector('header').append(branchBadge);
function setTheme(theme){
  document.documentElement.dataset.theme=theme;themeButton.textContent=theme==='light'?'Tema oscuro':'Tema claro';themeButton.setAttribute('aria-label','Cambiar a '+themeButton.textContent.toLowerCase());
  Object.assign(colors,theme==='light'?{'TypeScript':'#226ac4','C#':'#8445c3','JavaScript':'#946500',CSS:'#b8377e',SCSS:'#9c2869',Sass:'#85305f',Less:'#087d8b'}:{'TypeScript':'#69aaff','C#':'#c49aff','JavaScript':'#efc667',CSS:'#fb91c5',SCSS:'#e96eae',Sass:'#d95ea0',Less:'#88dce6'});
  try{localStorage.setItem('mapalocal-theme',theme);}catch(_){}draw();
}
function updateBranch(graph){
  const git=graph.git;
  const label=!git?'Rama: sin datos (análisis anterior)':!git.available?'Git no disponible':!git.repository?'Sin repositorio Git':git.detached?'HEAD separado · '+git.commit.slice(0,8):'Rama: '+(git.branch||'desconocida');
  branchBadge.textContent=label;branchBadge.title='Estado al analizar. Vuelve a analizar para actualizarlo.'+(git&&git.commit?' Commit: '+git.commit:'');
  if(git)branchBadge.title+=' · '+(git.ignore_applied?'.gitignore aplicado':'.gitignore no aplicado');
}
let preferredTheme='dark';try{preferredTheme=localStorage.getItem('mapalocal-theme')||'dark';}catch(_){}
setTheme(preferredTheme==='light'?'light':'dark');
