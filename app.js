const container=document.getElementById('tools');
const COUNTER_NAMESPACE='rapomaru-slot-tool';
const BASE='https://rapomaru666.github.io/slot-tool/';
const pending2026=[['darkhaibi-index.html','DARK HAIBI','スマート沖スロ ダークハイビ'],['sao2-index.html','SAO II','スロット ソードアート・オンラインII'],['sengokuotome5-index.html','SENGOKU OTOME 5','L戦国乙女5 業火を穿つ宿焔の双刃'],['birdiewing-index.html','BIRDIE WING','スマスロ BIRDIE WING -Golf Girls\' Story-'],['karakuri2-index.html','KARAKURI 2','Lパチスロ からくりサーカス2'],['kerotto5bt-index.html','KEROTTO 5 BT','スマスロケロット5BT'],['ultraman-final-index.html','ULTRAMAN FINAL','Ｌ ULTRAMAN 最終決戦'],['nangoku-special-index.html','NANGOKU SPECIAL','L南国育ちSPECIAL'],['rotis-index.html','ROTIS','ローティス'],['yajikita-index.html','YAJIKITA','スマスロ やじきた道中記参る！'],['tondemo-skill-index.html','TONDEMO SKILL','スマスロ とんでもスキルで異世界放浪メシ'],['superbin-index.html','SUPER BIN','Lすーぱぁびん娘'],['toaru-index.html','TOARU','スマスロ とある魔術の禁書目録2'],['world-dai-star-index.html','WORLD DAI STAR','スロット ワールドダイスター'],['streetfighter6-index.html','STREET FIGHTER 6','スマスロ ストリートファイター6'],['garei-zero-re-index.html','GA-REI ZERO Re','Lパチスロ 喰霊‐零‐Re']];
const added2025=[['hihouden-index.html','HIHOUDEN','スマスロ 秘宝伝'],['mushokutensei-index.html','MUSHOKU TENSEI','L 無職転生 ～異世界行ったら本気だす～'],['fujikobt-index.html','FUJIKO BT','L不二子BT'],['okidoki-duo-encore-index.html','OKIDOKI DUO','スマスロ 沖ドキ！DUO アンコール'],['bakemonogatari-index.html','BAKEMONOGATARI','スマスロ 化物語']];
[...pending2026.map(x=>[...x,'2026']),...added2025.map(x=>[...x,'2025'])].forEach(addTool);
function addTool([href,label,title,year='']){if(container.querySelector('a[href="'+BASE+href+'"]'))return;const a=document.createElement('a');a.className='tool';a.href=BASE+href;a.innerHTML='<span class="new">'+year+'</span><div class="machine">'+label+'<br><b>777</b></div><h3>'+title+'</h3><p>設定判別ツール</p><div class="tags"><i>'+year+'年</i><i>設定判別</i></div><button>使う　›</button>';container.appendChild(a)}
function prettyName(file){return file.replace(/-index\.html$/,'').replace(/[-_]+/g,' ').replace(/\b\w/g,m=>m.toUpperCase())}
async function discoverAllTools(){
  try{
    const files=[];
    for(let page=1;page<=10;page++){
      const r=await fetch('https://api.github.com/repos/rapomaru666/slot-tool/contents/?ref=main&per_page=100&page='+page,{cache:'no-store'});
      if(!r.ok)break;
      const batch=await r.json();
      if(!Array.isArray(batch)||!batch.length)break;
      files.push(...batch);
      if(batch.length<100)break;
    }
    files.filter(x=>x.type==='file'&&/-index\.html$/.test(x.name)&&x.name!=='index.html'&&!x.path.startsWith('backup/')).forEach(x=>addTool([x.name,prettyName(x.name),'L '+prettyName(x.name),'']))
  }catch(e){console.warn('portal auto discovery failed',e)}
}
function counterName(tool){const raw=tool.getAttribute('href')||'';const file=raw.split('/').pop().split('?')[0].replace(/\.html$/,'');return file.replace(/[^a-zA-Z0-9_-]/g,'-')}
function counterGet(name){return fetch('https://api.counterapi.dev/v1/'+encodeURIComponent(COUNTER_NAMESPACE)+'/'+encodeURIComponent(name),{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>Number(d&&d.count||d&&d.value||0)).catch(()=>0)}
function counterUp(name){return fetch('https://api.counterapi.dev/v1/'+encodeURIComponent(COUNTER_NAMESPACE)+'/'+encodeURIComponent(name)+'/up',{cache:'no-store'}).catch(()=>null)}
async function loadRecommended(){const tools=[...container.querySelectorAll('.tool')];const ranked=await Promise.all(tools.map(async(tool,index)=>({tool,index,count:await counterGet(counterName(tool))})));ranked.sort((a,b)=>b.count-a.count||a.index-b.index);tools.forEach(t=>t.style.display='none');ranked.slice(0,5).forEach(({tool})=>{tool.style.display='block';container.appendChild(tool)})}
function setupClicks(){container.querySelectorAll('.tool').forEach(tool=>{if(tool.dataset.bound)return;tool.dataset.bound='1';tool.addEventListener('click',async e=>{if(e.target.closest('button')||e.currentTarget===tool){e.preventDefault();const href=tool.href;await counterUp(counterName(tool));location.href=href}})})}
async function boot(){await discoverAllTools();await loadRecommended();setupClicks()}
boot();
const input=document.getElementById('search');const btn=document.getElementById('searchBtn');
function search(){const q=input.value.trim().toLowerCase();const tools=[...document.querySelectorAll('.tool')];if(!q){tools.forEach(t=>t.style.display='block');document.getElementById('tools').scrollIntoView({behavior:'smooth'});return}let found=0;tools.forEach(t=>{const hit=t.textContent.toLowerCase().includes(q);t.style.display=hit?'block':'none';if(hit)found++});document.getElementById('tools').scrollIntoView({behavior:'smooth'});if(!found)alert('該当するツールがありません。')}
btn.addEventListener('click',search);input.addEventListener('keydown',e=>{if(e.key==='Enter')search()});input.addEventListener('input',()=>{if(!input.value.trim())loadRecommended()});