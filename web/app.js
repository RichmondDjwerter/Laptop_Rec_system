const form = document.querySelector('#prefs');
const cards = document.querySelector('#cards');
const message = document.querySelector('#message');
const inputs = ['budget', 'performance', 'weight'];
let lastResults = [];
let showAll = false;
let compareNames = [];
let appliedWeights = {Price:4, Performance:4, Portability:3, 'Battery size':1};

function comparisonRow(label, a, b, formatter) {
  return `<div class="comparison-line"><span>${label}</span><strong>${formatter(a)}</strong><strong>${formatter(b)}</strong></div>`;
}

function renderComparison() {
  const tray = document.querySelector('#compareTray');
  const chosen = compareNames.map(name => lastResults.find(item => item.name === name)).filter(Boolean);
  if (chosen.length !== 2) { tray.hidden = true; tray.innerHTML = ''; return; }
  const [a, b] = chosen;
  tray.hidden = false;
  const cost = Math.round(b.price - a.price);
  const perf = b.performance - a.performance;
  const weight = b.weight - a.weight;
  const explanation = `${escapeHtml(b.name)} costs CHF ${Math.abs(cost).toLocaleString()} ${cost >= 0 ? 'more' : 'less'}, ` +
    `has ${Math.abs(perf).toFixed(0)} ${perf >= 0 ? 'more' : 'fewer'} illustrative performance points, and weighs ${Math.abs(weight).toFixed(2)} kg ${weight >= 0 ? 'more' : 'less'}.`;
  tray.innerHTML = `<div class="compare-heading"><strong>Compare your choices</strong><button type="button" id="clearCompare" class="clear-compare">Clear</button></div>
    <div class="comparison-line comparison-names"><span>Feature</span><strong>${escapeHtml(a.name)}</strong><strong>${escapeHtml(b.name)}</strong></div>
    ${comparisonRow('Price', a.price, b.price, x => `CHF ${Math.round(x).toLocaleString()}`)}
    ${comparisonRow('Performance*', a.performance, b.performance, x => `${x.toFixed(0)} / 100`)}
    ${comparisonRow('Weight', a.weight, b.weight, x => `${x.toFixed(2)} kg`)}
    ${comparisonRow('RAM', a.ram, b.ram, x => `${x} GB`)}
    ${comparisonRow('Battery size', a.batteryWh, b.batteryWh, x => `${x} Wh`)}
    ${comparisonRow('Preference fit', a.score, b.score, x => `${Math.round(x*100)} / 100`)}
    <p class="compare-explanation">${explanation}</p><p class="compare-note">*Performance is an illustrative relative index, not measured speed. Battery capacity is not runtime.</p>`;
  document.querySelector('#clearCompare').addEventListener('click', () => {compareNames=[]; draw(lastResults);});
}


function showValues() {
  const labels = {
    budget: Number(document.querySelector('#budget').value).toLocaleString(),
    performance: `${document.querySelector('#performance').value} / 100`,
    weight: `${Number(document.querySelector('#weight').value).toFixed(1)} kg max`,
  };
  for (const [id, value] of Object.entries(labels)) document.querySelector(`#${id}Out`).textContent = value;
  for (const id of inputs) {
    const el = document.querySelector(`#${id}`);
    const percent = (el.value - el.min) / (el.max - el.min) * 100;
    el.style.background = `linear-gradient(90deg,#55aeea ${percent}%,#e6edf1 ${percent}%)`;
  }
}
inputs.forEach(id => document.querySelector(`#${id}`).addEventListener('input', showValues));
showValues();

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}
function laptopSvg(index) {
  const colors = [['#53b7ef','#a7e1ff'],['#347cc5','#daeeff'],['#ee9a52','#f7d587'],['#5556b5','#c8c6fa']][index % 4];
  return `<svg viewBox="0 0 180 105" aria-hidden="true"><defs><linearGradient id="g${index}" x2="1" y2="1"><stop stop-color="${colors[0]}"/><stop offset="1" stop-color="${colors[1]}"/></linearGradient></defs><path d="M39 15 Q39 10 45 10h91q6 0 6 6v59H39z" fill="#303d47"/><path d="M44 16h92v53H44z" fill="url(#g${index})"/><path d="M34 76h112l13 10q2 3-4 4H27q-6-1-3-4z" fill="#b7c4cc"/><path d="M71 78h40l5 6H66z" fill="#8c9ba4"/></svg>`;
}
function scoreRow(label, value) {
  const percent = Math.round(value * 100);
  const level = percent >= 70 ? '' : percent >= 40 ? 'mid' : 'low';
  return `<div class="explain-row"><span>${label}</span><div class="track"><div class="fill ${level}" style="width:${percent}%"></div></div><strong>${percent}%</strong></div>`;
}
function draw(results) {
  const query = document.querySelector('#search').value.trim().toLowerCase();
  const sort = document.querySelector('#sort').value;
  results = results.filter(item => item.name.toLowerCase().includes(query));
  if (sort === 'price') results.sort((a,b) => a.price - b.price);
  if (sort === 'weight') results.sort((a,b) => a.weight - b.weight);
  document.querySelector('#resultCount').textContent = `${results.length} match${results.length === 1 ? '' : 'es'} in the catalog`;
  const showMoreButton = document.querySelector('#showMore');
  showMoreButton.hidden = Boolean(query) || results.length <= 8;
  showMoreButton.textContent = showAll ? 'Show fewer laptops' : `Show all ${results.length} laptops`;
  const visible = (showAll || query) ? results : results.slice(0, 8);
  if (!results.length) {
    cards.innerHTML = '';
    document.querySelector('#compareTray').hidden = true;
    message.hidden = false;
    message.textContent = query ? 'No recommendations match that search. Try another model name.' : 'No laptops meet all your must-have requirements. Try raising your budget or changing the filters.';
    return;
  }
  const strongestFit = Math.max(...results.map(item => item.score));
  message.hidden = strongestFit >= 0.45;
  if (!message.hidden) message.textContent = 'No strong fit found for these preferences. The options below involve compromises; try adjusting the budget or priorities.';
  cards.innerHTML = visible.map((item, index) => `<article class="laptop-card">
    <div class="card-top">${index === 0 && sort === 'match' ? '<span class="badge">Best match</span>' : '<span></span>'}<span class="match">${Math.round(item.score * 100)} / 100 fit</span></div>
    <div class="laptop-art">${laptopSvg(index)}</div><div class="card-body"><h3>${escapeHtml(item.name)}</h3>
    <div class="price">CHF ${Math.round(item.price).toLocaleString()}</div>
    <div class="specs"><div class="spec"><i>◉</i>${item.performance.toFixed(0)}/100 performance*</div><div class="spec"><i>◇</i>${item.weight.toFixed(2)} kg</div><div class="spec"><i>▣</i>${escapeHtml(item.os)}</div><div class="spec"><i>▤</i>${item.ram || '—'} GB RAM</div></div>
    <div class="explain">${Object.entries(item.memberships).filter(([key]) => (appliedWeights[key] || 0) > 0).map(([key,value]) => scoreRow(key,value)).join('')}</div>
    <button class="details" type="button" aria-expanded="false">Why this laptop?</button><div class="details-content"><strong>${escapeHtml(item.explanation || '')}</strong>${item.warnings?.length ? `<div class="caution-text">${item.warnings.map(escapeHtml).join('<br>')}</div>` : ''}<br>${Object.entries(item.contributions).filter(([key]) => (appliedWeights[key] || 0) > 0).map(([key,value]) => `${escapeHtml(key)}: +${(value * 100).toFixed(1)} points`).join('<br>')}<br>Weighted score: ${(item.baseScore*100).toFixed(1)} / 100${item.budgetFactor < 0.999 ? `<br>Large price-overrun adjustment: ×${item.budgetFactor.toFixed(2)}.` : ''}${item.gpuFactor < 0.999 ? `<br>Gaming GPU rule: ×${item.gpuFactor.toFixed(2)} (fuzzy IF–THEN caution).` : ''}<br><b>Final fit: ${(item.score*100).toFixed(1)} / 100</b><br><br><b>Hardware:</b> ${escapeHtml(item.cpu || 'Unknown CPU')} · ${escapeHtml(item.gpu || 'Unknown GPU')} · ${item.ram || '—'} GB RAM · ${item.storage || '—'} GB SSD.<br><b>Battery size:</b> ${item.batteryWh ? item.batteryWh + ' Wh' : 'unknown'} (capacity, not runtime).<br><br>Suitability is not a probability. Prices and performance are illustrative estimates.</div>
    <button class="compare-pick" type="button" data-name="${escapeHtml(item.name)}" aria-pressed="${compareNames.includes(item.name)}">${compareNames.includes(item.name) ? 'Selected for comparison ✓' : 'Compare'}</button></div></article>`).join('');
  document.querySelectorAll('.details').forEach(button => button.addEventListener('click', () => {
    const detail = button.nextElementSibling;
    detail.classList.toggle('open');
    const opened = detail.classList.contains('open');
    button.textContent = opened ? 'Hide explanation' : 'Why this laptop?';
    button.setAttribute('aria-expanded', String(opened));
  }));
  document.querySelectorAll('.compare-pick').forEach(button => button.addEventListener('click', () => {
    const name = button.dataset.name;
    compareNames = compareNames.includes(name)
      ? compareNames.filter(x => x !== name)
      : (compareNames.length >= 2 ? [compareNames[0], name] : [...compareNames, name]);
    draw(lastResults);
  }));
  renderComparison();
}

function setMode(mode) {
  const textMode = mode === 'text';
  document.querySelector('#sliderMode').hidden = textMode;
  document.querySelector('#textMode').hidden = !textMode;
  document.querySelectorAll('.mode-tab').forEach(tab => {
    const active = tab.dataset.mode === mode;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
  });
}
document.querySelectorAll('.mode-tab').forEach(tab => tab.addEventListener('click', () => setMode(tab.dataset.mode)));

document.querySelector('#interpretButton').addEventListener('click', async () => {
  const requestText = document.querySelector('#requestText').value.trim();
  const summary = document.querySelector('#interpretSummary');
  const button = document.querySelector('#interpretButton');
  if (!requestText) {
    summary.hidden = false;
    summary.innerHTML = '<strong>Describe your ideal laptop in a sentence.</strong>Try: “A relatively cheap, fast MacBook for everyday work.”';
    return;
  }
  button.disabled = true;
  button.textContent = 'Translating your request…';
  const defaults = {
    budget: document.querySelector('#budget').value,
    performance: document.querySelector('#performance').value,
    weight: document.querySelector('#weight').value,
    os: document.querySelector('#os').value,
    compatibility: document.querySelector('#compatibility').value || 'Any',
    strict_budget: document.querySelector('#strictBudget').checked,
    workload: document.querySelector('#workload').value,
    battery_weight: Number(form.elements['batteryWeight'].value),
    portability_weight: Number(form.elements['portabilityWeight'].value),
  };
  try {
    const response = await fetch('/interpret', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:requestText,defaults})});
    const result = await response.json();
    if (!response.ok) throw Error(result.error);
    for (const id of inputs) document.querySelector(`#${id}`).value = result.values[id];
    document.querySelector('#os').value = result.values.os;
    document.querySelector('#compatibility').value = result.values.compatibility || 'Any';
    document.querySelector('#strictBudget').checked = result.values.strict_budget;
    document.querySelector('#workload').value = result.values.workload || 'general';
    form.elements['batteryWeight'].value = String(result.values.battery_weight ?? 1);
    form.elements['portabilityWeight'].value = String(result.values.portability_weight ?? 3);
    showValues();
    const mapped = result.mapped.length ? result.mapped.map(escapeHtml).join('<br>') : 'No preference phrases recognized; current values are unchanged.';
    summary.hidden = false;
    summary.innerHTML = `<strong>Mapped to these preferences</strong>${mapped}<br><span class="parse-caveat">Review the interpreted preferences; you can edit them.</span>`;
    form.dispatchEvent(new Event('submit', {cancelable:true}));
  } catch (error) {
    summary.hidden = false;
    summary.innerHTML = `<strong>Could not interpret that request</strong>${escapeHtml(error.message)}`;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Translate my request <span>↗</span>';
  }
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const data = new FormData(form);
  const payload = {
    budget: document.querySelector('#budget').value,
    performance: document.querySelector('#performance').value,
    weight: document.querySelector('#weight').value,
    priceWeight: data.get('priceWeight'),
    performanceWeight: data.get('performanceWeight'),
    portabilityWeight: data.get('portabilityWeight'),
    batteryWeight: data.get('batteryWeight'),
    workload: document.querySelector('#workload').value,
    os: document.querySelector('#os').value,
    compatibility: document.querySelector('#compatibility').value.trim() || 'Any',
    strictBudget: document.querySelector('#strictBudget').checked,
  };
  const button = form.querySelector('.find-button');
  button.disabled = true;
  button.textContent = 'Finding your matches…';
  try {
    const response = await fetch('/recommend', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const body = await response.json();
    if (!response.ok) throw Error(body.error);
    lastResults = body.results;
    showAll = false;
    compareNames = [];
    appliedWeights = {
      Price: Number(payload.priceWeight),
      Performance: Number(payload.performanceWeight),
      Portability: Number(payload.portabilityWeight),
      'Battery size': Number(payload.batteryWeight),
    };
    draw(lastResults);
  } catch (error) {
    message.hidden = false;
    message.textContent = `Could not load recommendations: ${error.message}`;
  } finally {
    button.disabled = false;
    button.innerHTML = '<span>✦</span> Find recommendations <span class="arrow">→</span>';
  }
});
document.querySelector('#search').addEventListener('input', () => draw(lastResults));
document.querySelector('#sort').addEventListener('change', () => draw(lastResults));
document.querySelector('#showMore').addEventListener('click', () => {
  showAll = !showAll;
  draw(lastResults);
});
fetch('/catalog-info').then(response => response.json()).then(info => {
  if (info.warnings?.length) {
    const notice = document.querySelector('#datasetNotice');
    notice.hidden = false;
    notice.textContent = `${info.warnings.length} malformed catalog row(s) were skipped. See the Terminal for details.`;
  }
  form.dispatchEvent(new Event('submit', {cancelable:true}));
}).catch(() => form.dispatchEvent(new Event('submit', {cancelable:true})));
