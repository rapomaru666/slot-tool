const container=document.getElementById('tools');
const COUNTER_NAMESPACE='rapomaru-slot-tool';
const BASE='https://rapomaru666.github.io/slot-tool/';

function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function keyName(s){return String(s??'').toLowerCase().replace(/[\s　・･‐‑‒–—―ー－:：/／\\()（）\[\]【】「」『』,.，．!！?？~〜～'\"]/g,'')}
function labelName(name){return String(name||'SLOT').replace(/^L\s*パチスロ\s*/i,'').replace(/^スマスロ\s*/,'').replace(/^パチスロ\s*/,'').slice(0,28).toUpperCase()}
function existingNameKeys(){return new Set([...container.querySelectorAll('.tool h3')].map(x=>keyName(x.textContent)))}

function addMasterTool(row){
  const name=String(row.name||'').trim(); if(!name)return;
  const keys=existingNameKeys(); if(keys.has(keyName(name)))return;
  const isMonkey=name==='スマスロモンキーターンV';
  const monkeyFile='monkeyturn5-index.html';
  const available=isMonkey||(row.toolStatus==='available' && row.file);
  const file=isMonkey?monkeyFile:row.file;
  const ghoulBase=!!row.ghoulBase;
  const a=document.createElement('a');
  a.className='tool'; a.dataset.machine=name; a.dataset.status=available?'available':'pending'; a.dataset.ghoulBase=ghoulBase?'1':'0';
  a.href=available?BASE+file:'#';
  const year=row.year||'';
  const statusTag=available?(ghoulBase?'喰種ベース':'設定判別'):'作成中';
  a.innerHTML='<span class="new">'+esc(year)+'</span><div class="machine">'+esc(labelName(name))+'<br><b>777</b></div><h3>'+esc(name)+'</h3><p>'+(available?'設定判別ツール':'作成中....')+'</p><div class="tags"><i>'+esc(year)+'年</i><i>'+statusTag+'</i></div><button>'+(available?'使う　›':'作成中')+'</button>';
  container.appendChild(a);
}

async function discoverAllTools(){
  try{
    const r=await fetch('RAPOMAN-MACHINE-MASTER.json?'+Date.now(),{cache:'no-store'});
    if(r.ok){
      const master=await r.json();
      if(Array.isArray(master.machines)&&master.machines.length){master.machines.forEach(addMasterTool);return}
    }
  }catch(e){console.warn('master load failed',e)}
  try{
    const r=await fetch('machines.json?'+Date.now(),{cache:'no-store'});
    if(r.ok){const manifest=await r.json();if(Array.isArray(manifest.tools))manifest.tools.forEach(x=>{if(x.file)addMasterTool({name:x.file.replace(/-index\.html$/,'').replace(/[-_]+/g,' '),year:'',file:x.file,toolStatus:'available'})})}
  }catch(e){console.warn('fallback manifest load failed',e)}
}

function counterName(tool){const raw=tool.getAttribute('href')||'';const file=raw.split('/').pop().split('?')[0].replace(/\.html$/,'');return file.replace(/[^a-zA-Z0-9_-]/g,'-')}
function counterGet(name){if(!name)return Promise.resolve(0);return fetch('https://api.counterapi.dev/v1/'+encodeURIComponent(COUNTER_NAMESPACE)+'/'+encodeURIComponent(name),{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>Number(d&&d.count||d&&d.value||0)).catch(()=>0)}
function counterUp(name){if(!name)return Promise.resolve(null);return fetch('https://api.counterapi.dev/v1/'+encodeURIComponent(COUNTER_NAMESPACE)+'/'+encodeURIComponent(name)+'/up',{cache:'no-store'}).catch(()=>null)}

async function loadRecommended(){
  const tools=[...container.querySelectorAll('.tool')];
  const available=tools.filter(t=>t.dataset.status!=='pending');
  const ranked=await Promise.all(available.map(async(tool,index)=>({tool,index,count:await counterGet(counterName(tool))})));
  ranked.sort((a,b)=>b.count-a.count||a.index-b.index);
  tools.forEach(t=>t.style.display='none');
  ranked.slice(0,5).forEach(({tool})=>{tool.style.display='block';container.appendChild(tool)});
}

function setupClicks(){container.querySelectorAll('.tool').forEach(tool=>{if(tool.dataset.bound)return;tool.dataset.bound='1';tool.addEventListener('click',async e=>{if(tool.dataset.status==='pending'){e.preventDefault();return}if(e.target.closest('button')||e.currentTarget===tool){e.preventDefault();const href=tool.href;await counterUp(counterName(tool));location.href=href}})})}

async function boot(){await discoverAllTools();await loadRecommended();setupClicks()}
boot();

const input=document.getElementById('search');const btn=document.getElementById('searchBtn');
function search(){const q=input.value.trim().toLowerCase();const tools=[...document.querySelectorAll('.tool')];if(!q){loadRecommended();document.getElementById('tools').scrollIntoView({behavior:'smooth'});return}let found=0;tools.forEach(t=>{const hit=t.textContent.toLowerCase().includes(q);t.style.display=hit?'block':'none';if(hit)found++});document.getElementById('tools').scrollIntoView({behavior:'smooth'});if(!found)alert('該当するツールがありません。')}
btn.addEventListener('click',search);input.addEventListener('keydown',e=>{if(e.key==='Enter')search()});input.addEventListener('input',()=>{if(!input.value.trim())loadRecommended()});
