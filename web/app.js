const form = document.querySelector('#prefs');
const cards = document.querySelector('#cards');
const message = document.querySelector('#message');
const inputs = ['budget', 'performance', 'weight'];
let lastResults = [];

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
  if (!results.length) {
    cards.innerHTML = '';
    message.hidden = false;
    message.textContent = query ? 'No recommendations match that search. Try another model name.' : 'No laptops meet all your must-have requirements. Try raising your budget or changing the filters.';
    return;
  }
  message.hidden = true;
  cards.innerHTML = results.map((item, index) => `<article class="laptop-card">
    <div class="card-top">${index === 0 && sort === 'match' ? '<span class="badge">Best match</span>' : '<span></span>'}<span class="match">${Math.round(item.score * 100)}% match</span></div>
    <div class="laptop-art">${laptopSvg(index)}</div><div class="card-body"><h3>${escapeHtml(item.name)}</h3>
    <div class="price">CHF ${Math.round(item.price).toLocaleString()}</div>
    <div class="specs"><div class="spec"><i>◉</i>${item.performance}/100 performance*</div><div class="spec"><i>◇</i>${item.weight.toFixed(2)} kg</div><div class="spec"><i>▣</i>${escapeHtml(item.os)}</div></div>
    <div class="explain">${scoreRow('Price',item.memberships.Price)}${scoreRow('Performance',item.memberships.Performance)}${scoreRow('Portability',item.memberships.Portability)}</div>
    <button class="details" type="button">View score details</button><div class="details-content">${Object.entries(item.contributions).map(([key,value]) => `${escapeHtml(key)} contributes ${Math.round(value * 100)} percentage points`).join('<br>')}<br><br>Match score reflects your preferences. Performance is an estimated CPU/spec index.</div></div></article>`).join('');
  document.querySelectorAll('.details').forEach(button => button.addEventListener('click', () => {
    const detail = button.nextElementSibling;
    detail.classList.toggle('open');
    button.textContent = detail.classList.contains('open') ? 'Hide score details' : 'View score details';
  }));
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
  };
  try {
    const response = await fetch('/interpret', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:requestText,defaults})});
    const result = await response.json();
    if (!response.ok) throw Error(result.error);
    for (const id of inputs) document.querySelector(`#${id}`).value = result.values[id];
    document.querySelector('#os').value = result.values.os;
    document.querySelector('#compatibility').value = result.values.compatibility === 'Any' ? '' : result.values.compatibility;
    showValues();
    const mapped = result.mapped.length ? result.mapped.map(escapeHtml).join('<br>') : 'No preference phrases recognized; current values are unchanged.';
    summary.hidden = false;
    summary.innerHTML = `<strong>Mapped to these preferences</strong>${mapped}<br><span class="parse-caveat">Review the values in Sliders. Shared weights remain unchanged.</span>`;
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
    os: document.querySelector('#os').value,
    compatibility: document.querySelector('#compatibility').value.trim() || 'Any',
  };
  const button = form.querySelector('.find-button');
  button.disabled = true;
  button.textContent = 'Finding your matches…';
  try {
    const response = await fetch('/recommend', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const body = await response.json();
    if (!response.ok) throw Error(body.error);
    lastResults = body.results;
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
fetch('/catalog-info').then(response => response.json()).then(info => {
  if (info.warnings?.length) {
    const notice = document.querySelector('#datasetNotice');
    notice.hidden = false;
    notice.textContent = `${info.warnings.length} malformed catalog row(s) were skipped. See the Terminal for details.`;
  }
  form.dispatchEvent(new Event('submit', {cancelable:true}));
}).catch(() => form.dispatchEvent(new Event('submit', {cancelable:true})));
