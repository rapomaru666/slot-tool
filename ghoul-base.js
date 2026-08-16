document.addEventListener('DOMContentLoaded',()=>{
const C=window.MACHINE_CONFIG||{};
const metrics=C.metrics||[];
const values=Array(metrics.length).fill(0);
let totalMode=true;
const $=id=>document.getElementById(id);
const metricsEl=$('metrics'),result=$('result-section'),pred=$('prediction-text'),bars=$('bars'),games=$('games'),start=$('start-games');
function row(m,i){return `<div class="bonus-row${i===0?' important':''}"><span>${m.name}</span><div class="counter"><button class="counter-btn minus" data-i="${i}" data-n="-1">−</button><span id="v${i}">0</span><button class="counter-btn plus" data-i="${i}" data-n="1">＋</button></div></div>`}
metricsEl.innerHTML=metrics.map(row).join('');
bars.innerHTML=[1,2,3,4,5,6].map(s=>`<div class="graph-row"><span>設定${s}</span><div class="bar-bg"><div id="bar${s}" class="bar"></div></div><span id="pct${s}">0%</span></div>`).join('');
metricsEl.addEventListener('click',e=>{const b=e.target.closest('button[data-i]');if(!b)return;const i=+b.dataset.i;values[i]=Math.max(0,values[i]+(+b.dataset.n));$('v'+i).textContent=values[i]});
$('game-mode')?.addEventListener('click',()=>{totalMode=!totalMode;$('game-mode').classList.toggle('on',totalMode);$('mode-label').textContent=totalMode?'ON':'OFF'});
document.querySelectorAll('.material-grid button,.material-list button').forEach(b=>b.addEventListener('click',()=>{const p=b.parentElement;p.querySelectorAll('button').forEach(x=>x.classList.remove('selected'));b.classList.add('selected')}));
function targetGames(){const g=Number(games?.value||0),s=Number(start?.value||0);return totalMode?g:Math.max(0,g-s)}
function factorialLog(n){let x=0;for(let i=2;i<=n;i++)x+=Math.log(i);return x}
function pois(g,n,r){if(!r||g<=0)return 0;const l=g/r;return n===0?-l:n*Math.log(l)-l-factorialLog(n)}
function probabilities(){const g=targetGames();if(g<=0)return null;const logs=[];let usable=0;for(let k=0;k<6;k++){let x=0;metrics.forEach((m,i)=>{const r=(m.rates||[])[k];if(!r||values[i]===0)return;usable++;x+=pois(g,values[i],r)});logs.push(x)}if(!usable)return null;const m=Math.max(...logs),w=logs.map(x=>Math.exp(x-m)),sum=w.reduce((a,b)=>a+b,0)||1;return w.map(x=>x/sum*100)}
function render(p){for(let s=1;s<=6;s++){const v=p?.[s-1]||0;$('bar'+s).style.width=`${Math.min(100,Math.max(0,v))}%`;$('pct'+s).textContent=`${Math.round(v)}%`}if(!p){pred.textContent='設定予測：判定材料不足';return}const m=Math.max(...p),i=p.indexOf(m);pred.textContent=`設定予測：設定${i+1}が最有力　（判別対象 ${targetGames()}G）`}
$('judge-btn').addEventListener('click',()=>{const g=targetGames();if(g<=0){alert('判別対象ゲーム数を入力してください。');return}render(probabilities());result.classList.add('visible');result.scrollIntoView({behavior:'smooth',block:'start'})});
$('reset-btn').addEventListener('click',()=>{games.value='';start.value='';totalMode=true;$('game-mode')?.classList.add('on');if($('mode-label'))$('mode-label').textContent='ON';values.fill(0);values.forEach((_,i)=>$('v'+i).textContent='0');document.querySelectorAll('.material-grid button,.material-list button').forEach(b=>b.classList.remove('selected'));for(let s=1;s<=6;s++){$('bar'+s).style.width='0%';$('pct'+s).textContent='0%'}pred.textContent='-';result.classList.remove('visible')});
});
