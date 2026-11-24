/* receipt_v4.js — draws receipts and the price chart for story_v1.html
   (copied from receipt_v3.js on 2026-11-24; the price chart now shows the MEDIAN PER PERIOD,
    taken from RECEIPTS.by_period, with the period being viewed highlighted)
   Classic script (no module), so it also works without a build step.

   Exposes:
     window.drawReceipt(container, receipt, opts)
     window.showPriceChart(region, line, opts)

   Rules (see viz/DECISIONS.md): every number shown comes from window.RECEIPTS
   (made by scripts/viz_prepare_data.py). Nothing is computed here except formatting.
*/
(function () {
  'use strict';

  const R = () => window.RECEIPTS || {};

  const REGION_CLASS = {
    'New England': 'ne', 'Mid-Atlantic': 'ma', 'South': 'so', 'Britain': 'br', 'Other ports': 'op',
  };
  const regionClass = name => REGION_CLASS[name] || 'op';

  // ---------- small helpers ----------
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function fmtUSD(x) {
    if (x == null || isNaN(x)) return '';
    if (x >= 1000) return '$' + Math.round(x).toLocaleString('en-US');
    return '$' + x.toFixed(2);
  }

  function cityRegion(city) {
    const c = (R().cities || []).find(c => c.name === city);
    return c ? c.region : '';
  }

  function bySection(lines) {
    const order = R().sections || [];
    const groups = [];
    for (const s of order) {
      const ls = lines.filter(l => (l.section || 'Other') === s);
      if (ls.length) groups.push([s, ls]);
    }
    const rest = lines.filter(l => !order.includes(l.section || 'Other'));
    if (rest.length) groups.push(['Other', rest]);
    return groups;
  }

  // what the arrow compares against, per view
  const COMPARE = {
    period: 'the period just before (no arrow if it had no price)',
    year: 'the year just before (no arrow if it had no price)',
    month: 'the last earlier month with a price in this city',
  };

  // ---------- one receipt line ----------
  function drawLine(line, opts) {
    const row = el('div', 'r-line');
    row.tabIndex = 0;
    row.setAttribute('role', 'button');

    const name = el('span', 'r-line__name', line.product);
    const unit = el('span', 'r-line__unit', 'per ' + line.unit);
    const dots = el('span', 'r-line__dots');
    const prov = line.n_provisional > 0;
    const price = el('span', 'r-line__price' + (prov ? ' is-prov' : ''), (prov ? '≈' : '') + fmtUSD(line.price_usd));
    if (prov) price.title = 'Converted from local currency at the legal rate (provisional)';

    const chg = el('span', 'r-line__chg');
    if (line.pct_change != null) {
      const p = Math.round(line.pct_change);
      if (p > 0) { chg.classList.add('is-up'); chg.textContent = '▲ ' + p + '%'; }
      else if (p < 0) { chg.classList.add('is-down'); chg.textContent = '▼ ' + Math.abs(p) + '%'; }
      else { chg.classList.add('is-flat'); chg.textContent = '= 0%'; }
      chg.title = 'Change from ' + (COMPARE[opts.view] || 'the previous receipt') +
        (line.prev_month ? ' (' + line.prev_month + ')' : '');
    }

    const flag = el('span', 'r-line__flag');
    const notes = [];
    if (line.warn) notes.push('Printed prices here range from ' + fmtUSD(line.price_min) + ' to ' + fmtUSD(line.price_max) +
      ' (mixed varieties or a misreading).');
    if (line.jump) notes.push('More than 100% change: check the original printed list.');
    if (notes.length) { flag.textContent = '⚠'; flag.title = notes.join(' '); }

    row.append(name, unit, dots, price, chg, flag);

    const open = () => window.showPriceChart(opts.region, line, opts);
    if (opts.region && (R().timelines || {})[opts.region]) {
      row.addEventListener('click', open);
      row.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
      row.title = 'Click to see the price of ' + line.product + ' period by period';
    } else {
      row.classList.add('is-static');
      row.removeAttribute('role');
      row.tabIndex = -1;
    }
    return row;
  }

  function drawLineGroups(parent, lines, opts) {
    for (const [section, ls] of bySection(lines)) {
      parent.appendChild(el('div', 'r-section', section));
      for (const l of ls) parent.appendChild(drawLine(l, opts));
    }
  }

  function notQuoted(lines, text) {
    if (!lines.length) return null;
    const p = el('p', 'r-notquoted');
    p.appendChild(el('span', 'r-notquoted__label', text + ' '));
    p.appendChild(document.createTextNode(lines.map(l => l.product).join(', ')));
    return p;
  }

  // ---------- header (structure of a printed receipt) ----------
  //   Title
  //   place line
  //   Household basket: n of m goods quoted
  //   Date: ...                                  right side
  function drawHeader(card, regionName, receipt, opts) {
    const head = el('header', 'r-head');
    head.appendChild(el('h2', 'r-head__title', opts.title || regionName));
    if (opts.place) {
      // each city stays whole when the line wraps
      const pl = el('p', 'r-head__line r-head__place');
      [].concat(opts.place).forEach((name, i) => {
        if (i) pl.appendChild(document.createTextNode('\u00a0· '));
        pl.appendChild(el('span', null, name));
      });
      head.appendChild(pl);
    }
    const lines = (receipt && receipt.lines) || [];
    const house = lines.filter(l => l.group !== 'trade');
    if (house.length && house.some(l => l.status === 'ok'))
      head.appendChild(el('p', 'r-head__line', 'Household basket: ' +
        house.filter(l => l.status === 'ok').length + ' of ' + house.length + ' goods priced'));
    let right = opts.dateRight || '';
    if (!right && receipt) {
      const meta = [];
      if (receipt.issues) meta.push(receipt.issues.length + ' issue' + (receipt.issues.length === 1 ? '' : 's'));
      if (receipt.newspapers) meta.push(receipt.newspapers.length + ' newspaper' + (receipt.newspapers.length === 1 ? '' : 's'));
      if (receipt.n_monthly_receipts) meta.push(receipt.n_monthly_receipts + ' monthly receipt' + (receipt.n_monthly_receipts === 1 ? '' : 's'));
      right = meta.join(' · ');
    }
    const row = el('div', 'r-head__date');
    row.append(el('span', null, opts.dateLeft || ''), el('span', null, right));
    head.appendChild(row);
    card.appendChild(head);
  }

  // ---------- receipt ----------
  // opts: { view, title, place, dateLeft, dateRight, region, highlight:{from,to}, whenText, emptyText }
  function drawReceipt(container, receipt, opts) {
    opts = opts || {};
    const regionName = opts.region || receipt.region || cityRegion(receipt.city);
    opts.region = regionName;
    const card = el('article', 'r-card r-card--' + regionClass(regionName));
    drawHeader(card, regionName, receipt, opts);
    const body = el('div', 'r-body');
    card.appendChild(body);

    if (!receipt || receipt.status === 'no_data' || !receipt.lines || !receipt.lines.some(l => l.status === 'ok')) {
      drawEmpty(card, body, receipt, opts);
      container.appendChild(card);
      return card;
    }

    const house = receipt.lines.filter(l => l.group !== 'trade');
    const trade = receipt.lines.filter(l => l.group === 'trade');
    const hOk = house.filter(l => l.status === 'ok');
    const hMiss = house.filter(l => l.status !== 'ok');

    drawLineGroups(body, hOk, opts);
    const nq = notQuoted(hMiss, 'Also in the basket, no printed price here:');
    if (nq) body.appendChild(nq);

    if (trade.length) {
      const tOk = trade.filter(l => l.status === 'ok');
      const tMiss = trade.filter(l => l.status !== 'ok');
      const box = el('section', 'r-trade');
      const btn = el('button', 'r-trade__toggle');
      btn.type = 'button';
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = '<span class="r-trade__icon" aria-hidden="true">+</span>';
      btn.appendChild(document.createTextNode('Trade goods: ' + tOk.length + ' of ' + trade.length + ' priced'));
      const content = el('div', 'r-trade__content');
      content.hidden = true;
      drawLineGroups(content, tOk, opts);
      const tq = notQuoted(tMiss, 'No printed price here:');
      if (tq) content.appendChild(tq);
      btn.addEventListener('click', () => {
        const open = btn.getAttribute('aria-expanded') !== 'true';
        btn.setAttribute('aria-expanded', String(open));
        btn.querySelector('.r-trade__icon').textContent = open ? '−' : '+';
        content.hidden = !open;
      });
      box.append(btn, content);
      body.appendChild(box);
    }

    // footnote
    const where = { period: 'this period', year: 'this year', month: 'this month' }[opts.view] || 'this receipt';
    const foot = el('footer', 'r-foot');
    foot.appendChild(el('p', null, 'US dollars. Each price is the median of the distinct printed prices in ' + where + '.'));
    if (receipt.lines.some(l => l.status === 'ok' && l.n_provisional > 0))
      foot.appendChild(el('p', null, '≈ converted from local currency at the legal rate (provisional).'));
    foot.appendChild(el('p', null, '▲ ▼ change from ' + (COMPARE[opts.view] || 'the previous receipt') + '.'));
    if (receipt.lines.some(l => l.warn || l.jump))
      foot.appendChild(el('p', null, '⚠ worth checking against the original page (hover it).'));
    foot.appendChild(el('p', 'r-foot__hint', 'Click a product to see its price period by period.'));
    body.appendChild(foot);

    container.appendChild(card);
    return card;
  }

  // empty receipt: blurred placeholder + clear note (missing data is blurred, not hidden)
  function drawEmpty(card, body, receipt, opts) {
    card.classList.add('r-card--empty');
    const ghost = el('div', 'r-ghost');
    ghost.setAttribute('aria-hidden', 'true');
    const lines = (receipt && receipt.lines && receipt.lines.length) ? receipt.lines.filter(l => l.group !== 'trade').slice(0, 9) : [];
    const names = lines.length ? lines.map(l => [l.product, l.unit]) :
      [['flour', 'barrel'], ['beef', 'barrel'], ['pork', 'barrel'], ['butter', 'lb'], ['sugar', 'cwt'], ['coffee', 'lb'], ['tea', 'lb'], ['rum', 'gallon']];
    for (const [p, u] of names) {
      const row = el('div', 'r-line is-static');
      row.append(el('span', 'r-line__name', p), el('span', 'r-line__unit', 'per ' + u), el('span', 'r-line__dots'),
        el('span', 'r-line__price', '$00.00'));
      ghost.appendChild(row);
    }
    body.appendChild(ghost);
    const note = el('div', 'r-empty-note');
    note.appendChild(el('strong', null, 'No price list survives here'));
    note.appendChild(el('p', null, opts.emptyText || 'No newspaper price current was found for this place and time.'));
    body.appendChild(note);
  }

  // ---------- price chart (one product in one region: median per period + every printed price) ----------
  function closeChart() {
    const old = document.querySelector('.chart-backdrop');
    if (old) old.remove();
    document.removeEventListener('keydown', escClose);
  }
  function escClose(e) { if (e.key === 'Escape') closeChart(); }

  function showPriceChart(region, line, opts) {
    closeChart();
    const tl = ((R().timelines || {})[region] || {})[line.product];
    const back = el('div', 'chart-backdrop');
    const pop = el('div', 'chart-pop');
    pop.setAttribute('role', 'dialog');
    pop.classList.add('r-card--' + regionClass(region));
    pop.setAttribute('aria-label', line.product + ' prices in ' + region);
    back.appendChild(pop);
    back.addEventListener('click', e => { if (e.target === back) closeChart(); });
    document.addEventListener('keydown', escClose);

    const close = el('button', 'chart-pop__close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', closeChart);
    pop.appendChild(close);

    const head = el('header', 'chart-pop__head r-band--' + regionClass(region));
    head.appendChild(el('h2', null, line.product));
    head.appendChild(el('p', null, region + ' · US dollars per ' + (tl ? tl.unit : line.unit)));
    pop.appendChild(head);

    const info = el('div', 'chart-pop__info');
    const here = [];
    here.push((opts.whenText || 'Here') + ': ' + (line.n_provisional ? '≈' : '') + fmtUSD(line.price_usd));
    if (line.n_obs) here.push(line.n_obs + ' printed price' + (line.n_obs === 1 ? '' : 's'));
    if (line.price_min != null && line.price_max != null && line.price_min !== line.price_max)
      here.push('range ' + fmtUSD(line.price_min) + '–' + fmtUSD(line.price_max));
    if (line.cities && line.cities.length) here.push(line.cities.join(', '));
    info.appendChild(el('p', 'chart-pop__here', here.join(' · ')));
    if (line.varieties && line.varieties.length)
      info.appendChild(el('p', 'chart-pop__printed', 'Printed as: ' + line.varieties.join(' · ')));
    pop.appendChild(info);

    const box = el('div', 'chart-pop__chart');
    pop.appendChild(box);
    const tip = el('div', 'chart-pop__tip');
    pop.appendChild(tip);
    pop.appendChild(el('p', 'chart-pop__legend',
      '▬ median price of the period (number above it)   · small dots: every printed price (● in dollars, ○ converted, provisional)   shaded = the period you are looking at'));
    document.body.appendChild(back);
    close.focus();

    if (!tl) {
      box.appendChild(el('p', 'chart-pop__none', 'No dated prices for this product in this unit.'));
      return;
    }
    drawChartSVG(box, tip, tl, region, opts.highlight, line);
  }

  // median per period for this product + unit, as computed by viz_prepare_data.py (the page computes nothing)
  function periodMedians(region, product, unit) {
    return (R().periods || []).map(p => {
      const rec = (R().by_period || []).find(r => r.region === region && r.period === p.id);
      const l = rec && (rec.lines || []).find(x => x.product === product && x.unit === unit && x.status === 'ok');
      return { p, v: l ? l.price_usd : null, n: l ? l.n_obs : 0, prov: l ? l.n_provisional > 0 : false };
    });
  }

  function drawChartSVG(box, tip, tl, region, hl, line) {
    const W = 640, H = 330, m = { t: 34, r: 14, b: 52, l: 58 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('class', 'chart-svg');
    const periods = R().periods || [];
    const meds = periodMedians(region, line.product, tl.unit || line.unit);
    const obs = tl.obs || [];
    const color = getComputedStyle(document.documentElement).getPropertyValue('--' + regionClass(region)).trim() || '#333';

    // which period is on screen (period view: its range; year/month view: the period that contains it)
    const yr = hl && hl.from != null ? Math.floor(hl.from) : null;
    const cur = periods.findIndex(p => yr != null && yr >= p.start && yr <= p.end);

    const band = d3.scaleBand().domain(periods.map(p => p.id)).range([m.l, W - m.r]).paddingInner(0.08);
    const maxV = d3.max([d3.max(obs, o => o.v) || 0, d3.max(meds, d => d.v) || 0]) || 1;
    const y = d3.scaleLinear().domain([0, maxV]).nice().range([H - m.b, m.t]);
    // inside each band, dots keep their date order
    const xIn = (o, p) => band(p.id) + band.bandwidth() * Math.min(0.98, Math.max(0.02, (o.y - p.start) / (p.end + 1 - p.start)));

    periods.forEach((p, i) => {
      const x0 = band(p.id), bw = band.bandwidth();
      svg.append('rect').attr('x', x0).attr('y', m.t - 6).attr('width', bw).attr('height', H - m.b - m.t + 6)
        .attr('class', i === cur ? 'chart-band is-current' : 'chart-band');
      svg.append('text').attr('x', x0 + bw / 2).attr('y', H - m.b + 18).attr('text-anchor', 'middle')
        .attr('class', 'chart-band-label' + (i === cur ? ' is-current' : '')).text(p.label);
      svg.append('text').attr('x', x0 + bw / 2).attr('y', H - m.b + 34).attr('text-anchor', 'middle')
        .attr('class', 'chart-band-sub').text(`${p.start}–${p.end}`);
    });

    svg.append('g').attr('class', 'chart-axis').attr('transform', `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(5).tickFormat(d => '$' + d3.format(',')(d)));

    // every printed price, faint, behind the medians
    const inPeriod = o => periods.find(p => o.y >= p.start && o.y < p.end + 1);
    svg.append('g').selectAll('circle').data(obs.filter(inPeriod)).join('circle')
      .attr('cx', o => xIn(o, inPeriod(o))).attr('cy', o => y(o.v)).attr('r', 3)
      .attr('fill', o => o.p ? '#fff' : color).attr('stroke', color).attr('stroke-width', 1)
      .attr('opacity', 0.35).attr('class', 'chart-dot')
      .on('mouseenter', function (e, o) {
        d3.select(this).attr('r', 6).attr('opacity', 1);
        tip.textContent = '';
        tip.appendChild(el('strong', null, o.d + ' · ' + o.c + ' · ' + (o.p ? '≈' : '') + fmtUSD(o.v)));
        tip.appendChild(el('span', null, 'Printed: ' + o.t));
        tip.classList.add('is-on');
      })
      .on('mouseleave', function () { d3.select(this).attr('r', 3).attr('opacity', 0.35); tip.classList.remove('is-on'); });

    // the medians (one per period); a period without prices says so
    meds.forEach((d, i) => {
      const x0 = band(d.p.id), bw = band.bandwidth();
      const isCur = i === cur;
      if (d.v == null) {
        svg.append('text').attr('x', x0 + bw / 2).attr('y', H - m.b - 10).attr('text-anchor', 'middle')
          .attr('class', 'chart-noprice').text('no prices');
        return;
      }
      svg.append('line').attr('x1', x0 + bw * 0.12).attr('x2', x0 + bw * 0.88).attr('y1', y(d.v)).attr('y2', y(d.v))
        .attr('class', 'chart-median' + (isCur ? ' is-current' : '')).attr('stroke', isCur ? color : '#3a4048');
      svg.append('text').attr('x', x0 + bw / 2).attr('y', y(d.v) - 9).attr('text-anchor', 'middle')
        .attr('class', 'chart-median-label' + (isCur ? ' is-current' : '')).attr('fill', isCur ? color : '#3a4048')
        .text((d.prov ? '≈' : '') + fmtUSD(d.v));
      svg.append('text').attr('x', x0 + bw / 2).attr('y', H - m.b - 6).attr('text-anchor', 'middle')
        .attr('class', 'chart-n').text(`${d.n} price${d.n === 1 ? '' : 's'}`);
    });
  }

  window.drawReceipt = drawReceipt;
  window.showPriceChart = showPriceChart;
  window.fmtUSD = fmtUSD;
})();
