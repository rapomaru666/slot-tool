document.addEventListener("DOMContentLoaded", () => {
  const state = { koakuma: 0, big: 0, episode: 0, jt: 0 };
  const rates = {
    bonus: [253.1, 248.1, 241.6, 222.5, 211.8, 210.0],
    jt: [758.2, 746.3, 722.8, 655.9, 615.9, 606.2]
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
    return count === 0
      ? -lambda
      : count * Math.log(lambda) - lambda - logFactorial(count);
  }

  function calculateProbabilities(games) {
    const bonusCount = getValue("koakuma") + getValue("big") + getValue("episode");
    const jtCount = getValue("jt");
    const logs = [];

    for (let setting = 0; setting < 6; setting++) {
      let score = 0;
      score += poissonLogLikelihood(games, bonusCount, rates.bonus[setting]);
      score += poissonLogLikelihood(games, jtCount, rates.jt[setting]);
      logs.push(score);
    }

    const maxLog = Math.max(...logs);
    const weights = logs.map(value => Math.exp(value - maxLog));
    const total = weights.reduce((sum, value) => sum + value, 0);
    return total ? weights.map(value => value / total * 100) : weights.map(() => 0);
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
    const best = probabilities.indexOf(max) + 1;
    element.textContent = `設定予測：設定${best}が最有力`;
  }

  function judge() {
    const currentGames = Number(document.getElementById("games")?.value || 0);
    const startGames = Number(document.getElementById("start-games")?.value || 0);

    if (currentGames < 0 || startGames < 0) {
      alert("ゲーム数は0以上で入力してください。");
      return;
    }
    if (currentGames < startGames) {
      alert("総ゲーム数は開始ゲーム数以上にしてください。");
      return;
    }

    const effectiveGames = currentGames - startGames;
    if (effectiveGames <= 0) {
      alert("総ゲーム数と開始ゲーム数の差が0Gです。実戦ゲーム数を入力してください。");
      return;
    }

    const bonusCount = getValue("koakuma") + getValue("big") + getValue("episode");
    const jtCount = getValue("jt");
    if (bonusCount === 0 && jtCount === 0) {
      alert("BONUSまたはJTの初当り回数を入力してください。");
      return;
    }

    const probabilities = calculateProbabilities(effectiveGames);
    updateGraph(probabilities);
    updatePrediction(probabilities);

    const result = document.getElementById("result-section");
    if (result) {
      result.classList.add("visible");
      setTimeout(() => result.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    }
  }

  function reset() {
    Object.keys(state).forEach(id => setValue(id, 0));
    const games = document.getElementById("games");
    const startGames = document.getElementById("start-games");
    if (games) games.value = "";
    if (startGames) startGames.value = "";

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
