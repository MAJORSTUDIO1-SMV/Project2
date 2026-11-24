/* map_projection.js — ONE shared map setup for map_guide.html (tracing guide)
   and the Explorer map (owner's drawing as background + clickable regions).
   Both must use this file so the drawing, the regions and the city dots line up.

   Usage (classic script, after d3 and topojson-client):
     MapProj.load().then(m => { m.states, m.world, m.mainPath, m.insetPath, m.project(city) ... })
*/
(function () {
  const W = 1600, H = 1200;                      // size of the guide PNG and of map_drawing.jpg
  const INSET = { x: 1170, y: 40, w: 390, h: 300 }; // Britain box (top right)
  const FRAME = { west: -92, east: -64, south: 24, north: 47.5 };

  const URLS = {
    states: 'https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json',
    world: 'https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json',
  };

  // State FIPS code -> map group, as in the 1790s (drawn on modern borders)
  const GROUP = {
    // New England (Maine = District of Maine, part of Massachusetts until 1820)
    '09': 'New England', '23': 'New England', '25': 'New England',
    '33': 'New England', '44': 'New England', '50': 'New England',
    // Mid-Atlantic
    '34': 'Mid-Atlantic', '36': 'Mid-Atlantic', '42': 'Mid-Atlantic',
    '10': 'Mid-Atlantic', '24': 'Mid-Atlantic', '11': 'Mid-Atlantic',
    // South (Virginia includes today's West Virginia)
    '51': 'South', '54': 'South', '37': 'South', '45': 'South', '13': 'South',
    // Southern frontier: Kentucky (1792), Tennessee (1796), Mississippi Territory (1798)
    '21': 'South frontier', '47': 'South frontier', '28': 'South frontier', '01': 'South frontier',
    // Northwest Territory
    '39': 'Northwest Territory', '18': 'Northwest Territory', '17': 'Northwest Territory',
    '26': 'Northwest Territory', '55': 'Northwest Territory',
    // Spanish lands
    '12': 'Spanish Florida',
    '22': 'Louisiana', '29': 'Louisiana', '05': 'Louisiana', '19': 'Louisiana', '27': 'Louisiana',
  };
  // Map group -> price region (null = not a price region, drawn neutral)
  const REGION_OF_GROUP = {
    'New England': 'New England', 'Mid-Atlantic': 'Mid-Atlantic',
    'South': 'South', 'South frontier': 'South',
  };
  const GROUP_LABELS = {
    'Northwest Territory': { text: 'Northwest Territory', lonlat: [-86.5, 41.2] },
    'Spanish Florida': { text: 'Spanish Florida', lonlat: [-82.2, 28.6] },
    'Louisiana': { text: 'Louisiana', sub: '(Spanish; French 1800–03)', lonlat: [-91.9, 35.6] },
    'British North America': { text: 'British North America', lonlat: [-77.8, 46.0] },
    'South frontier': { text: 'Frontier', sub: '(Kentucky, Tennessee, Mississippi Terr.)', lonlat: [-86.6, 33.6] },
  };
  // region names sit where they don't cross a border (New England in the sea off Cape Cod)
  const REGION_LABELS = {
    'New England': [-68.0, 40.6],
    'Mid-Atlantic': [-78.2, 41.6],
    'South': [-79.6, 34.4],
  };
  const COLORS = {
    'New England': '#6b4768', 'Mid-Atlantic': '#60867b', 'South': '#c18f38',
    'Britain': '#b25b78', 'Other ports': '#9b8f7a',
  };
  const UK_IDS = ['826', '372']; // United Kingdom, Ireland (ISO 3166 numeric)
  const CANADA_ID = '124';

  const frameShape = {
    type: 'MultiPoint',
    coordinates: [[FRAME.west, FRAME.south], [FRAME.east, FRAME.south],
                  [FRAME.west, FRAME.north], [FRAME.east, FRAME.north]],
  };
  const mainProj = d3.geoConicConformal().parallels([30, 45]).rotate([80, 0])
    .fitExtent([[30, 30], [W - 30, H - 30]], frameShape);
  const mainPath = d3.geoPath(mainProj);

  function inFrame(xy) {
    return xy && xy[0] >= 0 && xy[0] <= W && xy[1] >= 0 && xy[1] <= H &&
      !(xy[0] >= INSET.x && xy[0] <= INSET.x + INSET.w && xy[1] >= INSET.y && xy[1] <= INSET.y + INSET.h);
  }

  let cache = null;
  function load() {
    if (cache) return cache;
    cache = Promise.all([d3.json(URLS.states), d3.json(URLS.world)]).then(([us, world]) => {
      const states = topojson.feature(us, us.objects.states).features;
      for (const f of states) {
        f.group = GROUP[f.id] || 'Other land';
        f.region = REGION_OF_GROUP[f.group] || null;
      }
      const countries = topojson.feature(world, world.objects.countries).features;
      const uk = { type: 'FeatureCollection', features: countries.filter(c => UK_IDS.includes(String(c.id))) };
      const insetProj = d3.geoMercator().fitExtent(
        [[INSET.x + 20, INSET.y + 40], [INSET.x + INSET.w - 20, INSET.y + INSET.h - 20]], uk);
      const insetPath = d3.geoPath(insetProj);

      // borders between different groups (strong) and inside a group (faint);
      // no border between Virginia and West Virginia (one state then)
      const vaWv = (a, b) => (a.id === '51' && b.id === '54') || (a.id === '54' && b.id === '51');
      // strong line only where it means something in the 1790s: around the price regions
      // and along the Mississippi (Northwest Territory | Louisiana). Modern borders = faint dashes.
      const g = f => GROUP[f.id] || 'Other land';
      const isRegion = f => !!REGION_OF_GROUP[g(f)];
      const mississippi = (a, b) => (g(a) === 'Northwest Territory' && g(b) === 'Louisiana') ||
                                    (g(b) === 'Northwest Territory' && g(a) === 'Louisiana') ||
                                    (g(a) === 'South frontier' && g(b) === 'Louisiana') ||
                                    (g(b) === 'South frontier' && g(a) === 'Louisiana');
      const strong = (a, b) => a !== b && g(a) !== g(b) && (isRegion(a) || isRegion(b) || mississippi(a, b));
      const groupBorders = topojson.mesh(us, us.objects.states, strong);
      const innerBorders = topojson.mesh(us, us.objects.states,
        (a, b) => a !== b && !strong(a, b) && !vaWv(a, b));

      function project(city) {
        if (!city || city.lat == null || city.lon == null) return null;
        if (city.region === 'Britain') return insetProj([city.lon, city.lat]);
        const xy = mainProj([city.lon, city.lat]);
        return inFrame(xy) ? xy : null;
      }
      return {
        W, H, INSET, COLORS, GROUP_LABELS, REGION_LABELS,
        states, countries, uk, canada: countries.find(c => String(c.id) === CANADA_ID),
        groupBorders, innerBorders, mainProj, mainPath, insetProj, insetPath, project,
      };
    });
    return cache;
  }

  window.MapProj = { W, H, INSET, FRAME, URLS, GROUP, REGION_OF_GROUP, COLORS, mainProj, mainPath, load };
})();
