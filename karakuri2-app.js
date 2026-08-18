document.addEventListener("DOMContentLoaded",()=>{
  const state={at:0,cz:0,strongCherry:0,strongCherryHit:0,stageMasaru:0,stageNarumi:0};
  const rates={
    at:[519,504,474,458,430,410],
    cz:[342,341,339,339,327,318],
    strongCherry:[0.098,0.102,0.125,0.137,0.148,0.164]
  };
  const $=id=>document.getElementById(id);
  let totalMode=true;

  function setCounter(id,value){
    state[id]=Math.max(0,Number(value)||0);
    const el=$(`${id}-value`);
    if(el)el.textContent=state[id];
  }

  function updateModeUI(){
    const toggle=$("game-mode");
    const label=$("mode-label");
    const start=$("start-games");
    if(toggle){
      toggle.classList.toggle("on",totalMode);
      toggle.setAttribute("aria-pressed",String(totalMode));
    }
    if(label)label.textContent=totalMode?"ON":"OFF";
    if(start)start.disabled=totalMode;
  }

  function targetGames(){
    const total=Number($("games")?.value||0);
    const start=Number($("start-games")?.value||0);
    return totalMode?total:Math.max(0,total-start);
  }

  document.querySelectorAll(".counter-btn").forEach(btn=>{
    btn.addEventListener("click",()=>{
      const id=btn.dataset.target;
      if(!Object.prototype.hasOwnProperty.call(state,id))return;
      setCounter(id,state[id]+(btn.classList.contains("plus")?1:-1));
    });
  });

  $("game-mode")?.addEventListener("click",()=>{
    totalMode=!totalMode;
    updateModeUI();
  });

  document.querySelectorAll("button.signal").forEach(btn=>{
    btn.addEventListener("click",()=>btn.classList.toggle("selected"));
  });

  function logFactorial(n){let v=0;for(let i=2;i<=n;i++)v+=Math.log(i);return v;}
  function poissonLog(games,count,rate){if(games<=0||!rate)return 0;const lambda=games/rate;return count===0?-lambda:count*Math.log(lambda)-lambda-logFactorial(count);}
  function binomialLog(n,k,p){if(n<=0)return 0;if(k<0||k>n||p<=0||p>=1)return -Infinity;const logComb=logFactorial(n)-logFactorial(k)-logFactorial(n-k);return logComb+k*Math.log(p)+(n-k)*Math.log(1-p);}

  function allowedSettings(){
    let allowed=new Set([1,2,3,4,5,6]);
    document.querySelectorAll("button.signal.selected").forEach(btn=>{
      if(btn.dataset.min){const min=Number(btn.dataset.min);allowed=new Set([...allowed].filter(s=>s>=min));}
      if(btn.dataset.only){const only=new Set(btn.dataset.only.split(",").map(Number));allowed=new Set([...allowed].filter(s=>only.has(s)));}
      if(btn.dataset.exclude)allowed.delete(Number(btn.dataset.exclude));
    });
    return allowed;
  }

  function softSignals(){
    return [...document.querySelectorAll("button.signal.selected[data-soft]")]
      .map(btn=>btn.dataset.soft)
      .filter((v,i,a)=>a.indexOf(v)===i);
  }

  function probabilities(games){
    const allowed=allowedSettings();
    const logs=[];
    for(let i=0;i<6;i++){
      const setting=i+1;
      if(!allowed.has(setting)){logs.push(-Infinity);continue;}
      let log=0;
      log+=poissonLog(games,state.at,rates.at[i]);
      log+=poissonLog(games,state.cz,rates.cz[i]);
      if(state.strongCherry>0)log+=binomialLog(state.strongCherry,state.strongCherryHit,rates.strongCherry[i]);
      logs.push(log);
    }
    const finite=logs.filter(Number.isFinite);
    if(!finite.length)return [0,0,0,0,0,0];
    const max=Math.max(...finite);
    const weights=logs.map(v=>Number.isFinite(v)?Math.exp(v-max):0);
    const total=weights.reduce((a,b)=>a+b,0);
    return total?weights.map(v=>v/total*100):[0,0,0,0,0,0];
  }

  function render(p,games){
    for(let s=1;s<=6;s++){
      const v=p[s-1]||0;
      const pct=$(`setting-percent-${s}`),bar=$(`setting-bar-${s}`);
      if(pct)pct.textContent=`${Math.round(v)}%`;
      if(bar)bar.style.width=`${Math.min(100,Math.max(0,v))}%`;
    }
    const max=Math.max(...p),pred=$("prediction-text");
    if(!max)pred.textContent="設定予測：入力した示唆条件が矛盾しています";
    else pred.textContent=`設定予測：設定${p.indexOf(max)+1}が最有力　（判別対象 ${games}G）`;

    const parts=[];
    const signals=softSignals();
    if(signals.length)parts.push(`参考示唆：${signals.join(" / ")}`);
    const stageTotal=state.stageMasaru+state.stageNarumi;
    if(stageTotal>0){
      const masaruPct=Math.round(state.stageMasaru/stageTotal*100);
      const narumiPct=100-masaruPct;
      parts.push(`AT開始ステージ：勝 ${state.stageMasaru}回（${masaruPct}%） / 鳴海 ${state.stageNarumi}回（${narumiPct}%）`);
    }
    const summary=$("signal-summary");
    if(summary)summary.textContent=parts.length?`${parts.join("　｜　")} ※設定別選択率未公表の示唆は数値％へ加算していません。`:"";
  }

  $("judge-btn")?.addEventListener("click",()=>{
    const total=Number($("games")?.value||0),start=Number($("start-games")?.value||0),games=targetGames();
    if(total<=0){alert("総ゲーム数を入力してください。");$("games")?.focus();return;}
    if(!totalMode&&start>=total){alert("開始ゲーム数は総ゲーム数より小さい値を入力してください。");$("start-games")?.focus();return;}
    if(games<=0){alert("判別対象ゲーム数が0Gです。");return;}
    if(state.strongCherryHit>state.strongCherry){alert("強チェリー当選回数が強チェリー回数を超えています。");return;}
    render(probabilities(games),games);
    $("result-section")?.classList.add("visible");
    $("result-section")?.scrollIntoView({behavior:"smooth",block:"start"});
  });

  $("reset-btn")?.addEventListener("click",()=>{
    Object.keys(state).forEach(id=>setCounter(id,0));
    if($("games"))$("games").value="";
    if($("start-games"))$("start-games").value="";
    totalMode=true;updateModeUI();
    document.querySelectorAll("button.signal.selected").forEach(btn=>btn.classList.remove("selected"));
    for(let s=1;s<=6;s++){
      const pct=$(`setting-percent-${s}`),bar=$(`setting-bar-${s}`);
      if(pct)pct.textContent="0%";
      if(bar)bar.style.width="0%";
    }
    if($("prediction-text"))$("prediction-text").textContent="-";
    if($("signal-summary"))$("signal-summary").textContent="";
    $("result-section")?.classList.remove("visible");
  });

  updateModeUI();
});
