(() => {
  "use strict";
  const CFG = window.JUGGLER_CONFIG || {};
  const ROWS = 100;
  const COST_PER_GAME = 50 / Number(CFG.gamesPer50 || 42);
  const PAYOUT = { BIG: Number(CFG.bigPayout || 240), REG: Number(CFG.regPayout || 96) };
  const SETTING_RATES = Array.isArray(CFG.settingRates) ? CFG.settingRates : [];

  const rowsEl = document.getElementById("rows");
  const canvas = document.getElementById("slumpChart");
  const emptyState = document.getElementById("emptyState");
  const ctx = canvas.getContext("2d");
  const $ = id => document.getElementById(id);
  const totalGamesEl = $("totalGames"), bigCountEl = $("bigCount"), regCountEl = $("regCount");
  const currentDiffEl = $("currentDiff"), maxPlusEl = $("maxPlus"), maxMinusEl = $("maxMinus");
  const bigProbEl = $("bigProb"), regProbEl = $("regProb"), estimatedSettingEl = $("estimatedSetting");
  const fmt = n => Math.round(n).toLocaleString("ja-JP");

  function formatProb(totalGames, count) {
    if (!totalGames || !count) return "—";
    return "1/" + (totalGames / count).toFixed(1);
  }

  function estimateSetting(totalGames, big, reg) {
    if (!totalGames || !SETTING_RATES.length) return null;
    const none = Math.max(0, totalGames - big - reg);
    let best = null;
    for (const row of SETTING_RATES) {
      const pBig = 1 / row.big, pReg = 1 / row.reg;
      const pNone = Math.max(1e-12, 1 - pBig - pReg);
      const score = big * Math.log(pBig) + reg * Math.log(pReg) + none * Math.log(pNone);
      if (!best || score > best.score) best = { setting: row.setting, score };
    }
    return best ? best.setting : null;
  }

  function makeRows() {
    const frag = document.createDocumentFragment();
    for (let i = 1; i <= ROWS; i++) {
      const row = document.createElement("div");
      row.className = "history-row";
      row.innerHTML = `
        <div class="row-no">${i}</div>
        <input class="game-input" type="number" min="0" step="1" inputmode="numeric" placeholder="G数" aria-label="${i}回目 ゲーム数">
        <select class="bonus-select" aria-label="${i}回目 ボーナス種類">
          <option value="">なし</option>
          <option value="BIG">BIG</option>
          <option value="REG">REG</option>
        </select>`;
      frag.appendChild(row);
    }
    rowsEl.appendChild(frag);
  }

  function collect() {
    let totalGames=0,diff=0,big=0,reg=0,max=0,min=0;
    const points=[{x:0,y:0}];
    for (const row of rowsEl.querySelectorAll(".history-row")) {
      const input=row.querySelector(".game-input");
      if(input.value==="") continue;
      const games=Math.max(0,Number(input.value)||0);
      const type=row.querySelector(".bonus-select").value;
      totalGames+=games;
      diff-=games*COST_PER_GAME;
      points.push({x:totalGames,y:diff});
      min=Math.min(min,diff);max=Math.max(max,diff);
      if(type==="BIG"||type==="REG"){
        diff+=PAYOUT[type];
        points.push({x:totalGames,y:diff});
        if(type==="BIG")big++;else reg++;
        min=Math.min(min,diff);max=Math.max(max,diff);
      }
    }
    return {points,totalGames,diff,big,reg,max,min};
  }

  function niceStep(range){
    if(range<=0)return 100;
    const rough=range/6,power=Math.pow(10,Math.floor(Math.log10(rough))),n=rough/power;
    return (n<=1?1:n<=2?2:n<=5?5:10)*power;
  }

  function draw(data){
    const rect=canvas.getBoundingClientRect(),dpr=Math.max(1,window.devicePixelRatio||1);
    canvas.width=Math.round(rect.width*dpr);canvas.height=Math.round(rect.height*dpr);
    ctx.setTransform(dpr,0,0,dpr,0,0);
    const W=rect.width,H=rect.height,pad={l:50,r:12,t:16,b:30},plotW=W-pad.l-pad.r,plotH=H-pad.t-pad.b;
    ctx.clearRect(0,0,W,H);ctx.fillStyle="#0d1016";ctx.fillRect(0,0,W,H);
    const hasData=data.points.length>1;emptyState.style.display=hasData?"none":"grid";
    const xMax=Math.max(100,data.totalGames),ys=data.points.map(p=>p.y);
    let yMin=Math.min(0,...ys),yMax=Math.max(0,...ys);
    if(yMin===yMax){yMin-=500;yMax+=500}
    const step=niceStep(yMax-yMin);yMin=Math.floor(yMin/step)*step-step;yMax=Math.ceil(yMax/step)*step+step;
    const x=v=>pad.l+(v/xMax)*plotW,y=v=>pad.t+((yMax-v)/(yMax-yMin))*plotH;
    ctx.font="10px -apple-system,BlinkMacSystemFont,sans-serif";ctx.textBaseline="middle";
    ctx.strokeStyle="#232936";ctx.lineWidth=1;ctx.fillStyle="#747d8d";
    for(let val=Math.ceil(yMin/step)*step;val<=yMax+.001;val+=step){
      const py=y(val);ctx.beginPath();ctx.moveTo(pad.l,py);ctx.lineTo(W-pad.r,py);ctx.stroke();
      ctx.textAlign="right";ctx.fillText(fmt(val),pad.l-6,py);
    }
    if(yMin<=0&&yMax>=0){const zy=y(0);ctx.strokeStyle="#6a7280";ctx.lineWidth=1.4;ctx.beginPath();ctx.moveTo(pad.l,zy);ctx.lineTo(W-pad.r,zy);ctx.stroke()}
    ctx.fillStyle="#747d8d";ctx.textBaseline="top";
    for(let i=0;i<=4;i++){const val=Math.round((xMax/4)*i),px=x(val);ctx.textAlign=i===0?"left":i===4?"right":"center";ctx.fillText(val.toLocaleString("ja-JP")+"G",px,H-pad.b+8)}
    if(!hasData)return;
    const grad=ctx.createLinearGradient(0,pad.t,0,H-pad.b);grad.addColorStop(0,"#64f29b");grad.addColorStop(.52,"#52a9ff");grad.addColorStop(1,"#ff6376");
    ctx.strokeStyle=grad;ctx.lineWidth=2.6;ctx.lineJoin="round";ctx.lineCap="round";ctx.beginPath();
    data.points.forEach((p,i)=>{if(i===0)ctx.moveTo(x(p.x),y(p.y));else ctx.lineTo(x(p.x),y(p.y))});ctx.stroke();
    const last=data.points[data.points.length-1];ctx.fillStyle=last.y>=0?"#52e38b":"#ff6376";ctx.beginPath();ctx.arc(x(last.x),y(last.y),4,0,Math.PI*2);ctx.fill();
  }

  function update(){
    const data=collect();
    totalGamesEl.textContent=fmt(data.totalGames)+"G";bigCountEl.textContent=data.big;regCountEl.textContent=data.reg;
    currentDiffEl.textContent=(data.diff>0?"+":"")+fmt(data.diff)+"枚";
    currentDiffEl.classList.toggle("plus",data.diff>0);currentDiffEl.classList.toggle("minus",data.diff<0);
    maxPlusEl.textContent=(data.max>0?"+":"")+fmt(data.max)+"枚";maxMinusEl.textContent=fmt(data.min)+"枚";
    bigProbEl.textContent=formatProb(data.totalGames,data.big);regProbEl.textContent=formatProb(data.totalGames,data.reg);
    const setting=estimateSetting(data.totalGames,data.big,data.reg);
    estimatedSettingEl.textContent=setting?"推定設定 "+setting:"推定設定 —";
    draw(data);
  }

  makeRows();
  rowsEl.addEventListener("input",update);rowsEl.addEventListener("change",update);
  $("resetBtn").addEventListener("click",()=>{rowsEl.querySelectorAll(".game-input").forEach(el=>el.value="");rowsEl.querySelectorAll(".bonus-select").forEach(el=>el.value="");update();window.scrollTo({top:0,behavior:"smooth"})});
  let resizeTimer;window.addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(update,100)});
  update();
})();