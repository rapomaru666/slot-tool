const container=document.getElementById('tools');
const COUNTER_NAMESPACE='rapomaru-slot-tool';

const pending2026=[['darkhaibi-index.html','DARK HAIBI','スマート沖スロ ダークハイビ'],['sao2-index.html','SAO II','スロット ソードアート・オンラインII'],['sengokuotome5-index.html','SENGOKU OTOME 5','L戦国乙女5 業火を穿つ宿焔の双刃'],['birdiewing-index.html','BIRDIE WING','スマスロ BIRDIE WING -Golf Girls\\' Story-'],['karakuri2-index.html','KARAKURI 2','Lパチスロ からくりサーカス2'],['kerotto5bt-index.html','KEROTTO 5 BT','スマスロケロット5BT'],['ultraman-final-index.html','ULTRAMAN FINAL','Ｌ ULTRAMAN 最終決戦'],['nangoku-special-index.html','NANGOKU SPECIAL','L南国育ちSPECIAL'],['rotis-index.html','ROTIS','ローティス'],['yajikita-index.html','YAJIKITA','スマスロ やじきた道中記参る！'],['tondemo-skill-index.html','TONDEMO SKILL','スマスロ とんでもスキルで異世界放浪メシ'],['superbin-index.html','SUPER BIN','Lすーぱぁびん娘'],['toaru-index.html','TOARU','スマスロ とある魔術の禁書目録2'],['world-dai-star-index.html','WORLD DAI STAR','スロット ワールドダイスター'],['streetfighter6-index.html','STREET FIGHTER 6','スマスロ ストリートファイター6'],['garei-zero-re-index.html','GA-REI ZERO Re','Lパチスロ 喰霊‐零‐Re']];
pending2026.forEach(([href,label,title])=>{const a=document.createElement('a');a.className='tool';a.href='https://rapomaru666.github.io/slot-tool/'+href;a.innerHTML='<span class="new">2026</span><div class="machine">'+label+'<br><b>777</b></div><h3>'+title+'</h3><p>作成中....</p><div class="tags"><i>2026年</i><i>作成中</i></div><button>使う　›</button>';container.appendChild(a)});

function counterName(tool){
  const raw=tool.getAttribute('href')||'';
  const file=raw.split('/').pop().split('?')[0].replace(/\.html$/,'');
  return file.replace(/[^a-zA-Z0-9_-]/g,'-');
}
function counterGet(name){
  return fetch('https://api.counterapi.dev/v1/'+encodeURIComponent(COUNTER_NAMESPACE)+'/'+encodeURIComponent(name),{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>Number(d&&d.count||d&&d.value||0)).catch(()=>0);
}
function counterUp(name){
  return fetch('https://api.counterapi.dev/v1/'+encodeURIComponent(COUNTER_NAMESPACE)+'/'+encodeURIComponent(name)+'/up',{cache:'no-store'}).catch(()=>null);
}

async function loadRecommended(){
  const tools=[...container.querySelectorAll('.tool')];
  const ranked=await Promise.all(tools.map(async (tool,index)=>({tool,index,count:await counterGet(counterName(tool))})));
  ranked.sort((a,b)=>b.count-a.count||a.index-b.index);
  tools.forEach(t=>t.style.display='none');
  ranked.slice(0,5).forEach(({tool})=>{tool.style.display='block';container.appendChild(tool)});
}

function setupClicks(){
  container.querySelectorAll('.tool').forEach(tool=>{
    tool.addEventListener('click',async e=>{
      if(e.target.closest('button')||e.currentTarget===tool){
        e.preventDefault();
        const href=tool.href;
        await counterUp(counterName(tool));
        location.href=href;
      }
    });
  });
}

loadRecommended().finally(setupClicks);

const input=document.getElementById('search');const btn=document.getElementById('searchBtn');
function search(){const q=input.value.trim().toLowerCase();const tools=[...document.querySelectorAll('.tool')];if(!q){tools.forEach(t=>t.style.display='block');document.getElementById('tools').scrollIntoView({behavior:'smooth'});return}let found=0;tools.forEach(t=>{const hit=t.textContent.toLowerCase().includes(q);t.style.display=hit?'block':'none';if(hit)found++});document.getElementById('tools').scrollIntoView({behavior:'smooth'});if(!found)alert('該当するツールがありません。');}
btn.addEventListener('click',search);input.addEventListener('keydown',e=>{if(e.key==='Enter')search()});input.addEventListener('input',()=>{if(!input.value.trim())loadRecommended()});