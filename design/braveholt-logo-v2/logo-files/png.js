const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs'); const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  fs.mkdirSync(__dirname + '/out/png', { recursive: true });
  const jobs = [];
  for (const f of fs.readdirSync(__dirname + '/out/svg')) {
    const svg = fs.readFileSync(__dirname + '/out/svg/' + f, 'utf8');
    const vb = svg.match(/viewBox="([^"]+)"/)[1].split(/\s+/).map(Number); const ar = vb[2] / vb[3];
    let sizes;
    if (f.includes('app-icon-small')) sizes = [[48, 48], [32, 32], [16, 16]];
    else if (f.includes('app-icon')) sizes = [[1024, 1024], [512, 512], [180, 180]];
    else if (f.includes('mark')) sizes = [[Math.round(1024 * ar), 1024], [Math.round(256 * ar), 256]];
    else if (f.includes('horizontal')) sizes = [[2400, Math.round(2400 / ar)], [800, Math.round(800 / ar)]];
    else sizes = [[1600, Math.round(1600 / ar)], [600, Math.round(600 / ar)]];
    for (const [w, h] of sizes) jobs.push([f, svg, w, h]);
  }
  for (const [f, svg, w, h] of jobs) {
    await p.setViewportSize({ width: w, height: h });
    await p.setContent(`<html><body style="margin:0;background:transparent">${svg.replace('<svg ', `<svg width="${w}" height="${h}" style="display:block" `)}</body></html>`);
    const out = __dirname + '/out/png/' + f.replace('.svg', `-${f.includes('app-icon') ? w : (f.includes('mark') ? h : w)}px.png`);
    await p.screenshot({ path: out, omitBackground: true });
  }
  await b.close(); console.log(jobs.length, 'pngs');
})();
