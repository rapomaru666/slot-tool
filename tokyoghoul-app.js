document.addEventListener("DOMContentLoaded", () => {

  const state = {
    reminiscence: 0,
    rize: 0,
    at: 0,
    episode: 0,
    direct: 0,
    lowerReplay: 0,
    within100Trials: 0,
    within100Hits: 0,
    pullbackTrials: 0,
    pullbackHits: 0,
    uraTrials: 0,
    uraHits: 0
  };

  const rates = {
    at: [394.4, 380.5, 357.0, 325.9, 291.2, 261.3],
    reminiscence: [300.5, 295.1, 287.6, 276.7, 262.7, 251.2],
    rize: [2079.1, 1906.5, 1722.8, 1478.9, 1226.6, 1074.9],
    episode: [6620.2, 5879.7, 5114.5, 4062.5, 3166.7, 2639.5],
    direct: [28460.6, 24453.5, 18093.0, 12019.5, 8615.4, 7036.8],
    lowerReplay: [1260.3, 1213.6, 1170.3, 1129.9, 1092.3, 1024.0]
  };

  const percentages = {
    within100: [0.1958, 0.2104, 0.2315, 0.2637, 0.3196, 0.3601],
    pullback: [0.0781, 0.0781, 0.0938, 0.1094, 0.1250, 0.1523],
    ura: [0.0110, 0.0132, 0.0163, 0.0219, 0.0285, 0.0332]
  };

  function getValue(id) {
    return state[id] || 0;
  }

  function setValue(id, value) {
    state[id] = Math.max(0, value);
    const element = document.getElementById(`${id}-value`);
    if (element) element.textContent = state[id];
  }

  document.querySelectorAll(".counter-btn").forEach(button => {
    button.addEventListener("click", () => {
      const target = button.dataset.target;
      if (!target) return;
      const amount = button.classList.contains("plus") ? 1 : -1;
      setValue(target, getValue(target) + amount);
    });
  });

  function logFactorial(n) {
    let result = 0;
    for (let i = 2; i <= n; i++) result += Math.log(i);
    return result;
  }

  function poissonLogLikelihood(games, count, rate) {
    if (!games || count < 0) return 0;
    const lambda = games / rate;
    if (lambda <= 0) return 0;
    if (count === 0) return -lambda;
    return count * Math.log(lambda) - lambda - logFactorial(count);
  }

  function binomialLogLikelihood(trials, hits, probability) {
    if (trials <= 0) return 0;
    const safeHits = Math.max(0, Math.min(hits, trials));
    const miss = trials - safeHits;
    const p = Math.max(0.000001, Math.min(0.999999, probability));
    return safeHits * Math.log(p) + miss * Math.log(1 - p);
  }

  function calculateProbabilities() {
    const games = Number(document.getElementById("games")?.value || 0);
    const logs = [];

    for (let setting = 0; setting < 6; setting++) {
      let score = 0;
      score += poissonLogLikelihood(games, getValue("at"), rates.at[setting]);
      score += poissonLogLikelihood(games, getValue("reminiscence"), rates.reminiscence[setting]);
      score += poissonLogLikelihood(games, getValue("rize"), rates.rize[setting]);
      score += poissonLogLikelihood(games, getValue("episode"), rates.episode[setting]);
      score += poissonLogLikelihood(games, getValue("direct"), rates.direct[setting]);
      score += poissonLogLikelihood(games, getValue("lowerReplay"), rates.lowerReplay[setting]);
      score += binomialLogLikelihood(getValue("within100Trials"), getValue("within100Hits"), percentages.within100[setting]);
      score += binomialLogLikelihood(getValue("pullbackTrials"), getValue("pullbackHits"), percentages.pullback[setting]);
      score += binomialLogLikelihood(getValue("uraTrials"), getValue("uraHits"), percentages.ura[setting]);
      logs.push(score);
    }

    const maxLog = Math.max(...logs);
    const weights = logs.map(value => Math.exp(value - maxLog));
    const total = weights.reduce((sum, value) => sum + value, 0);
    if (!total) return weights.map(() => 0);
    return weights.map(value => value / total * 100);
  }

  function updateGraph(probabilities) {
    for (let setting = 1; setting <= 6; setting++) {
      const percentage = probabilities[setting - 1] || 0;
      const text = document.getElementById(`setting-percent-${setting}`);
      const bar = document.getElementById(`setting-bar-${setting}`);
      if (text) text.textContent = `${Math.round(percentage)}%`;
      if (bar) bar.style.width = `${Math.max(0, Math.min(100, percentage))}%`;
    }
  }

  function updatePrediction(probabilities) {
    const element = document.getElementById("prediction-text");
    if (!element) return;
    const max = Math.max(...probabilities);
    if (!max || !Number.isFinite(max)) {
      element.textContent = "設定予測：判定材料不足";
      return;
    }
    const candidates = probabilities.map((value, index) => ({ value, setting: index + 1 })).filter(item => Math.abs(item.value - max) < 0.5);
    if (candidates.length === 1) {
      element.textContent = `設定予測：設定${candidates[0].setting}が最有力`;
    } else {
      const first = candidates[0].setting;
      const last = candidates[candidates.length - 1].setting;
      element.textContent = `設定予測：設定${first}～${last}が候補`;
    }
  }

  function judge() {
    const games = Number(document.getElementById("games")?.value || 0);
    if (!games || games <= 0) {
      alert("総ゲーム数を入力してください。");
      document.getElementById("games")?.focus();
      return;
    }
    const probabilities = calculateProbabilities();
    updateGraph(probabilities);
    updatePrediction(probabilities);
    const result = document.getElementById("result-section");
    if (result) {
      result.classList.add("visible");
      setTimeout(() => result.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    }
  }

  function reset() {
    Object.keys(state).forEach(id => {
      state[id] = 0;
      const element = document.getElementById(`${id}-value`);
      if (element) element.textContent = "0";
    });

    const games = document.getElementById("games");
    if (games) games.value = "";

    for (let setting = 1; setting <= 6; setting++) {
      const text = document.getElementById(`setting-percent-${setting}`);
      const bar = document.getElementById(`setting-bar-${setting}`);
      if (text) text.textContent = "0%";
      if (bar) bar.style.width = "0%";
    }

    const prediction = document.getElementById("prediction-text");
    if (prediction) prediction.textContent = "-";
    document.getElementById("result-section")?.classList.remove("visible");
  }

  document.getElementById("judge-btn")?.addEventListener("click", judge);
  document.getElementById("reset-btn")?.addEventListener("click", reset);
});
