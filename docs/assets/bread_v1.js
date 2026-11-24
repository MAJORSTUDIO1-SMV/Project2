/* Bread v1 — Navigation panel, receipt card, and data loading */

// ===== Configuration =====
const REGIONS = [
  { id: 'new-england', label: 'New England', ink: '#6b4768', cities: ['Portland', 'Newport'] },
  { id: 'mid-atlantic', label: 'Mid-Atlantic', ink: '#60867b', cities: ['New York', 'Philadelphia'] },
  { id: 'south', label: 'South', ink: '#c18f38', cities: ['Charleston', 'Williamsburg', 'Alexandria', 'Richmond'] },
];

// ===== Drawing constants (from spec) =====
const LOAF_PATH = 'M6 62 C4 30 30 6 60 6 C92 6 116 30 114 62 Z';
const LOAF_SLASHES = 'M36 28 L48 18 M56 26 L68 16 M76 28 L88 18';
const LOAF_VIEWBOX = '0 0 120 70';

// MAX_OZ will be computed on load from BREAD_DATA
let MAX_OZ = 128; // fallback, will be overwritten in init()

const COIN_MAX_DRAW = 40;

const PERIODS = [
  { id: 'colonial', label: 'Colonial 1770–1775', start: 1770, end: 1775 },
  { id: 'war', label: 'War of Independence 1776–1783', start: 1776, end: 1783 },
  { id: 'confederation', label: 'Confederation 1784–1789', start: 1784, end: 1789 },
  { id: '1790s', label: '1790s', start: 1790, end: 1799 },
  { id: '1800s', label: '1800–1810', start: 1800, end: 1810 },
];

// City to region mapping
const CITY_REGION = {
  'Portland': 'new-england',
  'Newport': 'new-england',
  'New York': 'mid-atlantic',
  'Philadelphia': 'mid-atlantic',
  'Charleston': 'south',
  'Williamsburg': 'south',
  'Alexandria': 'south',
  'Richmond': 'south',
};

// USD status note mapping
const USD_STATUS_NOTES = {
  'exact': 'printed in this money, no conversion',
  'exact_unit_inferred': 'printed amount; the unit is inferred',
  'legal_rate': 'provisional: legal rate of the main visualization',
  'provisional_copper': 'provisional: coppers at 112 per dollar (no primary source yet)',
  'copper_outside_ny_not_converted': 'coppers outside New York: no rate',
  'wartime_paper_not_converted': 'wartime paper money: not converted',
};

// Flour source wording mapping
const FLOUR_SOURCE_WORDING = {
  'printed': 'printed in this notice',
  'same_notice_reprint': 'from another printing of the same notice',
  'same_notice_neighbor': 'from a nearby printing of the same notice',
  'range_from_1803_rule': 'estimated from the 1803 Alexandria rule (not printed)',
  'price_current_wholesale': "from the newspaper's price current (wholesale), not from this notice",
  'null': 'the notice does not print the flour price',
};

// Coin unit display names
const COIN_DISPLAY = {
  'copper': 'copper',
  'penny': 'penny',
  'cent': 'cent',
  'shilling': 'shilling',
};

// ===== Coin stack drawing (from bread/tasks/coin_stack.js) =====
function coinStackSvg(n, maxDraw = COIN_MAX_DRAW) {
  const W = 34, FACE = 10, THICK = 5, STEP = 5;
  const OFF = [0, -3, 2, -2, 3, -1, 1, -3, 2, 0];
  const C = { face: '#d08a4e', inner: '#c27a3f', rim: '#e3a76b', edge: '#b5652e', reed: '#8f4a1f' };
  const whole = Math.floor(n), half = n - whole >= 0.25;
  const total = Math.min(whole + (half ? 1 : 0), maxDraw);
  const pad = 4, w = W + pad * 2, h = (total - 1) * STEP + FACE + THICK + 2;
  let out = '';
  for (let i = 0; i < total; i++) {
    const isHalf = half && i === total - 1 && whole < maxDraw;
    const cw = W;
    const x = pad + OFF[i % OFF.length];
    const yTop = h - 1 - THICK - FACE - i * STEP;
    const cx = x + cw / 2, rx = cw / 2, ry = FACE / 2, cyTop = yTop + ry, cyBot = cyTop + THICK;
    let coin = '';
    coin += `<path d="M${x} ${cyTop} L${x} ${cyBot} A${rx} ${ry} 0 0 0 ${x + cw} ${cyBot} L${x + cw} ${cyTop} Z" fill="${C.edge}"/>`;
    const reeds = 7;
    for (let r = 1; r <= reeds; r++) {
      const rxp = x + (cw * r) / (reeds + 1);
      const dx = (rxp - cx) / rx, dy = ry * Math.sqrt(Math.max(0, 1 - dx * dx));
      coin += `<line x1="${rxp.toFixed(1)}" y1="${(cyTop + dy).toFixed(1)}" x2="${rxp.toFixed(1)}" y2="${(cyBot + dy - 0.5).toFixed(1)}" stroke="${C.reed}" stroke-width="1.6"/>`;
    }
    coin += `<ellipse cx="${cx}" cy="${cyTop}" rx="${rx}" ry="${ry}" fill="${C.rim}"/>`;
    coin += `<ellipse cx="${cx}" cy="${cyTop + 0.4}" rx="${rx * 0.78}" ry="${ry * 0.62}" fill="${C.inner}"/>`;
    coin += `<ellipse cx="${cx}" cy="${cyTop + 0.8}" rx="${rx * 0.72}" ry="${ry * 0.5}" fill="${C.face}"/>`;
    if (isHalf) {
      const id = 'halfcut' + Math.random().toString(36).slice(2, 8);
      out += `<clipPath id="${id}"><rect x="${x - 1}" y="${yTop - 1}" width="${rx + 1}" height="${FACE + THICK + 2}"/></clipPath>`;
      out += `<g clip-path="url(#${id})">${coin}</g>`;
      out += `<line x1="${cx}" y1="${cyTop - ry}" x2="${cx}" y2="${cyBot + ry}" stroke="${C.reed}" stroke-width="1.2"/>`;
    } else {
      out += coin;
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true">${out}</svg>`;
}

// ===== Drawing functions =====
function computeLoafWidth(weightOz) {
  if (!weightOz || weightOz <= 0) return 40;
  const ratio = Math.sqrt(weightOz / MAX_OZ);
  return 40 + 190 * ratio;
}

function computeLoafHeight(width) {
  return width * 0.58;
}

function createLoafSvg(width, regionInk) {
  const height = computeLoafHeight(width);
  const scale = width / 120; // viewBox is 120 wide
  const scaledHeight = 70 * scale;
  return `
    <svg class="bread-loaf" viewBox="${LOAF_VIEWBOX}" width="${width}" height="${scaledHeight}" aria-hidden="true" role="img">
      <path d="${LOAF_PATH}" fill="var(--crust-fill)" stroke="var(--crust-stroke)" stroke-width="3"/>
      <path d="${LOAF_SLASHES}" fill="none" stroke="var(--slash-stroke)" stroke-width="2" stroke-linecap="round"/>
    </svg>
  `;
}

function createCoinStackSvg(priceNumber, priceUnit, priceAsPrinted) {
  const wholeCoins = Math.floor(priceNumber);
  const hasFraction = priceNumber > wholeCoins;
  const totalCoins = wholeCoins + (hasFraction ? 1 : 0);
  const extraCount = totalCoins - COIN_MAX_DRAW;

  // Use the new coinStackSvg function
  const stackSvg = coinStackSvg(priceNumber, COIN_MAX_DRAW);

  // Label: just "14 coins" or "4½ coins"
  const coinWord = priceUnit === 'copper' ? 'coins' : priceUnit === 'penny' ? 'coins' : priceUnit === 'cent' ? 'coins' : 'coins';
  const label = `${wholeCoins}${hasFraction ? '½' : ''} ${coinWord}`;

  return `
    <div class="bread-coin-stack">
      ${stackSvg}
      ${extraCount > 0 ? `<span class="bread-coin-stack__extra">+${extraCount}</span>` : ''}
      <p class="bread-coin-stack__label">${label}</p>
    </div>
  `;
}

// ===== Weight formatting helper (Philadelphia table format) =====
function formatWeightAsPrinted(weightAsPrinted, weightOz) {
  if (!weightAsPrinted) return '';

  // Check if it's the Philadelphia table format: "0 8 3/4 (lb oz)" or "1 1 1/2 (lb oz)"
  const match = weightAsPrinted.match(/^(\d+)\s+(\d+(?:\s+\d+\/\d+)?)\s*\(lb\s*oz\)/i);
  if (match) {
    const lb = parseInt(match[1], 10);
    const ozPart = match[2].trim();
    if (lb === 0) {
      return `${ozPart} oz.`;
    } else {
      return `${lb} lb. ${ozPart} oz.`;
    }
  }

  // Check for "X lb. Y oz." format (already formatted)
  if (weightAsPrinted.includes('lb.') && weightAsPrinted.includes('oz.')) {
    return weightAsPrinted;
  }

  // Otherwise return as-is
  return weightAsPrinted;
}

function getWeightTableNote(weightAsPrinted) {
  if (!weightAsPrinted) return '';
  const match = weightAsPrinted.match(/^(\d+)\s+(\d+(?:\s+\d+\/\d+)?)\s*\(lb\s*oz\)/i);
  if (match) {
    const lb = parseInt(match[1], 10);
    const ozPart = match[2].trim();
    return `from the table: lb ${lb}, oz ${ozPart}`;
  }
  return '';
}

function createReceiptFigure(notice) {
  const weightOz = notice.weight_oz;
  const priceNumber = notice.price_number;
  const priceUnit = notice.price_unit;
  const priceAsPrinted = notice.price_as_printed;
  const weightAsPrinted = notice.weight_as_printed;

  if (!weightOz || !priceNumber) {
    return '<p class="bread-receipt__figure-none">weight not readable</p>';
  }

  const loafWidth = computeLoafWidth(weightOz);
  const loafSvg = createLoafSvg(loafWidth);
  const coinStackSvg = createCoinStackSvg(priceNumber, priceUnit, priceAsPrinted);

  // Accessibility: aria-label on the figure container
  const ariaLabel = `The whole loaf of ${weightAsPrinted} drawn to scale, next to ${priceAsPrinted}`;

  return `
    <div class="bread-receipt__figure" role="img" aria-label="${ariaLabel}">
      <div class="bread-receipt__figure-pair">
        <div class="bread-receipt__loaf-wrap">
          ${loafSvg}
          <p class="bread-receipt__figure-caption">the whole loaf, to scale</p>
        </div>
        <div class="bread-receipt__coins-wrap">
          ${coinStackSvg}
        </div>
      </div>
    </div>
  `;
}

// ===== State =====
let state = {
  regionId: 'mid-atlantic',
  city: 'New York',
  periodId: 'war',
  year: null, // will be set to first notice's year
  notices: [], // filtered notices for current selection
  allNotices: [], // all notices flat array
  selectedNotice: null, // currently selected notice object
};

// ===== DOM Elements =====
const regionChips = document.getElementById('region-chips');
const cityChips = document.getElementById('city-chips');
const periodChips = document.getElementById('period-chips');
const yearChips = document.getElementById('year-chips');
const receiptEl = document.getElementById('bread-receipt');
const shelfEl = document.getElementById('bread-shelf');

// ===== Initialize =====
function init() {
  // Flatten all notices from BREAD_DATA
  state.allNotices = flattenNotices(BREAD_DATA);
  console.log(`Total notices loaded: ${state.allNotices.length}`);

  // Build navigation
  renderRegionChips();
  renderCityChips();
  renderPeriodChips();

  // Apply default selection: Mid-Atlantic → New York → War → notice of Aug 1779 (1779-08-09)
  updateChipSelection('region', state.regionId);
  updateChipSelection('city', state.city);
  updateChipSelection('period', state.periodId);
  filterNotices();
  renderYearChips();

  // Select the Aug 1779 notice (1779-08-09) as default
  const defaultNotice = state.notices.find(n => n.date === '1779-08-09');
  if (defaultNotice) {
    state.year = getYearLabel(defaultNotice);
    state.selectedNotice = defaultNotice;
  } else {
    // Fallback to first notice
    state.year = state.notices.length > 0 ? getYearLabel(state.notices[0]) : null;
    state.selectedNotice = state.notices[0] || null;
  }
  updateChipSelection('year', state.year);
  renderReceipt();
  renderShelfPlaceholder();

  console.log(`Default selection: region=${state.regionId}, city=${state.city}, period=${state.periodId}, year=${state.year}, notice=${state.selectedNotice?.obs_id}`);
}

// ===== Data helpers =====
function flattenNotices(data) {
  const result = [];
  for (const [city, notices] of Object.entries(data)) {
    for (const notice of notices) {
      result.push({ ...notice, city });
    }
  }
  return result;
}

function getYearLabel(notice) {
  const date = notice.date; // "YYYY-MM-DD"
  const year = date.slice(0, 4);
  const month = date.slice(5, 7);
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${monthNames[parseInt(month, 10) - 1]} ${year}`;
}

function getPeriodIdFromDate(dateStr) {
  const year = parseInt(dateStr.slice(0, 4), 10);
  for (const p of PERIODS) {
    if (year >= p.start && year <= p.end) return p.id;
  }
  return null;
}

function getPeriodLabel(periodId) {
  const p = PERIODS.find(p => p.id === periodId);
  return p ? p.label : periodId;
}

function filterNotices() {
  state.notices = state.allNotices.filter(n => {
    if (n.city !== state.city) return false;
    const periodId = getPeriodIdFromDate(n.date);
    if (periodId !== state.periodId) return false;
    return true;
  });

  // Sort by date
  state.notices.sort((a, b) => a.date.localeCompare(b.date));
}

// ===== Render functions =====
function renderRegionChips() {
  regionChips.innerHTML = '';
  for (const region of REGIONS) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `bread-chip bread-chip--region`;
    btn.dataset.value = region.id;
    btn.textContent = region.label;
    btn.style.setProperty('--c', region.ink);
    btn.setAttribute('role', 'radio');
    btn.setAttribute('aria-pressed', 'false');
    btn.addEventListener('click', () => selectRegion(region.id));
    regionChips.appendChild(btn);
  }
}

function renderCityChips() {
  const region = REGIONS.find(r => r.id === state.regionId);
  if (!region) return;

  cityChips.innerHTML = '';
  for (const city of region.cities) {
    // Check if city has any notices
    const hasNotices = state.allNotices.some(n => n.city === city);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'bread-chip';
    btn.dataset.value = city;
    btn.textContent = city;
    btn.setAttribute('role', 'radio');
    btn.setAttribute('aria-pressed', 'false');
    if (!hasNotices) {
      btn.disabled = true;
    } else {
      btn.addEventListener('click', () => selectCity(city));
    }
    cityChips.appendChild(btn);
  }
}

function renderPeriodChips() {
  periodChips.innerHTML = '';
  for (const period of PERIODS) {
    // Check if city has any notices in this period
    const hasNotices = state.allNotices.some(n => {
      if (n.city !== state.city) return false;
      const pId = getPeriodIdFromDate(n.date);
      return pId === period.id;
    });
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'bread-chip';
    btn.dataset.value = period.id;
    btn.textContent = period.label;
    btn.setAttribute('role', 'radio');
    btn.setAttribute('aria-pressed', 'false');
    if (!hasNotices) {
      btn.disabled = true;
    } else {
      btn.addEventListener('click', () => selectPeriod(period.id));
    }
    periodChips.appendChild(btn);
  }
}

function renderYearChips() {
  yearChips.innerHTML = '';
  const yearLabels = state.notices.map(getYearLabel);
  // Deduplicate while preserving order
  const uniqueYears = [...new Set(yearLabels)];
  for (const yearLabel of uniqueYears) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'bread-chip';
    btn.dataset.value = yearLabel;
    btn.textContent = yearLabel;
    btn.setAttribute('role', 'radio');
    btn.setAttribute('aria-pressed', 'false');
    btn.addEventListener('click', () => selectYear(yearLabel));
    yearChips.appendChild(btn);
  }
}

function updateChipSelection(type, value) {
  const containerMap = {
    region: regionChips,
    city: cityChips,
    period: periodChips,
    year: yearChips,
  };
  const container = containerMap[type];
  if (!container) return;

  for (const btn of container.querySelectorAll('.bread-chip')) {
    const isSelected = btn.dataset.value === value;
    btn.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
  }
}

// ===== Selection handlers =====
function selectRegion(regionId) {
  state.regionId = regionId;
  const region = REGIONS.find(r => r.id === regionId);
  // Select first city with data
  const cityWithData = region.cities.find(c => state.allNotices.some(n => n.city === c));
  state.city = cityWithData || region.cities[0];

  // Select first period with data for that city
  const periodsWithData = PERIODS.filter(p =>
    state.allNotices.some(n => n.city === state.city && getPeriodIdFromDate(n.date) === p.id)
  );
  state.periodId = periodsWithData[0]?.id || 'colonial';

  filterNotices();

  renderCityChips();
  renderPeriodChips();
  renderYearChips();

  updateChipSelection('region', state.regionId);
  updateChipSelection('city', state.city);
  updateChipSelection('period', state.periodId);
  // Select first year/notice
  if (state.notices.length > 0) {
    state.selectedNotice = state.notices[0];
    state.year = getYearLabel(state.notices[0]);
    updateChipSelection('year', state.year);
    renderReceipt();
  } else {
    state.selectedNotice = null;
    state.year = null;
    updateChipSelection('year', null);
    renderReceiptPlaceholder();
  }
}

function selectCity(city) {
  state.city = city;
  // Select first period with data
  const periodsWithData = PERIODS.filter(p =>
    state.allNotices.some(n => n.city === state.city && getPeriodIdFromDate(n.date) === p.id)
  );
  state.periodId = periodsWithData[0]?.id || 'colonial';

  filterNotices();

  renderPeriodChips();
  renderYearChips();

  updateChipSelection('city', state.city);
  updateChipSelection('period', state.periodId);
  // Select first year/notice
  if (state.notices.length > 0) {
    state.selectedNotice = state.notices[0];
    state.year = getYearLabel(state.notices[0]);
    updateChipSelection('year', state.year);
    renderReceipt();
  } else {
    state.selectedNotice = null;
    state.year = null;
    updateChipSelection('year', null);
    renderReceiptPlaceholder();
  }
}

function selectPeriod(periodId) {
  state.periodId = periodId;
  filterNotices();

  renderYearChips();

  updateChipSelection('period', state.periodId);
  // Select first year/notice
  if (state.notices.length > 0) {
    state.selectedNotice = state.notices[0];
    state.year = getYearLabel(state.notices[0]);
    updateChipSelection('year', state.year);
    renderReceipt();
  } else {
    state.selectedNotice = null;
    state.year = null;
    updateChipSelection('year', null);
    renderReceiptPlaceholder();
  }
}

function selectYear(yearLabel) {
  state.year = yearLabel;
  // Find the notice with this year label
  const notice = state.notices.find(n => getYearLabel(n) === yearLabel);
  if (notice) {
    state.selectedNotice = notice;
  }
  updateChipSelection('year', state.year);
  renderReceipt();
  console.log(`Selected notice: ${yearLabel} (${state.selectedNotice?.obs_id})`);
}

// ===== Receipt rendering =====
function renderReceiptPlaceholder() {
  receiptEl.innerHTML = '<div class="bread-receipt__placeholder">Select a notice to see the receipt</div>';
  // Remove region ink border
  receiptEl.style.borderTopColor = '';
}

function renderReceipt() {
  if (!state.selectedNotice) {
    renderReceiptPlaceholder();
    return;
  }

  const n = state.selectedNotice;
  const regionInk = getRegionInkForCity(n.city);
  const yearLabel = getYearLabel(n);

  // Set the region ink border on receipt
  receiptEl.style.borderTopColor = regionInk;

  // Format price per pound
  const usdPerLb = n.usd_per_lb;
  const usdStatus = n.usd_status;
  let pppHtml = '';
  if (usdPerLb !== null && usdPerLb !== undefined) {
    const approx = ['legal_rate', 'provisional_copper'].includes(usdStatus) ? '≈ ' : '';
    const pppValue = `${approx}$${usdPerLb.toFixed(3)} / lb`;
    const noteText = USD_STATUS_NOTES[usdStatus] || usdStatus;
    pppHtml = `
      <div class="bread-receipt__field bread-receipt__ppp">
        <div class="bread-receipt__label">Price per pound</div>
        <div class="bread-receipt__ppp-value">${pppValue}</div>
        <div class="bread-receipt__ppp-note">${noteText}</div>
      </div>
    `;
  } else {
    const noteText = USD_STATUS_NOTES[usdStatus] || usdStatus || 'no dollar rate yet';
    pppHtml = `
      <div class="bread-receipt__field bread-receipt__ppp">
        <div class="bread-receipt__label">Price per pound</div>
        <div class="bread-receipt__ppp-value">no dollar rate yet</div>
        <div class="bread-receipt__ppp-note">${noteText}</div>
      </div>
    `;
  }

  // One coin bought
  let oneCoinHtml = '';
  if (n.weight_oz !== null && n.weight_oz !== undefined && n.price_number !== null && n.price_number !== undefined && n.price_number > 0) {
    const ozPerCoin = (n.weight_oz / n.price_number).toFixed(1);
    const coinWord = COIN_DISPLAY[n.price_unit] || n.price_unit || 'coin';
    oneCoinHtml = `
      <div class="bread-receipt__field bread-receipt__one-coin">
        One ${coinWord} bought ${ozPerCoin} oz of bread
      </div>
    `;
  }

  // Flour section
  let flourHtml = '';
  const flourPrinted = n.flour_price_as_printed;
  const flourSource = n.flour_source;
  const flourNote = n.flour_note;
  const flourLow = n.flour_low_usd_per_barrel;
  const flourHigh = n.flour_high_usd_per_barrel;

  let flourValueText = '';
  if (flourPrinted) {
    flourValueText = flourPrinted;
  }
  if (flourLow !== null && flourLow !== undefined && flourHigh !== null && flourHigh !== undefined) {
    const estText = `Estimated: about $${flourLow}–$${flourHigh} per barrel (1803 rule)`;
    flourValueText = flourValueText ? `${flourValueText}; ${estText}` : estText;
  }
  if (!flourValueText) {
    flourValueText = 'the notice does not print the flour price';
  }

  const sourceWording = FLOUR_SOURCE_WORDING[flourSource] || (flourSource ? flourSource : 'the notice does not print the flour price');

  flourHtml = `
    <div class="bread-receipt__field bread-receipt__flour">
      <div class="bread-receipt__flour-label">Flour</div>
      <div class="bread-receipt__flour-value">${flourValueText}</div>
      <div class="bread-receipt__flour-source">Source of the flour price: ${sourceWording}</div>
      ${flourNote ? `<div class="bread-receipt__flour-note">${flourNote}</div>` : ''}
    </div>
  `;

  // Newspaper and reprints
  const nAppearances = n.n_appearances || 1;
  const firstDate = n.date;
  const lastDate = n.last_date || n.date;
  const firstLabel = getYearLabel({ date: firstDate });
  let lastLabel = '';
  if (lastDate !== firstDate) {
    lastLabel = ` – ${getYearLabel({ date: lastDate })}`;
  }
  const reprintText = nAppearances > 1
    ? `Reprinted ${nAppearances} times, ${firstLabel}${lastLabel}`
    : `Printed once, ${firstLabel}`;

  // Link
  const pdfUrl = n.pdf_url;
  let linkHtml = '';
  if (pdfUrl) {
    linkHtml = `<a class="bread-receipt__link" href="${pdfUrl}" target="_blank" rel="noopener">See the original newspaper page ↗</a>`;
  } else {
    linkHtml = `<span class="bread-receipt__link" style="color: var(--note-grey); pointer-events: none;">no page link</span>`;
  }

  // Bread type line
  let breadTypeHtml = '';
  if (n.bread_type) {
    breadTypeHtml = `<div class="bread-receipt__bread-type">Bread: ${n.bread_type}</div>`;
  }

  // Figure (whole loaf + coin stack)
  const figureHtml = createReceiptFigure(n);

  // Build the receipt HTML
  receiptEl.innerHTML = `
    <div class="bread-receipt__content" data-obs="${n.obs_id}">
      <div class="bread-receipt__header">
        <h2 class="bread-receipt__title" style="color: ${regionInk};">Assize of Bread</h2>
        <p class="bread-receipt__city">${n.city}</p>
      </div>
      <hr class="bread-receipt__divider">
      <div class="bread-receipt__field">
        <div class="bread-receipt__label">Date</div>
        <div class="bread-receipt__value">${yearLabel}</div>
      </div>
      <div class="bread-receipt__field">
        <div class="bread-receipt__label">PRINTED PRICE</div>
        <div class="bread-receipt__price">${n.price_as_printed}</div>
      </div>
      <div class="bread-receipt__field">
        <div class="bread-receipt__label">WEIGHT OF THE LOAF</div>
        <div class="bread-receipt__weight">${n.weight_as_printed}</div>
        ${breadTypeHtml}
      </div>
      <hr class="bread-receipt__divider">
      ${figureHtml}
      <hr class="bread-receipt__divider">
      ${pppHtml}
      ${oneCoinHtml}
      <hr class="bread-receipt__divider">
      ${flourHtml}
      <hr class="bread-receipt__divider">
      <p class="bread-receipt__newspaper">${n.newspaper_title}</p>
      <p class="bread-receipt__reprints">${reprintText}</p>
      ${linkHtml}
      <div class="bread-receipt__obs-id" data-obs="${n.obs_id}">${n.obs_id}</div>
    </div>
  `;
}

function renderShelfPlaceholder() {
  shelfEl.innerHTML = '<div class="bread-shelf__placeholder">Select a notice to see the shelf</div>';
  shelfEl.style.borderTopColor = '';
}

function getRegionInkForCity(city) {
  const regionId = CITY_REGION[city];
  const region = REGIONS.find(r => r.id === regionId);
  return region ? region.ink : '#33404f';
}

// ===== Start =====
document.addEventListener('DOMContentLoaded', init);