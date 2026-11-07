// Read the original dashboard; execute its functions without browser/UI side effects.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'dashboard/index.html'), 'utf8');
function section(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  if (a < 0 || b < 0) throw new Error(`Dashboard source boundary missing: ${start}`);
  return source.slice(a, b);
}
const context = vm.createContext({});
vm.runInContext([
  section('const CUST =', '// ---------------------------------------------------------------- promises'),
  section('const ATTR_ITEMS =', 'function renderAttrTable()'),
  section('const NCA =', 'const NCA_DROPPED'),
  section('const qState =', 'function renderQuad()'),
  section('const E2E =', 'function renderPlanAB()'),
].join('\n'), context);
const options = JSON.parse(process.argv[2] || '{}');
context.options = options;
const result = vm.runInContext(`(() => {
  fillAttrDefaults(); syncRel();
  const ev = evaluate();
  const o = {...E2E, ...options};
  const economy = programEcon(ev, o);
  const stress = programEcon(ev, o, 1.5);
  // Execute the original chart block, including its seasonal weights and cash timing.
  return {ev, economy, stress, loyalty: loyalty(ev), data: {
    customers: CUST, flags: FLAGS, uncertainty: UNC, indicators: IND,
    attributes: ATTR, attribute_items: ATTR_ITEMS,
    benefits: TIER_BEN, growth: GROWTH, unit: UNIT
  }};
})()`, context);
// The chart loop and break-even expression are evaluated verbatim from renderE2E.
context.width = () => 800;
context.$ = () => ({});
context.dec = n => String(n);
vm.runInContext('fillAttrDefaults(); syncRel(); var ev = evaluate(); Object.assign(E2E, options);', context);
const chart = section('  // 52-week chart', '  const all = series.flatMap');
const chartResult = vm.runInContext(`(() => {${chart}; return series;})()`, context);
const breakEven = section('  const beImpact =', '  $("#e2eInsight")');
result.series = chartResult;
result.break_even_impact = vm.runInContext(`(() => {${breakEven}; return beImpact;})()`, context);
// Capture the source grid's actual pos/n loop, with a minimal DOM stand-in.
// Observe each computed cell without changing the source calculations.
const grid = section('  // 108-run grid', '  const beImpact =').replace(
  'n++;',
  'n++; cells.push({impact:i[0], margin:m[0], rebate_multiplier:r[0]/0.01, opportunity_cost:o[0], net:v});'
);
result.grid = vm.runInContext(`(() => {const cells = []; ${grid}; return {positive: pos, runs: n, cells};})()`, context);
console.log(JSON.stringify(result));
