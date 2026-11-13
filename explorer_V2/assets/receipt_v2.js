/* receipt_v2.js — draws receipts, scraps and the price chart for explorer_v2.html
   Classic script (no module), so it also works without a build step.

   Exposes:
     window.drawReceipt(container, receipt, opts)
     window.drawScrap(container, scrap)
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
    period: 'the previous period',
    year: 'the previous year with prices',
    month: 'the last earlier month this city priced it',
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
    if (line.warn) notes.push('Quotes this month range from ' + fmtUSD(line.price_min) + ' to ' + fmtUSD(line.price_max) +
      ' (mixed varieties or a misreading).');
    if (line.jump) notes.push('More than 100% change: check the original printed list.');
    if (notes.length) { flag.textContent = '⚠'; flag.title = notes.join(' '); }

    row.append(name, unit, dots, price, chg, flag);

    const open = () => window.showPriceChart(opts.region, line, opts);
    if (opts.region && (R().timelines || {})[opts.region]) {
      row.addEventListener('click', open);
      row.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
      row.title = 'Click to see every printed quote of ' + line.product;
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
        house.filter(l => l.status === 'ok').length + ' of ' + house.length + ' goods quoted'));
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
    const nq = notQuoted(hMiss, 'Also in the basket, not quoted here:');
    if (nq) body.appendChild(nq);

    if (trade.length) {
      const tOk = trade.filter(l => l.status === 'ok');
      const tMiss = trade.filter(l => l.status !== 'ok');
      const box = el('section', 'r-trade');
      const btn = el('button', 'r-trade__toggle');
      btn.type = 'button';
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = '<span class="r-trade__icon" aria-hidden="true">+</span>';
      btn.appendChild(document.createTextNode('Trade goods: ' + tOk.length + ' of ' + trade.length + ' quoted'));
      const content = el('div', 'r-trade__content');
      content.hidden = true;
      drawLineGroups(content, tOk, opts);
      const tq = notQuoted(tMiss, 'Not quoted here:');
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
    foot.appendChild(el('p', null, 'US dollars. Each price is the median of the distinct quotes printed in ' + where + '.'));
    if (receipt.lines.some(l => l.status === 'ok' && l.n_provisional > 0))
      foot.appendChild(el('p', null, '≈ converted from local currency at the legal rate (provisional).'));
    foot.appendChild(el('p', null, '▲ ▼ change from ' + (COMPARE[opts.view] || 'the previous receipt') + '.'));
    if (receipt.lines.some(l => l.warn || l.jump))
      foot.appendChild(el('p', null, '⚠ worth checking against the original page (hover it).'));
    foot.appendChild(el('p', 'r-foot__hint', 'Click a product to see every quote of it.'));
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

  // ---------- scrap (Other ports, or a port quoted in this view) ----------
  function drawScrap(container, scrap, opts) {
    opts = opts || {};
    const card = el('article', 'r-scrap');
    const head = el('header', 'r-scrap__head');
    if (opts.hideCity) head.appendChild(el('h3', 'r-scrap__city', scrap.label || scrap.month || ''));
    else {
      head.appendChild(el('h3', 'r-scrap__city', scrap.city));
      head.appendChild(el('p', 'r-scrap__when', scrap.label || scrap.month || ''));
    }
    card.appendChild(head);
    const body = el('div', 'r-scrap__body');
    const ok = (scrap.lines || []).filter(l => l.status === 'ok');
    for (const l of ok) body.appendChild(drawLine(l, { view: 'month', region: null }));
    card.appendChild(body);
    if (scrap.needs_review) card.appendChild(el('p', 'r-scrap__review', 'Location to be checked'));
    container.appendChild(card);
    return card;
  }

  // ---------- price chart (all printed quotes of one product in one region) ----------
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
    if (line.n_obs) here.push(line.n_obs + ' quote' + (line.n_obs === 1 ? '' : 's'));
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
      '● printed in dollars   ○ converted (provisional)   shaded = the receipt you are looking at'));
    document.body.appendChild(back);
    close.focus();

    if (!tl || !tl.obs || !tl.obs.length) {
      box.appendChild(el('p', 'chart-pop__none', 'No dated quotes for this product in this unit.'));
      return;
    }
    drawChartSVG(box, tip, tl, region, opts.highlight);
  }

  function drawChartSVG(box, tip, tl, region, hl) {
    const W = 640, H = 310, m = { t: 30, r: 18, b: 34, l: 58 };
    const svg = d3.select(box).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('class', 'chart-svg');
    const obs = tl.obs;
    const x = d3.scaleLinear().domain([1770, 1811]).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([0, d3.max(obs, o => o.v) || 1]).nice().range([H - m.b, m.t]);
    const color = getComputedStyle(document.documentElement).getPropertyValue('--' + regionClass(region)).trim() || '#333';

    // periods as faint background lines
    (R().periods || []).forEach((p, i) => {
      svg.append('line').attr('x1', x(p.start)).attr('x2', x(p.start)).attr('y1', m.t).attr('y2', H - m.b)
        .attr('class', 'chart-period-line');
      svg.append('text').attr('x', x(p.start) + 4).attr('y', m.t + 10 + (i % 2) * 13).attr('class', 'chart-period-text').text(p.label);
    });
    if (hl && hl.from != null) {
      const x0 = x(hl.from), x1 = Math.max(x(hl.to), x0 + 3);
      svg.append('rect').attr('x', x0).attr('y', m.t).attr('width', x1 - x0).attr('height', H - m.b - m.t)
        .attr('class', 'chart-hl');
    }
    svg.append('g').attr('class', 'chart-axis').attr('transform', `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickValues([1770, 1775, 1780, 1785, 1790, 1795, 1800, 1805, 1810]).tickFormat(d3.format('d')));
    svg.append('g').attr('class', 'chart-axis').attr('transform', `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(5).tickFormat(d => '$' + d3.format(',')(d)));

    svg.append('g').selectAll('circle').data(obs).join('circle')
      .attr('cx', o => x(o.y)).attr('cy', o => y(o.v)).attr('r', 4)
      .attr('fill', o => o.p ? '#fff' : color).attr('stroke', color).attr('stroke-width', 1.5)
      .attr('class', 'chart-dot')
      .on('mouseenter', function (e, o) {
        d3.select(this).attr('r', 7);
        tip.textContent = '';
        tip.appendChild(el('strong', null, o.d + ' · ' + o.c + ' · ' + (o.p ? '≈' : '') + fmtUSD(o.v)));
        tip.appendChild(el('span', null, 'Printed: ' + o.t));
        tip.classList.add('is-on');
      })
      .on('mouseleave', function () { d3.select(this).attr('r', 4); tip.classList.remove('is-on'); });
  }

  window.drawReceipt = drawReceipt;
  window.drawScrap = drawScrap;
  window.showPriceChart = showPriceChart;
  window.fmtUSD = fmtUSD;
})();
