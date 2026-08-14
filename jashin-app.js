document.addEventListener("DOMContentLoaded", () => {
  const state = { koakuma: 0, big: 0, episode: 0 };
  const hints = {};
  const bonusRates = [253.1,248.1,241.6,222.5,211.8,210.0];
  const softHints = {
    char_minos:{odd:0.025}, char_medusa:{odd:0.050}, char_pekora:{even:0.025}, char_poporon:{even:0.050},
    char_yurine_a:{high:0.030}, char_yurine_b:{high:0.060}, at_minos:{odd:0.025}, at_medusa:{odd:0.050},
    at_pekora:{even:0.025}, at_poporon:{even:0.050}, at_yurine_a:{high:0.030}, at_yurine_b:{high:0.060}
  };
  const minimums = {char_akudakumi:2,char_swimsuit:4,char_pajamas:5,char_all:6,at_akudakumi:2,at_swimsuit:4,at_pajamas:5,at_all:6};
  function getValue(id){return Number(hints[id]||0)}
  function setValue(id,value){hints[id]=Math.max(0,value);const element=document.getElementById(`${id}-value`);if(element)element.textContent=hints[id]}
  document.querySelectorAll(".counter-btn").forEach(button=>{button.addEventListener("click",()=>{const target=button.dataset.target;if(!target)return;const amount=button.classList.contains("plus")?1:-1;if(Object.prototype.hasOwnProperty.call(state,target)){state[target]=Math.max(0,state[target]+amount);const element=document.getElementById(`${target}-value`);if(element)element.textContent=state[target];return}setValue(target,getValue(target)+amount)})});
  function getBonusTotal(){return state.koakuma+state.big+state.episode}
  function logFactorial(n){let result=0;for(let i=2;i<=n;i++)result+=Math.log(i);return result}
  function baseProbabilities(games,bonusCount){if(!games||bonusCount<=0)return[1,1,1,1,1,1];const logs=bonusRates.map(rate=>{const lambda=games/rate;return bonusCount*Math.log(lambda)-lambda-logFactorial(bonusCount)});const max=Math.max(...logs);return logs.map(value=>Math.exp(value-max))}
  function getTrophyMinimum(){const trophy=document.getElementById("trophy");if(!trophy)return 1;const values={none:1,copper:2,silver:3,gold:4,kumanomi:5,rainbow:6};return values[trophy.value]||1}
  function getMinimumSetting(){let minimum=getTrophyMinimum();for(const[id,setting]of Object.entries(minimums)){if(getValue(id)>0)minimum=Math.max(minimum,setting)}return minimum}
  function applySoftHints(probabilities){return probabilities.map((probability,index)=>{const setting=index+1;let multiplier=1;for(const[id,hint]of Object.entries(softHints)){const count=getValue(id);if(!count)continue;if(hint.odd&&setting%2===1)multiplier*=1+hint.odd*count;if(hint.even&&setting%2===0)multiplier*=1+hint.even*count;if(hint.high&&setting>=4)multiplier*=1+hint.high*count}return probability*multiplier})}
  function applyMinimum(probabilities,minimum){return probabilities.map((value,index)=>{const setting=index+1;return setting<minimum?0:value})}
  function normalize(values){const total=values.reduce((sum,value)=>sum+value,0);if(!total)return values.map(()=>0);return values.map(value=>value/total*100)}
  function updateGraph(probabilities){for(let setting=1;setting<=6;setting++){const percentage=probabilities[setting-1]||0;const text=document.getElementById(`setting-percent-${setting}`);const bar=document.getElementById(`setting-bar-${setting}`);if(text)text.textContent=`${Math.round(percentage)}%`;if(bar)bar.style.width=`${Math.max(0,Math.min(100,percentage))}%`}}
  function updatePrediction(probabilities){const max=Math.max(...probabilities);const element=document.getElementById("prediction-text");if(!element)return;if(!max){element.textContent="設定予測：判定材料不足";return}const candidates=probabilities.map((value,index)=>({value,setting:index+1})).filter(item=>Math.abs(item.value-max)<0.5).map(item=>item.setting);if(candidates.length===1)element.textContent=`設定予測：設定${candidates[0]}が最有力`;else element.textContent=`設定予測：設定${candidates[0]}～${candidates[candidates.length-1]}が候補`}
  function judge(){const games=Number(document.getElementById("games")?.value||0);if(!games||games<=0){alert("総ゲーム数を入力してください。");document.getElementById("games")?.focus();return}const bonusCount=getBonusTotal();let probabilities=baseProbabilities(games,bonusCount);probabilities=applySoftHints(probabilities);probabilities=applyMinimum(probabilities,getMinimumSetting());probabilities=normalize(probabilities);updateGraph(probabilities);updatePrediction(probabilities);const result=document.getElementById("result-section");if(result){result.classList.add("visible");setTimeout(()=>{result.scrollIntoView({behavior:"smooth",block:"start"})},80)}}
  function reset(){state.koakuma=0;state.big=0;state.episode=0;["koakuma","big","episode"].forEach(id=>{const element=document.getElementById(`${id}-value`);if(element)element.textContent="0"});Object.keys(hints).forEach(id=>delete hints[id]);document.querySelectorAll(".counter span[id$='-value']").forEach(element=>{element.textContent="0"});const games=document.getElementById("games");if(games)games.value="";const trophy=document.getElementById("trophy");if(trophy)trophy.value="none";for(let setting=1;setting<=6;setting++){const text=document.getElementById(`setting-percent-${setting}`);const bar=document.getElementById(`setting-bar-${setting}`);if(text)text.textContent="0%";if(bar)bar.style.width="0%"}const prediction=document.getElementById("prediction-text");if(prediction)prediction.textContent="-";document.getElementById("result-section")?.classList.remove("visible")}
  document.getElementById("judge-btn")?.addEventListener("click",judge);
  document.getElementById("reset-btn")?.addEventListener("click",reset);
});
