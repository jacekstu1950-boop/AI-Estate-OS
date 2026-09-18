const money = new Intl.NumberFormat('pl-PL', {style:'currency', currency:'PLN'});
const number = new Intl.NumberFormat('pl-PL', {maximumFractionDigits:2});
let apartments = [];
const el = id => document.getElementById(id);

function valNum(id) {
  const v = el(id).value.trim();
  return v === '' ? null : Number(v);
}

function uniqueSorted(values) {
  return [...new Set(values.filter(v => v !== null && v !== undefined))]
    .sort((a,b) => Number(a) - Number(b));
}

function populate(id, values) {
  const select = el(id);
  const first = select.options[0].outerHTML;
  select.innerHTML = first + values.map(v =>
    '<option value="' + String(v) + '">' + String(v) + '</option>'
  ).join('');
}

function filteredRecords() {
  const code = el('searchCode').value.trim().toUpperCase();
  const rooms = el('filterRooms').value;
  const floor = el('filterFloor').value;
  const availability = el('filterAvailability').value;
  const areaMin = valNum('areaMin');
  const areaMax = valNum('areaMax');
  const priceMin = valNum('priceMin');
  const priceMax = valNum('priceMax');

  const rows = apartments.filter(item => {
    if (code && !String(item.apartment_code || '').toUpperCase().includes(code)) return false;
    if (rooms && String(item.rooms) !== rooms) return false;
    if (floor && String(item.floor) !== floor) return false;
    if (availability && String(item.availability) !== availability) return false;
    if (areaMin !== null && Number(item.area_m2) < areaMin) return false;
    if (areaMax !== null && Number(item.area_m2) > areaMax) return false;
    if (priceMin !== null && Number(item.price_pln) < priceMin) return false;
    if (priceMax !== null && Number(item.price_pln) > priceMax) return false;
    return true;
  });

  const sortBy = el('sortBy').value;
  rows.sort((a,b) => {
    if (sortBy === 'priceAsc') return Number(a.price_pln) - Number(b.price_pln);
    if (sortBy === 'priceDesc') return Number(b.price_pln) - Number(a.price_pln);
    if (sortBy === 'areaAsc') return Number(a.area_m2) - Number(b.area_m2);
    if (sortBy === 'areaDesc') return Number(b.area_m2) - Number(a.area_m2);
    if (sortBy === 'ppmAsc') return Number(a.price_per_m2_pln) - Number(b.price_per_m2_pln);
    return String(a.apartment_code).localeCompare(String(b.apartment_code), 'pl');
  });

  return rows;
}

function renderRows() {
  const rows = filteredRecords();
  el('resultsCount').textContent = 'Znaleziono: ' + rows.length + ' z ' + apartments.length;
  el('rows').innerHTML = rows.map(item => '<tr>' +
    '<td><strong>' + item.apartment_code + '</strong></td>' +
    '<td>' + (item.building ?? '') + '</td>' +
    '<td>' + (item.floor ?? '') + '</td>' +
    '<td>' + (item.rooms ?? '') + '</td>' +
    '<td>' + number.format(item.area_m2) + ' m²</td>' +
    '<td>' + money.format(item.price_pln) + '</td>' +
    '<td>' + money.format(item.price_per_m2_pln) + '</td>' +
    '<td>' + item.availability + '</td>' +
    '<td><a href="' + item.source_url + '" target="_blank" rel="noopener">Skanska</a></td>' +
  '</tr>').join('');
  el('emptyState').hidden = rows.length !== 0;
}

function bindFilters() {
  ['searchCode','filterRooms','filterFloor','filterAvailability','areaMin','areaMax','priceMin','priceMax','sortBy']
    .forEach(id => {
      el(id).addEventListener('input', renderRows);
      el(id).addEventListener('change', renderRows);
    });

  el('resetFilters').addEventListener('click', () => {
    ['searchCode','filterRooms','filterFloor','filterAvailability','areaMin','areaMax','priceMin','priceMax']
      .forEach(id => el(id).value = '');
    el('sortBy').value = 'code';
    renderRows();
  });
}

async function load() {
  const status = el('status');
  try {
    const [latestRes, changesRes] = await Promise.all([
      fetch('/api/skanska/stilla/latest'),
      fetch('/api/skanska/stilla/changes')
    ]);
    if (!latestRes.ok) throw new Error('Błąd endpointu latest: ' + latestRes.status);
    if (!changesRes.ok) throw new Error('Błąd endpointu changes: ' + changesRes.status);

    const latest = await latestRes.json();
    const changes = await changesRes.json();
    apartments = latest.records || [];

    status.innerHTML = '<span class="ok">API i dane działają poprawnie.</span>';
    el('summary').innerHTML =
      '<div class="card"><strong>Deweloper</strong><br>' + latest.developer + '</div>' +
      '<div class="card"><strong>Projekt</strong><br>' + latest.project + '</div>' +
      '<div class="card"><strong>Liczba lokali</strong><br>' + latest.count + '</div>' +
      '<div class="card"><strong>Verified PASS</strong><br>' + latest.verified_pass_count + '</div>' +
      '<div class="card"><strong>Prawa do 2D</strong><br><span class="warn">' + latest.floorplan_rights_status + '</span></div>';

    populate('filterRooms', uniqueSorted(apartments.map(x => x.rooms)));
    populate('filterFloor', uniqueSorted(apartments.map(x => x.floor)));

    const av = [...new Set(apartments.map(x => x.availability).filter(Boolean))].sort();
    el('filterAvailability').innerHTML = '<option value="">Wszystkie</option>' +
      av.map(v => '<option value="' + v + '">' + v + '</option>').join('');

    renderRows();

    const s = changes.summary || {};
    el('changes').innerHTML =
      'ADDED: <strong>' + (s.ADDED ?? 0) + '</strong> | ' +
      'REMOVED: <strong>' + (s.REMOVED ?? 0) + '</strong> | ' +
      'CHANGED: <strong>' + (s.CHANGED ?? 0) + '</strong> | ' +
      'UNCHANGED: <strong>' + (s.UNCHANGED ?? 0) + '</strong>';
  } catch (err) {
    status.innerHTML = '<span class="error">' + err.message + '</span>';
  }
}

bindFilters();
load();
