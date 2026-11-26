/* edition_sketch.js (2026-11-25) — sketch only. Data for Mid-Atlantic · Confederation is written here
   (taken from viz/data/receipts.js and viz/data/bread_v2.js). The real build will read those files. */
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const $ = id => document.getElementById(id);

  // ---------- style switch ----------
  const params = new URLSearchParams(location.search);
  let style = params.get('style') === 'old' ? 'old' : 'new';
  function setStyle(s) {
    style = s;
    document.body.className = 'style-' + s;
    document.querySelectorAll('.switch button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.style === s)));
    drawLoaves();
  }
  document.querySelectorAll('.switch button').forEach(b => b.addEventListener('click', () => setStyle(b.dataset.style)));

  // ---------- edition chooser in the dateline (only editions that have data) ----------
  const AV = {
    'New England': ['1790s', '1800–1810'],
    'Mid-Atlantic': ['Colonial', 'War', 'Confederation', '1790s', '1800–1810'],
    'South': ['War', '1800–1810'],
    'Britain': ['Confederation', '1790s', '1800–1810'],
  };
  const YR = { 'Colonial': '1770–1775', 'War': '1776–1783', 'Confederation': '1784–1789', '1790s': '1790–1799', '1800–1810': '1800–1810' };
  const PORTS = { 'New England': 'Boston and Portland', 'Mid-Atlantic': 'New York and Philadelphia', 'South': 'Alexandria and Charleston', 'Britain': 'Liverpool and London' };
  let selR = 'Mid-Atlantic', selP = 'Confederation';
  function showOpts(kind) {
    const o = $('opts'); o.innerHTML = '';
    const list = kind === 'R' ? Object.keys(AV) : AV[selR];
    list.forEach(x => {
      const s = document.createElement('span');
      s.textContent = x;
      if ((kind === 'R' ? selR : selP) === x) s.className = 'on';
      s.onclick = () => {
        if (kind === 'R') { selR = x; if (!AV[x].includes(selP)) selP = AV[x][AV[x].length - 1]; } else selP = x;
        o.innerHTML = ''; updateEdition();
      };
      o.appendChild(s);
    });
  }
  $('dR').onclick = () => showOpts('R');
  $('dP').onclick = () => showOpts('P');
  function updateEdition() {
    $('dR').textContent = selR; $('dP').textContent = selP; $('dY').textContent = YR[selP]; $('m-yrs').textContent = YR[selP];
    $('cap').textContent = 'Main ports: ' + PORTS[selR] +
      (selR === 'Mid-Atlantic' && selP === 'Confederation' ? '' : ' (sketch: the page below stays on Mid-Atlantic · Confederation)');
    if (window.d3) {
      d3.selectAll('#map .reg').style('fill', function () { return this.dataset.r === selR ? 'url(#hr)' : 'var(--paper)'; });
      d3.selectAll('#map .rl').style('fill', function () { return this.dataset.r === selR ? 'var(--red)' : 'currentColor'; });
    }
  }

  // ---------- engraved map ----------
  const G = { '09': 'New England', '23': 'New England', '25': 'New England', '33': 'New England', '44': 'New England', '50': 'New England',
    '34': 'Mid-Atlantic', '36': 'Mid-Atlantic', '42': 'Mid-Atlantic', '10': 'Mid-Atlantic', '24': 'Mid-Atlantic', '11': 'Mid-Atlantic',
    '51': 'South', '54': 'South', '37': 'South', '45': 'South', '13': 'South', '21': 'South', '47': 'South', '28': 'South', '01': 'South' };
  if (window.d3 && window.topojson) {
    Promise.all([
      d3.json('https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json'),
      d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json'),
    ]).then(([us, w]) => {
      const svg = d3.select('#map');
      const frame = { type: 'MultiPoint', coordinates: [[-92, 24.5], [-64, 24.5], [-92, 47.5], [-64, 47.5]] };
      const pr = d3.geoConicConformal().parallels([30, 45]).rotate([80, 0]).fitExtent([[0, 0], [640, 440]], frame);
      const pa = d3.geoPath(pr);
      const st = topojson.feature(us, us.objects.states).features;
      const cs = topojson.feature(w, w.objects.countries).features;
      const defs = svg.append('defs');
      const p = defs.append('pattern').attr('id', 'hr').attr('width', 7).attr('height', 7).attr('patternUnits', 'userSpaceOnUse').attr('patternTransform', 'rotate(45)');
      p.append('rect').attr('width', 7).attr('height', 7).style('fill', 'var(--paper)');
      p.append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 7).style('stroke', 'var(--red)').attr('stroke-width', 2.6);
      defs.append('clipPath').attr('id', 'fc').append('rect').attr('width', 640).attr('height', 440);
      const g = svg.append('g').attr('clip-path', 'url(#fc)');
      const land = { type: 'FeatureCollection', features: [
        ...st.filter(f => !['02', '15', '72', '78', '60', '66', '69'].includes(f.id)),
        ...cs.filter(c => ['124', '484', '192', '44'].includes(String(c.id)))] };
      // water lines along the coast: wide ink strokes, each covered by a slightly narrower paper stroke
      for (let k = 8; k >= 1; k--) {
        g.append('path').attr('d', pa(land)).attr('fill', 'none').style('stroke', 'currentColor').attr('stroke-width', k * 14 + 1.6).attr('stroke-opacity', k > 5 ? 0.3 : 0.7);
        g.append('path').attr('d', pa(land)).attr('fill', 'none').style('stroke', 'var(--paper)').attr('stroke-width', k * 14);
      }
      g.append('path').attr('d', pa(land)).style('fill', 'var(--paper)').style('stroke', 'currentColor').attr('stroke-width', 1.8);
      g.selectAll('.reg').data(st.filter(f => G[f.id])).join('path').attr('class', 'reg').attr('d', pa)
        .attr('data-r', f => G[f.id]).style('cursor', 'pointer')
        .on('click', (e, f) => { selR = G[f.id]; if (!AV[selR].includes(selP)) selP = AV[selR][AV[selR].length - 1]; updateEdition(); });
      g.append('path').attr('d', pa(topojson.mesh(us, us.objects.states, (a, b) => a !== b && G[a.id] !== G[b.id])))
        .attr('fill', 'none').style('stroke', 'currentColor').attr('stroke-width', 2.2);
      g.append('path').attr('d', pa(topojson.mesh(us, us.objects.states, (a, b) => a !== b && G[a.id] === G[b.id] && G[a.id])))
        .attr('fill', 'none').style('stroke', 'currentColor').attr('stroke-width', 0.9).attr('stroke-dasharray', '3 4');
      [['New England', [-68.0, 40.7], 'N. England'], ['Mid-Atlantic', [-77.8, 41.6], 'Mid-Atlantic'], ['South', [-80.6, 34.0], 'South']].forEach(([n, ll, t]) => {
        const xy = pr(ll);
        g.append('text').attr('class', 'rl').attr('data-r', n).attr('x', xy[0]).attr('y', xy[1]).attr('text-anchor', 'middle')
          .style('font-family', "'IM Fell English SC', serif").attr('font-size', 34).attr('letter-spacing', 1).text(t);
      });
      const uk = { type: 'FeatureCollection', features: cs.filter(c => ['826', '372'].includes(String(c.id))) };
      const bx = [470, 10, 160, 140];
      const ip = d3.geoMercator().fitExtent([[bx[0] + 16, bx[1] + 34], [bx[0] + bx[2] - 16, bx[1] + bx[3] - 10]], uk);
      svg.append('rect').attr('x', bx[0]).attr('y', bx[1]).attr('width', bx[2]).attr('height', bx[3]).style('fill', 'var(--paper)').style('stroke', 'currentColor').attr('stroke-width', 1.8);
      svg.selectAll('.uk').data(uk.features).join('path').attr('class', 'reg').attr('data-r', f => String(f.id) === '826' ? 'Britain' : 'x')
        .attr('d', d3.geoPath(ip)).style('stroke', 'currentColor').attr('stroke-width', 1.2).style('cursor', 'pointer')
        .on('click', (e, f) => { if (String(f.id) === '826') { selR = 'Britain'; if (!AV[selR].includes(selP)) selP = '1800–1810'; updateEdition(); } });
      svg.append('text').attr('class', 'rl').attr('data-r', 'Britain').attr('x', bx[0] + 10).attr('y', bx[1] + 28)
        .style('font-family', "'IM Fell English SC', serif").attr('font-size', 28).text('Britain');
      updateEdition();
    }).catch(() => { $('cap').textContent = '(The map needs the map files from the web.)'; });
  }

  // ---------- market receipt ----------
  const PER = ['Colonial', 'War', 'Confed.', '1790s', '1800–10'];
  const D = {
    'Indian corn': ['Grain & Flour', 'bu.', [0.417, 0.953, 0.5, 0.573, 0.775]],
    'Wheat': ['Grain & Flour', 'bu.', [0.771, 1.5, 0.906, 1.03, 1.7]],
    'Oats': ['Grain & Flour', 'bu.', [null, 0.198, 0.312, 0.35, 0.445]],
    'Rye': ['Grain & Flour', 'bu.', [null, 0.565, 0.562, 1.0, 0.7]],
    'Flour': ['Grain & Flour', 'bbl.', [null, null, 5.125, 5.06, 9.5]],
    'Rice': ['Grain & Flour', 'cwt.', [null, null, 4.042, 2.88, 5.0]],
    'Beans & peas': ['Grain & Flour', 'bu.', [null, null, 0.75, 0.73, null]],
    'Ship bread': ['Grain & Flour', 'cwt.', [null, null, 2.5, 3.071, 6.25]],
    'Beef': ['Meat', 'bbl.', [6.0, 11.25, 6.812, 7.5, 11.25]],
    'Pork': ['Meat', 'bbl.', [null, null, 11.458, 10.918, 20.0]],
    'Bacon & hams': ['Meat', 'lb.', [null, null, 0.078, 0.095, 0.105]],
    'Butter': ['Dairy', 'lb.', [null, 0.078, 0.12, 0.113, 0.158]],
    'Coffee': ['Groceries', 'lb.', [null, 0.125, 0.177, 0.185, 0.26]],
    'Tea': ['Groceries', 'lb.', [null, 0.452, 0.833, 0.53, 1.01]],
    'Salt': ['Groceries', 'bu.', [null, 0.25, 0.219, 0.33, 1.06]],
    'Sugar': ['Sugar & Molasses', 'lb.', [null, 0.219, 0.151, 0.175, 0.28]],
    'Molasses': ['Sugar & Molasses', 'gal.', [null, null, 0.24, 0.47, 0.55]],
    'Rum': ['Wine & Spirits', 'gal.', [null, 0.5, 0.539, 0.965, 1.1]],
    'Cotton': ['Staples', 'lb.', [null, 0.129, 0.417, 0.33, 0.4]],
    'Wax': ['Household', 'lb.', [null, null, 0.406, 0.215, 0.3]],
  };
  const off = new Set();
  (function buildReceipt() {
    const box = $('rec');
    box.innerHTML = '<p class="r-title">Price Current</p><p class="r-sub">New York · Philadelphia · 1784–1789</p>';
    let sec = '';
    Object.entries(D).forEach(([n, [s, u, v]]) => {
      if (s !== sec) { sec = s; const h = document.createElement('div'); h.className = 'sec'; h.textContent = s; box.appendChild(h); }
      const w = v[1], c = v[2];
      let chg = '<span class="c small">new</span>';
      if (w) { const p = Math.round((c / w - 1) * 100); chg = `<span class="c ${p > 0 ? 'red' : ''}">${p > 0 ? '▲' : p < 0 ? '▼' : '='}${Math.abs(p)}%</span>`; }
      const d = document.createElement('div'); d.className = 'ln';
      d.innerHTML = `<span class="n">${n}</span><span class="u">${u}</span><span class="d"></span><span class="p">≈$${c.toFixed(2)}</span>${chg}`;
      d.querySelector('.n').onclick = () => { off.has(n) ? off.delete(n) : off.add(n); d.classList.toggle('off'); basket(); };
      d.querySelector('.p').onclick = () => hist(n);
      box.appendChild(d);
    });
    const f = document.createElement('div'); f.className = 'r-foot';
    f.textContent = 'US dollars, median of the distinct printed prices. ▲▼ against the war years; "new": not printed in the war years. Click a name to strike it out, a price to see it period by period.';
    box.appendChild(f);
  })();
  function basket() {
    const kept = Object.entries(D).filter(([n, x]) => !off.has(n) && x[2][1]);
    const left = Object.entries(D).filter(([n, x]) => !off.has(n) && !x[2][1]).map(([n]) => n.toLowerCase());
    const b = $('big');
    if (!kept.length) { b.textContent = '—'; $('bt').textContent = 'Nothing left to compare.'; $('lo').textContent = ''; return; }
    const g = Math.exp(kept.reduce((s, [, x]) => s + Math.log(x[2][2] / x[2][1]), 0) / kept.length);
    const p = Math.round((g - 1) * 100);
    b.textContent = (p > 0 ? '+' : '') + p + '%'; b.classList.toggle('down', p < 0);
    $('bt').textContent = `Your basket cost ${Math.abs(p)}% ${p >= 0 ? 'more' : 'less'} than in the war years: the ${kept.length} goods you kept that were also printed then, each counting the same.`;
    $('lo').textContent = left.length ? 'Not in the comparison (no war-years price): ' + left.join(', ') + '.' : '';
  }
  function hist(n) {
    const v = D[n][2];
    const pts = v.map((x, i) => [PER[i], x, i]).filter(a => a[1] != null);
    const mx = Math.max(...pts.map(a => a[1]));
    let s = `<div class="t">${n}, ${D[n][1]} · by period</div><svg viewBox="0 0 280 140">`;
    pts.forEach((a, j) => {
      const x = 26 + j * (228 / Math.max(pts.length - 1, 1)), y = 118 - (a[1] / mx) * 86, cur = a[2] === 2;
      const col = cur ? 'var(--red)' : 'currentColor';
      s += `<line x1="${x - 15}" x2="${x + 15}" y1="${y}" y2="${y}" stroke="${col}" stroke-width="${cur ? 5 : 3}"/>` +
        `<text x="${x}" y="${y - 8}" text-anchor="middle" font-size="12" fill="${col}" font-family="var(--text)">$${a[1].toFixed(2)}</text>` +
        `<text x="${x}" y="136" text-anchor="middle" font-size="11" fill="currentColor" font-style="italic" font-family="var(--text)">${a[0]}</text>`;
    });
    $('hist').innerHTML = s + '</svg><p class="small">Only periods with printed prices. Red: this edition.</p>';
  }

  // ---------- loaves: woodcut (contemporary) or fine engraving (old style), to scale by weight ----------
  function el(t, a, p) { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); p.appendChild(e); return e; }
  function shape(cx, base, w, h) {
    return `M${cx - w / 2} ${base} C${cx - w / 2} ${base - h * 1.05} ${cx - w * 0.18} ${base - h} ${cx} ${base - h} C${cx + w * 0.18} ${base - h} ${cx + w / 2} ${base - h * 1.05} ${cx + w / 2} ${base} Z`;
  }
  function woodcut(svg, cx, base, w, h) {
    const id = 'w' + Math.random().toString(36).slice(2);
    el('path', { d: shape(cx, base, w, h) }, el('clipPath', { id }, svg));
    const g = el('g', { 'clip-path': `url(#${id})` }, svg);
    for (let y = base - h * 0.58; y < base; y += Math.max(3.4, h / 12)) el('line', { x1: cx - w * 0.04, x2: cx + w / 2, y1: y, y2: y, stroke: 'currentColor', 'stroke-width': y > base - h * 0.3 ? 2.8 : 1.7 }, g);
    el('path', { d: shape(cx, base, w, h), fill: 'none', stroke: 'currentColor', 'stroke-width': 3.2 }, svg);
    for (let k = -1; k <= 1; k++) { const x = cx + k * w * 0.22; el('path', { d: `M${x - w * 0.07} ${base - h * 0.62} l${w * 0.12} ${-h * 0.16}`, stroke: 'currentColor', 'stroke-width': 2.8 }, svg); }
    el('rect', { x: cx - w / 2 - 8, y: base, width: w + 16, height: 5, fill: 'currentColor' }, svg);
  }
  function engraved(svg, cx, base, w, h) {
    const id = 'e' + Math.random().toString(36).slice(2);
    el('path', { d: shape(cx, base, w, h) }, el('clipPath', { id }, svg));
    const g = el('g', { 'clip-path': `url(#${id})` }, svg);
    for (let i = 1; i <= 24; i++) {
      const t = i / 25, rw = w / 2 * (1 - t * 0.05), rh = h * (1 - t * 0.9);
      el('path', { d: `M${cx - rw} ${base} C${cx - rw} ${base - rh * 1.05} ${cx - rw * 0.36} ${base - rh} ${cx} ${base - rh} C${cx + rw * 0.36} ${base - rh} ${cx + rw} ${base - rh * 1.05} ${cx + rw} ${base}`,
        fill: 'none', stroke: 'currentColor', 'stroke-width': 0.35 + 0.5 * t, opacity: 0.6 }, g);
    }
    // shadow on the right side only: hatch, then cross-hatch nearer the edge (clipped to a band, so no hard triangle)
    const id2 = 's' + Math.random().toString(36).slice(2);
    el('rect', { x: cx + w * 0.12, y: base - h - 2, width: w, height: h + 4 }, el('clipPath', { id: id2 }, svg));
    const sh = el('g', { 'clip-path': `url(#${id2})` }, g);
    for (let x = cx - h; x < cx + w / 2 + h; x += 2.4) el('line', { x1: x, y1: base - h, x2: x + h * 0.35, y2: base, stroke: 'currentColor', 'stroke-width': 0.5 }, sh);
    const id3 = 't' + Math.random().toString(36).slice(2);
    el('rect', { x: cx + w * 0.3, y: base - h - 2, width: w, height: h + 4 }, el('clipPath', { id: id3 }, svg));
    const sh2 = el('g', { 'clip-path': `url(#${id3})` }, g);
    for (let x = cx - h; x < cx + w / 2 + h; x += 2.4) el('line', { x1: x + h * 0.35, y1: base - h, x2: x, y2: base, stroke: 'currentColor', 'stroke-width': 0.5 }, sh2);
    el('path', { d: shape(cx, base, w, h), fill: 'none', stroke: 'currentColor', 'stroke-width': 1.4 }, svg);
    for (let k = -2; k <= 2; k++) {
      const x = cx + k * w * 0.17, y0 = base - h * 0.66 + Math.abs(k) * h * 0.07;
      el('path', { d: `M${x - w * 0.06} ${y0 + h * 0.05} q${w * 0.06} ${-h * 0.12} ${w * 0.12} ${-h * 0.08}`, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.3 }, svg);
    }
    for (let i = 0; i < 12; i++) { const y = base + 3 + i * 1.7; el('line', { x1: cx - w * 0.35 + i * 2, y1: y, x2: cx + w * 0.62 - i * 3, y2: y, stroke: 'currentColor', 'stroke-width': 0.5 }, svg); }
  }
  function coins(svg, x, base, n, label) {
    const fill = 'var(--paper)';
    for (let i = 0; i < n; i++) el('ellipse', { cx: x, cy: base - i * 3.4 - 2, rx: 17, ry: 3.4, fill, stroke: 'currentColor', 'stroke-width': 1.2 }, svg);
    const t = el('text', { x, y: base - n * 3.4 - 10, 'text-anchor': 'middle', 'font-size': 12, fill: 'currentColor', 'font-style': 'italic' }, svg);
    t.textContent = label;
  }
  function drawLoaves() {
    const k = Math.sqrt(32 / 37);               // 2 lb. vs 2 lb. 5 oz.: area to scale
    [['l1', k, 21, '21 coppers'], ['l2', 1, 6, 'six pence']].forEach(([id, s, n, lab]) => {
      const svg = $(id); svg.innerHTML = ''; svg.style.color = 'var(--ink)';
      (style === 'old' ? engraved : woodcut)(svg, 100, 150, 160 * s, 100 * s);
      coins(svg, 238, 150, n, lab);
    });
  }

  // ---------- year by year (only years with a price) ----------
  (function evo() {
    if (!window.d3) return;
    const s = d3.select('#evo'), W = 1000, H = 230, m = { l: 50, r: 20, t: 18, b: 30 };
    const x = d3.scaleLinear().domain([1770, 1811]).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([0, 11]).range([H - m.b, m.t]);
    const v = { 1786: 4.78, 1787: 5.28, 1788: 4.07, 1789: 4.07, 1792: 4.67, 1793: 5.42, 1796: 10.13, 1800: 9.5 };
    s.append('g').attr('transform', `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickValues([1770, 1775, 1780, 1785, 1790, 1795, 1800, 1805, 1810]).tickFormat(d3.format('d')))
      .call(g => g.selectAll('text').style('font-family', 'var(--text)').attr('font-size', 13));
    s.append('g').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(t => '$' + t))
      .call(g => g.selectAll('text').style('font-family', 'var(--text)').attr('font-size', 13));
    const ks = Object.keys(v).map(Number); let seg = [];
    ks.forEach((k, i) => { seg.push(k); if (ks[i + 1] !== k + 1) {
      if (seg.length > 1) s.append('path').attr('d', d3.line().x(t => x(t + 0.5)).y(t => y(v[t]))(seg)).attr('fill', 'none').style('stroke', 'currentColor').attr('stroke-width', 2);
      seg = []; } });
    ks.forEach(k => {
      const cur = k >= 1784 && k <= 1789;
      s.append('circle').attr('cx', x(k + 0.5)).attr('cy', y(v[k])).attr('r', 5).style('fill', cur ? 'var(--red)' : 'currentColor');
      s.append('text').attr('x', x(k + 0.5)).attr('y', y(v[k]) + (k === 1788 ? 22 : -10)).attr('text-anchor', 'middle').style('font-family', 'var(--text)')
        .attr('font-size', 12).style('fill', cur ? 'var(--red)' : 'currentColor').text('$' + v[k].toFixed(2));
    });
  })();

  setStyle(style);
  updateEdition();
  basket();
  hist('Flour');
})();
