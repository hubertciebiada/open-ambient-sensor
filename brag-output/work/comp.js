/* OAS brag video — every frame is a pure function of t (seconds). */
(async function () {
  const W = 1920, H = 1080;
  const D = window.DATA;
  const $ = (id) => document.getElementById(id);
  const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
  const lerp = (a, b, t) => a + (b - a) * t;
  const P = (t, t0, d) => clamp((t - t0) / d);
  const E = {
    out3: (t) => 1 - Math.pow(1 - t, 3),
    out4: (t) => 1 - Math.pow(1 - t, 4),
    in2: (t) => t * t,
    in3: (t) => t * t * t,
    inOut3: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    inOutSine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
    outBack: (t) => { const c1 = 1.4, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
  };
  const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
  // Closed-form damped springs: a pure function of t, so seek(t) stays deterministic.
  // [frequency Hz, damping ratio]: snappy/ui overshoot a hair (UI), def/heavy/type never do.
  const SPR = { snappy: [2.4, 0.68], ui: [1.9, 0.78], def: [1.5, 0.9], heavy: [1.05, 1.0], type: [1.8, 1.0] };
  function spr(t, t0, kind) {
    const x = t - t0; if (x <= 0) return 0;
    const [f, z] = SPR[kind], w = 2 * Math.PI * f;
    if (z < 1) { const wd = w * Math.sqrt(1 - z * z); return 1 - Math.exp(-z * w * x) * (Math.cos(wd * x) + (z * w / wd) * Math.sin(wd * x)); }
    return 1 - Math.exp(-w * x) * (1 + w * x);
  }

  // ---- timeline (seconds) ----------------------------------------------------
  const TB = 3.0, TC = 7.5, TD = 12.0, TE = 16.5;
  const BEAT = 0.5625; // 106.67 bpm from the reveal on
  const PASS_T = TD + 5.5 * BEAT; // 15.094: "Total: 35/35 PASS"

  // ---- firmware logic (packages/leds.yaml + air-quality.yaml) ----------------
  // AQI Breathing: raised cosine over 4 s in perceived brightness, gamma 2.8,
  // trough at 20 % of the peak LED output.
  const P_LO = Math.pow(0.2, 1 / 2.8);
  function breathK(t) {
    const s = 0.5 - 0.5 * Math.cos((2 * Math.PI * (((t + 0.4) % 4) + 4) % 4) / 4);
    return Math.pow(P_LO + (1 - P_LO) * s, 2.8); // LED output relative to peak
  }
  const STOPS = [[0, 0, 255, 0], [50, 0, 255, 0], [100, 255, 255, 0], [150, 255, 128, 0], [200, 255, 0, 0], [300, 160, 0, 200], [500, 130, 0, 30]];
  function aqiColor(aqi) {
    aqi = clamp(aqi, 0, 500);
    for (let i = 1; i < STOPS.length; i++) {
      if (aqi <= STOPS[i][0]) {
        const a = STOPS[i - 1], b = STOPS[i], t = (aqi - a[0]) / (b[0] - a[0]);
        return [Math.floor(a[1] + t * (b[1] - a[1])), Math.floor(a[2] + t * (b[2] - a[2])), Math.floor(a[3] + t * (b[3] - a[3]))];
      }
    }
    return [130, 0, 30];
  }
  function co2Aqi(c) {
    if (c <= 800) return 50 * c / 800;
    if (c <= 1000) return 51 + 49 * (c - 800.1) / 199.9;
    if (c <= 1500) return 101 + 99 * (c - 1000.1) / 499.9;
    if (c <= 2000) return 201 + 99 * (c - 1500.1) / 499.9;
    return 301 + 199 * (c - 2000.1) / 2999.9;
  }
  const PM25 = 4, PM_AQI = 50 * PM25 / 12;

  function rgbHue(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    if (d === 0) return 0;
    let h;
    if (mx === r) h = ((g - b) / d) % 6; else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4;
    return (h * 60 + 360) % 360;
  }
  const PHOTO_HUE = 161; // measured: median hue of the lit pixels in the real photo
  function displayHue(fwHue) { // firmware green (120°) shows as the photo's own mint
    return fwHue + (PHOTO_HUE - 120) * Math.pow(clamp(fwHue / 120), 3);
  }
  function hsv2rgb(h, s, v) {
    h = ((h % 360) + 360) % 360 / 60;
    const i = Math.floor(h), f = h - i, p = v * (1 - s), q = v * (1 - s * f), u = v * (1 - s * (1 - f));
    switch (i) { case 0: return [v, u, p]; case 1: return [q, v, p]; case 2: return [p, v, u]; case 3: return [p, q, v]; case 4: return [u, p, v]; default: return [v, p, q]; }
  }

  // ---- assets --------------------------------------------------------------
  function loadImg(src) {
    return new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = src; });
  }
  const [photo, render] = await Promise.all([loadImg("photo-ring.jpg"), loadImg("render-top.png")]);
  await Promise.all([photo.decode(), render.decode()]);
  await Promise.all([
    document.fonts.load('640 104px "InterV"'), document.fonts.load('430 38px "InterV"'),
    document.fonts.load('400 21px "JBM"'), document.fonts.load('500 21px "JBM"'), document.fonts.load('700 21px "JBM"'),
  ]);
  await document.fonts.ready;

  const cv = $("cv"), ctx = cv.getContext("2d");

  // ---- grain (static, seeded) -------------------------------------------------
  {
    const g = $("grain").getContext("2d"), id = g.createImageData(W, H);
    let s = 1234567;
    for (let i = 0; i < W * H; i++) {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      const v = 128 + ((s >> 8) % 110) - 55;
      id.data[i * 4] = id.data[i * 4 + 1] = id.data[i * 4 + 2] = v; id.data[i * 4 + 3] = 255;
    }
    g.putImageData(id, 0, 0);
  }

  // ---- photo: HSV planes + feathered alpha -------------------------------------
  // processing size; LED-ring centre (the drawing anchor); cover centre + radius (perspective puts
  // the domed centre a little right of the rim's centre) -- all fractions of the photo, measured
  const PS = 1000, RC = 0.525, RCPY = 0.535, CCX = 0.504, CCY = 0.533, CR = 0.293;
  const phH = new Float32Array(PS * PS), phS = new Float32Array(PS * PS), phV = new Float32Array(PS * PS), phA = new Uint8ClampedArray(PS * PS);
  {
    const c = document.createElement("canvas"); c.width = c.height = PS;
    const x = c.getContext("2d"); x.drawImage(photo, 0, 0, PS, PS);
    const d = x.getImageData(0, 0, PS, PS).data;
    const BL = 0.055;
    for (let y = 0; y < PS; y++) for (let xx = 0; xx < PS; xx++) {
      const i = y * PS + xx;
      let r = Math.max(0, (d[i * 4] / 255 - BL) / (1 - BL)), g = Math.max(0, (d[i * 4 + 1] / 255 - BL) / (1 - BL)), b = Math.max(0, (d[i * 4 + 2] / 255 - BL) / (1 - BL));
      const mx = Math.max(r, g, b), mn = Math.min(r, g, b), dd = mx - mn;
      let h = 0;
      if (dd > 0) { if (mx === r) h = ((g - b) / dd) % 6; else if (mx === g) h = (b - r) / dd + 2; else h = (r - g) / dd + 4; h = (h * 60 + 360) % 360; }
      phH[i] = h; phS[i] = (mx > 0 ? dd / mx : 0) * smooth(0.06, 0.3, mx); phV[i] = mx;
      const rr = Math.hypot(xx / PS - CCX, y / PS - CCY);
      phA[i] = Math.round(255 * (1 - smooth(0.33, 0.47, rr)));
    }
  }
  const phCan = document.createElement("canvas"); phCan.width = phCan.height = PS;
  const phCtx = phCan.getContext("2d"), phImg = phCtx.createImageData(PS, PS);
  let phKey = "";
  function photoFrame(dh, gain, sat) {
    const key = dh.toFixed(2) + "|" + gain.toFixed(3) + "|" + sat.toFixed(3);
    if (key === phKey) return phCan;
    phKey = key;
    const o = phImg.data;
    const wSpread = clamp(Math.abs(dh) / 25);
    for (let i = 0; i < PS * PS; i++) {
      const v = Math.min(1, phV[i] * gain);
      const s = Math.min(1, phS[i] * sat);
      let h;
      if (wSpread > 0) {
        let dev = phH[i] - PHOTO_HUE; dev -= 360 * Math.round(dev / 360);
        const hs = PHOTO_HUE + dh + Math.max(-40, Math.min(40, dev)) * 0.25;
        h = (phH[i] + dh) * (1 - wSpread) + hs * wSpread;
      } else h = phH[i] + dh;
      h = (((h / 60) % 6) + 6) % 6;
      const k = Math.floor(h), f = h - k, p = v * (1 - s), q = v * (1 - s * f), u = v * (1 - s * (1 - f));
      let r, g, b;
      switch (k) { case 0: r = v; g = u; b = p; break; case 1: r = q; g = v; b = p; break; case 2: r = p; g = v; b = u; break; case 3: r = p; g = q; b = v; break; case 4: r = u; g = p; b = v; break; default: r = v; g = p; b = q; }
      o[i * 4] = r * 255; o[i * 4 + 1] = g * 255; o[i * 4 + 2] = b * 255; o[i * 4 + 3] = phA[i];
    }
    phCtx.putImageData(phImg, 0, 0);
    return phCan;
  }
  function drawPhoto(can, cx, cy, size, alpha) {
    if (alpha <= 0) return;
    ctx.save(); ctx.globalAlpha = alpha;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(can, cx - RC * size, cy - RCPY * size, size, size);
    ctx.restore();
  }
  function bloom(cx, cy, rad, rgb, a) {
    if (a <= 0) return;
    ctx.save(); ctx.globalCompositeOperation = "screen";
    const g = ctx.createRadialGradient(cx, cy, rad * 0.15, cx, cy, rad);
    g.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${0.55 * a})`);
    g.addColorStop(0.45, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${0.18 * a})`);
    g.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
    ctx.fillStyle = g; ctx.fillRect(cx - rad, cy - rad, rad * 2, rad * 2);
    ctx.restore();
  }

  // ---- board render (KiCad 3D top view) masked to the real D-shape ---------------
  const RS = 12.858, RX0 = 12, RY0 = 119, RCX = 771.5, RCY = 771.5; // render px/mm, crop, centre in crop
  const BW = 1544, BH = 1332;
  const boardCan = document.createElement("canvas"); boardCan.width = BW; boardCan.height = BH;
  const DA0 = Math.atan2(43.498, -41.327), DA1 = Math.atan2(43.498, 41.327);
  function dShape(c, cx, cy, s, inset) {
    c.beginPath(); c.arc(cx, cy, (60 - inset) * s, DA0, DA1 + 2 * Math.PI, false); c.closePath();
  }
  function rrect(c, x0, y0, x1, y1, r) { c.beginPath(); c.roundRect(x0, y0, x1 - x0, y1 - y0, r); }
  const HOLES = [];
  for (const f of D.footprints) for (const p of f.pads) if (p.type === "np_thru_hole") HOLES.push([p.x, p.y, p.w / 2]);
  function punchHoles(c, cx, cy, s, grow) {
    c.save(); c.globalCompositeOperation = "destination-out"; c.fillStyle = "#000";
    rrect(c, cx + (20.5 - grow) * s, cy + (-33.95 - grow) * s, cx + (47.85 + grow) * s, cy + (23.0 + grow) * s, (1.5 + grow) * s); c.fill();
    rrect(c, cx + (24.7 - grow) * s, cy + (28 - grow) * s, cx + (29.7 + grow) * s, cy + (39 + grow) * s, (1.5 + grow) * s); c.fill();
    c.beginPath(); c.arc(cx, cy, (5 + grow) * s, 0, 2 * Math.PI); c.fill();
    for (const [x, y, r] of HOLES) { c.beginPath(); c.arc(cx + x * s, cy + y * s, (r + grow) * s, 0, 2 * Math.PI); c.fill(); }
    c.restore();
  }
  {
    const b = boardCan.getContext("2d");
    b.save(); dShape(b, RCX, RCY, RS, 0.12); b.clip();
    b.drawImage(render, RX0, RY0, BW, BH, 0, 0, BW, BH);
    b.restore();
    punchHoles(b, RCX, RCY, RS, 0.12);
  }
  const sweepCan = document.createElement("canvas"); sweepCan.width = BW; sweepCan.height = BH;
  const sweepCtx = sweepCan.getContext("2d");

  // board -> stage transform used by scene B (and the B->C zoom)
  let BT = { cx: 1320, cy: 600, s: 7.0, rot: 0 };
  const b2s = (x, y) => {
    const c = Math.cos(BT.rot), sn = Math.sin(BT.rot);
    return [BT.cx + (x * c - y * sn) * BT.s, BT.cy + (x * sn + y * c) * BT.s];
  };

  // ---- module ghost outlines (F.Fab of the mech-ref footprints) --------------------
  const FAB = {};
  for (const f of D.footprints) if (f.fab && f.fab.length) FAB[f.ref] = f.fab;
  function arcPts(a, m, b, n = 24) {
    const [x1, y1] = a, [x2, y2] = m, [x3, y3] = b;
    const d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2));
    const ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / d;
    const uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / d;
    const r = Math.hypot(x1 - ux, y1 - uy);
    const a1 = Math.atan2(y1 - uy, x1 - ux), a2 = Math.atan2(y2 - uy, x2 - ux), a3 = Math.atan2(y3 - uy, x3 - ux);
    const norm = (v) => ((v % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
    let d13 = norm(a3 - a1); const d12 = norm(a2 - a1);
    if (d12 > d13) d13 -= 2 * Math.PI;
    const pts = [];
    for (let i = 0; i <= n; i++) pts.push([ux + r * Math.cos(a1 + d13 * i / n), uy + r * Math.sin(a1 + d13 * i / n)]);
    return pts;
  }
  function fabPaths(ref) {
    const out = [];
    for (const g of FAB[ref] || []) {
      if (g.t === "poly") out.push(g.closed ? [...g.pts, g.pts[0]] : g.pts);
      else if (g.t === "arc") out.push(arcPts(g.a, g.m, g.b));
      else if (g.t === "circle") { const pts = []; for (let i = 0; i <= 20; i++) pts.push([g.c[0] + g.r * Math.cos(i / 20 * 2 * Math.PI), g.c[1] + g.r * Math.sin(i / 20 * 2 * Math.PI)]); out.push(pts); }
    }
    return out;
  }
  const GHOST = { SENS1: fabPaths("SENS1").slice(0, 1), LDR1: fabPaths("LDR1"), MOD1: fabPaths("MOD1").filter((p) => p.length !== 21) };
  function drawGhost(ref, p, alpha) {
    if (p <= 0 || alpha <= 0) return;
    ctx.save(); ctx.globalAlpha = alpha; ctx.strokeStyle = "#5cffa8"; ctx.lineWidth = 2; ctx.lineJoin = "round";
    const paths = GHOST[ref];
    let total = 0; const lens = paths.map((pts) => { let l = 0; for (let i = 1; i < pts.length; i++) l += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); total += l; return l; });
    let budget = total * p;
    ctx.setLineDash([7, 6]);
    paths.forEach((pts, k) => {
      if (budget <= 0) return;
      const take = Math.min(budget, lens[k]); budget -= take;
      ctx.beginPath(); let acc = 0; let [px, py] = b2s(...pts[0]); ctx.moveTo(px, py);
      for (let i = 1; i < pts.length; i++) {
        const seg = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
        if (acc + seg >= take) { const f = (take - acc) / seg; const q = b2s(lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)); ctx.lineTo(q[0], q[1]); break; }
        acc += seg; const q = b2s(...pts[i]); ctx.lineTo(q[0], q[1]);
      }
      ctx.stroke();
    });
    ctx.restore();
  }

  // LED ring (real footprint positions; SK6812-SIDE emits radially outward)
  const LEDS = D.footprints.filter((f) => /^D1[1-8]$/.test(f.ref)).map((f) => ({ x: f.x, y: f.y, rot: f.rot }));
  function drawBoardLeds(k, alpha, rgb) {
    if (alpha <= 0) return;
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    for (const L of LEDS) {
      const [sx, sy] = b2s(L.x, L.y);
      const ang = Math.atan2(L.y, L.x) + BT.rot;
      const ex = sx + Math.cos(ang) * 2.2 * BT.s, ey = sy + Math.sin(ang) * 2.2 * BT.s;
      const rad = 7.5 * BT.s * (0.6 + 0.4 * k);
      const g = ctx.createRadialGradient(ex, ey, 0, ex, ey, rad);
      g.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${0.75 * alpha * (0.35 + 0.65 * k)})`);
      g.addColorStop(0.3, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${0.22 * alpha * (0.35 + 0.65 * k)})`);
      g.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
      ctx.fillStyle = g; ctx.fillRect(ex - rad, ey - rad, rad * 2, rad * 2);
    }
    ctx.restore();
  }

  // ---- blueprint (scene D): real Edge.Cuts, pads, tracks, vias -----------------------
  // the D outline sweeps as one stroke (arc over the top, then the chord); the cut-outs follow
  const isRim = (o) => (o.t === "arc" && o.a[1] > 40) || (o.t === "line" && o.a[1] > 40 && o.b[1] > 40);
  const rimArc = D.outline.find((o) => o.t === "arc" && o.a[1] > 40), rimChord = D.outline.find((o) => o.t === "line" && o.a[1] > 40 && o.b[1] > 40);
  const rimPath = [...arcPts(rimArc.a, rimArc.m, rimArc.b, 180), rimChord.b];
  const outlinePaths = D.outline.filter((o) => !isRim(o)).map((o) => {
    if (o.t === "line") return [o.a, o.b];
    if (o.t === "arc") return arcPts(o.a, o.m, o.b, 12);
    const pts = []; for (let i = 0; i <= 48; i++) pts.push([o.c[0] + o.r * Math.cos(i / 48 * 2 * Math.PI), o.c[1] + o.r * Math.sin(i / 48 * 2 * Math.PI)]); return pts;
  });
  const PADS = [];
  for (const f of D.footprints) for (const p of f.pads) PADS.push(p);
  PADS.forEach((p) => { p.key = p.x * 0.8 + p.y * 0.35; });
  const padOrder = [...PADS].sort((a, b) => a.key - b.key);
  padOrder.forEach((p, i) => { p.t0 = TD + 0.32 + (i / padOrder.length) * 0.95; });
  // tracks: nets start staggered left -> right; each net routes itself end to end
  const NETS = D.nets;
  NETS.forEach((n, i) => {
    let len = 0; n.segs.forEach((s) => { s.len = Math.hypot(s.b[0] - s.a[0], s.b[1] - s.a[1]); len += s.len; });
    const speed = Math.max(90, len / 1.05);
    let t = TD + 0.62 + (i / NETS.length) * 1.55;
    n.segs.forEach((s) => { s.t0 = t; s.t1 = t + Math.max(0.012, s.len / speed); t = s.t1; });
    n.t1 = t;
  });
  const VIAS = D.vias.map((v, i) => ({ ...v, t0: v.seg_i >= 0 ? NETS[v.net_i].segs[v.seg_i].t1 : TD + 2.2 + i * 0.03 }));

  function drawBlueprint(t, cx, cy, s, alpha, glowBoost) {
    if (alpha <= 0) return;
    const X = (x) => cx + x * s, Y = (y) => cy + y * s;
    ctx.save(); ctx.globalAlpha = alpha;
    // substrate
    const fillA = smooth(TD + 0.35, TD + 0.9, t);
    if (fillA > 0) {
      ctx.save(); ctx.globalAlpha = alpha * fillA;
      dShape(ctx, cx, cy, s, 0); ctx.fillStyle = "#0c1512"; ctx.fill();
      ctx.restore();
      ctx.save(); punchHoles(ctx, cx, cy, s, 0); ctx.restore();
      // punchHoles cut through the background too: repaint it inside the holes
      ctx.save(); ctx.globalCompositeOperation = "destination-over"; ctx.fillStyle = "#070b09"; ctx.fillRect(0, 0, W, H); ctx.restore();
    }
    // outline, drawn on
    const pRim = E.inOut3(P(t, TD - 0.24, 0.86)), pCut = E.inOut3(P(t, TD + 0.3, 0.5));
    const cool = smooth(TD + 0.5, TD + 1.1, t);
    ctx.lineJoin = "round"; ctx.lineCap = "round";
    for (const pts of [rimPath, ...outlinePaths]) {
      const po = pts === rimPath ? pRim : pCut;
      ctx.save();
      if (pts === rimPath && cool < 1) {
        ctx.strokeStyle = `rgba(${lerp(92, 190, cool)},${lerp(255, 204, cool)},${lerp(168, 197, cool)},0.95)`;
        ctx.lineWidth = lerp(3.2, 1.6, cool); ctx.shadowColor = `rgba(92,255,168,${0.95 * (1 - cool)})`; ctx.shadowBlur = 20 * (1 - cool);
      } else { ctx.strokeStyle = "rgba(190,204,197,0.85)"; ctx.lineWidth = 1.6; }
      let len = 0; for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      const take = len * po; if (take <= 0) continue;
      ctx.beginPath(); ctx.moveTo(X(pts[0][0]), Y(pts[0][1])); let acc = 0;
      for (let i = 1; i < pts.length; i++) {
        const seg = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
        if (acc + seg >= take) { const f = (take - acc) / seg; ctx.lineTo(X(lerp(pts[i - 1][0], pts[i][0], f)), Y(lerp(pts[i - 1][1], pts[i][1], f))); break; }
        acc += seg; ctx.lineTo(X(pts[i][0]), Y(pts[i][1]));
      }
      ctx.stroke();
      ctx.restore();
    }
    // pads
    for (const p of PADS) {
      const q = E.outBack(P(t, p.t0, 0.22)); if (q <= 0) continue;
      ctx.save(); ctx.translate(X(p.x), Y(p.y)); ctx.rotate(-p.rot * Math.PI / 180); ctx.scale(q, q);
      const w = p.w * s, h = p.h * s;
      if (p.type === "np_thru_hole") {
        ctx.beginPath(); ctx.arc(0, 0, w / 2, 0, 2 * Math.PI); ctx.strokeStyle = "rgba(190,204,197,0.7)"; ctx.lineWidth = 1.4; ctx.stroke();
      } else {
        ctx.fillStyle = p.type === "thru_hole" ? "rgba(232,214,190,0.92)" : "rgba(222,230,226,0.9)";
        ctx.beginPath();
        if (p.shape === "circle") ctx.arc(0, 0, w / 2, 0, 2 * Math.PI);
        else if (p.shape === "oval") ctx.roundRect(-w / 2, -h / 2, w, h, Math.min(w, h) / 2);
        else if (p.shape === "roundrect") ctx.roundRect(-w / 2, -h / 2, w, h, Math.min(w, h) * 0.25);
        else ctx.rect(-w / 2, -h / 2, w, h);
        ctx.fill();
        if (p.drill) { ctx.beginPath(); ctx.arc(0, 0, (p.drill / 2) * s, 0, 2 * Math.PI); ctx.fillStyle = "#070b09"; ctx.fill(); }
      }
      ctx.restore();
    }
    // tracks: glow pass + core pass
    const drawn = [];
    for (const n of NETS) for (const sg of n.segs) {
      const q = P(t, sg.t0, sg.t1 - sg.t0); if (q <= 0) continue;
      drawn.push([sg, q]);
    }
    const col = { F: [255, 154, 77], B: [77, 168, 255] };
    ctx.save(); ctx.globalCompositeOperation = "lighter"; ctx.lineCap = "round";
    for (const [sg, q] of drawn) {
      const c = col[sg.l];
      ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${0.13 * glowBoost})`; ctx.lineWidth = 7 + 4 * (glowBoost - 1);
      ctx.beginPath(); ctx.moveTo(X(sg.a[0]), Y(sg.a[1])); ctx.lineTo(X(lerp(sg.a[0], sg.b[0], q)), Y(lerp(sg.a[1], sg.b[1], q))); ctx.stroke();
    }
    ctx.restore();
    ctx.lineCap = "round";
    for (const [sg, q] of drawn) {
      const c = col[sg.l];
      ctx.strokeStyle = `rgba(${Math.min(255, c[0] + 30 * (glowBoost - 1))},${Math.min(255, c[1] + 30 * (glowBoost - 1))},${Math.min(255, c[2] + 30 * (glowBoost - 1))},0.95)`;
      ctx.lineWidth = Math.max(1.7, sg.w * s);
      ctx.beginPath(); ctx.moveTo(X(sg.a[0]), Y(sg.a[1])); ctx.lineTo(X(lerp(sg.a[0], sg.b[0], q)), Y(lerp(sg.a[1], sg.b[1], q))); ctx.stroke();
    }
    // vias
    for (const v of VIAS) {
      const q = E.outBack(P(t, v.t0, 0.2)); if (q <= 0) continue;
      ctx.beginPath(); ctx.arc(X(v.at[0]), Y(v.at[1]), (v.size / 2) * s * q, 0, 2 * Math.PI);
      ctx.fillStyle = "rgba(236,242,239,0.95)"; ctx.fill();
      ctx.beginPath(); ctx.arc(X(v.at[0]), Y(v.at[1]), (v.drill / 2) * s * q, 0, 2 * Math.PI);
      ctx.fillStyle = "#0c1512"; ctx.fill();
    }
    ctx.restore();
  }

  // ---- text helpers ------------------------------------------------------------
  function splitWords(el) {
    const parts = el.innerHTML.split(/(<br>)/);
    el.innerHTML = parts.map((p) => (p === "<br>" ? "<br>" : p.split(" ").filter(Boolean).map((w) => `<span class="w"><span class="wi">${w}</span></span>`).join(" "))).join("");
    return [...el.querySelectorAll(".wi")];
  }
  function revealWords(words, t, t0, stagger, dur) {
    words.forEach((w, i) => {
      const q = spr(t, t0 + i * stagger, "type");
      w.style.transform = `translateY(${(1 - q) * 105}%)`;
      w.style.opacity = clamp(q * 1.6);
    });
  }
  function setBlock(el, op, dy = 0, extra = "") {
    el.style.opacity = op;
    el.style.visibility = op <= 0.001 ? "hidden" : "visible";
    el.style.transform = `translateY(${dy}px)${extra}`;
  }
  const inOut = (t, tin, din, tout, dout) => clamp(Math.min(E.out3(P(t, tin, din)), 1 - E.in2(P(t, tout, dout))));
  // spring in, accelerate out ("fast in, then hold")
  const inOutS = (t, tin, kind, tout, dout) => Math.min(spr(t, tin, kind), 1 - E.in2(P(t, tout, dout)));

  const wA1 = splitWords($("a-l1")), wA2 = splitWords($("a-l2"));
  const wBT = splitWords($("b-title"));
  const wC = splitWords($("c-head"));
  const wD1 = splitWords($("d-l1")), wD2 = splitWords($("d-l2"));
  const wE = splitWords($("e-word"));

  // ---- terminal ------------------------------------------------------------------
  const LINE_H = 29, VISIBLE = 16;
  const term = $("d-lines");
  const CMD = "python build.py";
  const cmdEl = document.createElement("div");
  cmdEl.innerHTML = `<span class="pr">$ </span><span class="cmd" id="cmd"></span><span class="cmd" id="caret">▍</span>`;
  term.appendChild(cmdEl);
  const stageEls = D.stages.map(([nn, name], i) => {
    const el = document.createElement("div");
    el.innerHTML = `<span class="n">${nn}</span> <span class="nm">${name.padEnd(43, " ")}</span><span class="ok">PASS</span>`;
    el.t0 = PASS_T - (D.stages.length - i) * (BEAT / 8);
    term.appendChild(el); return el;
  });
  const totEl = document.createElement("div");
  totEl.innerHTML = `<span class="tot">Total: 35/35 PASS</span>`;
  totEl.t0 = PASS_T; term.appendChild(totEl);
  const tLines = [cmdEl, ...stageEls, totEl];
  cmdEl.t0 = TD + 0.26;

  // ---- chips + leaders (scene B) ---------------------------------------------------------
  const svgNS = "http://www.w3.org/2000/svg";
  const leaders = $("leaders");
  function mkLeader() {
    const l = document.createElementNS(svgNS, "path"); l.setAttribute("fill", "none"); l.setAttribute("stroke", "#5cffa8"); l.setAttribute("stroke-width", "2"); l.setAttribute("stroke-linecap", "round");
    const d = document.createElementNS(svgNS, "circle"); d.setAttribute("r", "6"); d.setAttribute("fill", "#5cffa8");
    const ring = document.createElementNS(svgNS, "circle"); ring.setAttribute("fill", "none"); ring.setAttribute("stroke", "#5cffa8"); ring.setAttribute("stroke-width", "2");
    leaders.append(l, ring, d); return { l, d, ring };
  }
  const LD = { esp: mkLeader(), radar: mkLeader() };
  const CHIP_T = { sen: TB + 2 * BEAT, radar: TB + 3 * BEAT, esp: TB + 4 * BEAT }; // 4.125, 4.6875, 5.25
  function placeChip(el, key, anchor, chipXY, side, t) {
    const qs = spr(t, CHIP_T[key] + 0.1, "snappy"), qo = 1 - E.in2(P(t, TC - 0.34, 0.22));
    const q = clamp(qs * 1.6) * qo;
    const [ax, ay] = b2s(...anchor);
    const cw = el.offsetWidth, ch = el.offsetHeight;
    const [cx, cy] = chipXY;
    el.style.left = cx + "px"; el.style.top = cy + "px";
    el.style.opacity = q; el.style.visibility = q <= 0.001 ? "hidden" : "visible";
    el.style.transform = `translateY(${(1 - qs) * 18}px) scale(${0.96 + 0.04 * qs})`;
    const L = LD[key];
    const sx = side === "right" ? cx + cw : cx + cw * 0.5, sy = side === "right" ? cy + ch / 2 : cy + ch;
    const lq = E.inOut3(P(t, CHIP_T[key], 0.34));
    const out = 1 - E.in2(P(t, TC - 0.34, 0.22));
    const mx = lerp(ax, sx, lq), my = lerp(ay, sy, lq);
    L.l.setAttribute("d", `M${ax},${ay} L${mx},${my}`);
    L.l.setAttribute("opacity", lq > 0 ? out : 0);
    const dq = Math.max(0, spr(t, CHIP_T[key] - 0.05, "snappy"));
    L.d.setAttribute("cx", ax); L.d.setAttribute("cy", ay); L.d.setAttribute("r", 6 * dq); L.d.setAttribute("opacity", out * (dq > 0 ? 1 : 0));
    const rp = P(t, CHIP_T[key], 0.7);
    L.ring.setAttribute("cx", ax); L.ring.setAttribute("cy", ay); L.ring.setAttribute("r", 6 + 22 * E.out3(rp)); L.ring.setAttribute("opacity", out * (rp > 0 && rp < 1 ? (1 - rp) * 0.8 : 0));
  }

  // ---- scene C card state ------------------------------------------------------------------
  function co2At(tc) {
    if (tc < 0.6) return 640;
    if (tc < 2.6) return lerp(640, 1180, E.inOut3((tc - 0.6) / 2.0));
    if (tc < 2.9) return 1180;
    if (tc < 4.2) return lerp(1180, 720, E.out3((tc - 2.9) / 1.3));
    return 720;
  }
  const spark = $("c-spark").getContext("2d");
  function drawSpark(tc, rgb, alpha) {
    const w = 636, h = 64;
    spark.clearRect(0, 0, w, h);
    spark.save(); spark.globalAlpha = alpha;
    const y = (c) => h - 8 - ((c - 560) / (1260 - 560)) * (h - 16);
    // 1000 ppm reference line
    spark.strokeStyle = "rgba(255,255,255,0.08)"; spark.lineWidth = 1; spark.setLineDash([4, 5]);
    spark.beginPath(); spark.moveTo(0, y(1000)); spark.lineTo(w, y(1000)); spark.stroke(); spark.setLineDash([]);
    const tEnd = clamp(tc, 0, 4.4);
    spark.beginPath();
    const N = 120;
    for (let i = 0; i <= N; i++) { const tt = (i / N) * tEnd; const x = (tt / 4.4) * w; const yy = y(co2At(tt)); if (i === 0) spark.moveTo(x, yy); else spark.lineTo(x, yy); }
    spark.strokeStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`; spark.lineWidth = 3; spark.lineJoin = "round"; spark.stroke();
    const x = (tEnd / 4.4) * w, yy = y(co2At(tEnd));
    spark.beginPath(); spark.arc(x, yy, 5, 0, 2 * Math.PI); spark.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`; spark.fill();
    spark.restore();
  }

  // ---- the LED ring as a mark: real footprint positions, bodies tangential, light radial --------
  // Drawn one LED at a time, so the seven SK6812s can leave the blueprint and land as the logomark.
  const LED_ORDER = [...LEDS].sort((a, b) => ((Math.atan2(a.y, a.x) + 2.5 * Math.PI) % (2 * Math.PI)) - ((Math.atan2(b.y, b.x) + 2.5 * Math.PI) % (2 * Math.PI)));
  function drawLed(x, y, ang, s, k, alpha) {
    if (alpha <= 0) return;
    ctx.save(); ctx.globalAlpha = alpha; ctx.globalCompositeOperation = "lighter";
    const ex = x + Math.cos(ang) * 1.8 * s, ey = y + Math.sin(ang) * 1.8 * s, r = 7 * s, a0 = 0.4 + 0.6 * k;
    const g = ctx.createRadialGradient(ex, ey, 0, ex, ey, r);
    g.addColorStop(0, `rgba(92,255,168,${0.55 * a0})`); g.addColorStop(0.35, `rgba(92,255,168,${0.16 * a0})`); g.addColorStop(1, "rgba(92,255,168,0)");
    ctx.fillStyle = g; ctx.fillRect(ex - r, ey - r, 2 * r, 2 * r);
    ctx.restore();
    ctx.save(); ctx.globalAlpha = alpha; ctx.translate(x, y); ctx.rotate(ang + Math.PI / 2);
    ctx.beginPath(); ctx.roundRect(-2.0 * s, -0.8 * s, 4.0 * s, 1.6 * s, 0.4 * s);
    ctx.fillStyle = `rgba(${lerp(170, 220, k)},255,${lerp(200, 225, k)},0.95)`; ctx.fill();
    ctx.restore();
  }
  // (d) the cover's perforation field around the mark, lit outward from the ring -- the product's
  // own signature (vertical slots on concentric rings, as in the photo), so the end card isn't
  // just "centred text + logo"
  const HALO = [];
  for (let r = 92, ring = 0; r <= 158; r += 9.5, ring++) {
    const n = Math.floor(2 * Math.PI * r / 10.5);
    for (let i = 0; i < n; i++) HALO.push({ r, a: (i + (ring % 2) * 0.5) / n * 2 * Math.PI });
  }
  function drawHalo(cx, cy, k, t0, t) {
    if (t <= t0) return;
    ctx.save(); ctx.globalCompositeOperation = "lighter";
    for (const h of HALO) {
      const d = (h.r - 92) / 66, on = smooth(t0 + d * 0.45, t0 + d * 0.45 + 0.3, t);
      if (on <= 0) continue;
      const a = on * Math.exp(-(h.r - 92) / 34) * (0.3 + 0.7 * k) * 0.9;
      ctx.fillStyle = `rgba(92,255,168,${a})`;
      ctx.beginPath(); ctx.roundRect(cx + Math.cos(h.a) * h.r - 0.9, cy + Math.sin(h.a) * h.r - 2.3, 1.8, 4.6, 0.9); ctx.fill();
    }
    ctx.restore();
  }
  function drawMarkBase(cx, cy, s, k, alpha) {
    if (alpha <= 0) return;
    ctx.save(); ctx.globalAlpha = alpha;
    const hz = ctx.createRadialGradient(cx, cy, 0, cx, cy, 34 * s);
    hz.addColorStop(0, `rgba(92,255,168,${0.10 + 0.08 * k})`); hz.addColorStop(1, "rgba(92,255,168,0)");
    ctx.fillStyle = hz; ctx.fillRect(cx - 34 * s, cy - 34 * s, 68 * s, 68 * s);
    ctx.beginPath(); ctx.arc(cx, cy, 5 * s, 0, 2 * Math.PI); ctx.strokeStyle = "rgba(238,243,240,0.22)"; ctx.lineWidth = 2; ctx.stroke();
    ctx.restore();
  }

  // ---- background --------------------------------------------------------------------------
  function drawBg() {
    ctx.fillStyle = "#070b09"; ctx.fillRect(0, 0, W, H);
    const g = ctx.createRadialGradient(W * 0.5, H * 0.45, 0, W * 0.5, H * 0.45, W * 0.7);
    g.addColorStop(0, "rgba(22,34,29,0.55)"); g.addColorStop(1, "rgba(7,11,9,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  }

  // ---- camera poses that make the cuts continuous --------------------------------------------
  // A -> B: the board sits exactly behind the photographed cover (cover r 64 mm, PCB r 60 mm).
  const A_CX = 1330, A_CY = 560, IRIS_T = TB - 0.2;
  const photoScaleA = (t) => lerp(1.0, 1.07, E.inOutSine(clamp(t / TB)));
  const aSize = 1100 * photoScaleA(IRIS_T);
  const XR = { cx: A_CX + (CCX - RC) * aSize, cy: A_CY + (CCY - RCPY) * aSize, s: (CR * aSize * 60 / 64) / 60 };
  // C -> D: the blueprint's rim is traced over the cover in the scene-C photo.
  const TR = { cx: 600 + (CCX - RC) * 1000, cy: 560 + (CCY - RCPY) * 1000, s: (CR * 1000 * 60 / 64) / 60 };
  // D -> E: the seven LEDs fly from the blueprint into the logomark.
  const LOGO = { cx: 960, cy: 318, s: 4.6 }, FLY_T = TE - 0.36;

  // =====================================================================================
  window.renderAt = function (t) {
    drawBg();
    const k = breathK(t);

    // ---------- A: hook -- the ring powers on behind the cover ----------
    const iris = 560 * spr(t, IRIS_T, "def");
    if (t < TB + 0.7) {
      const on = spr(t, 0.05, "def");
      const size = 1100 * photoScaleA(Math.min(t, IRIS_T));
      const gain = (0.25 + 0.75 * Math.pow(k, 1 / 2.2)) * on;
      const a = 1 - E.inOut3(P(t, TB + 0.1, 0.45));
      ctx.save();
      if (iris > 0) { ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.arc(XR.cx, XR.cy, iris, 0, 2 * Math.PI, true); ctx.clip("evenodd"); }
      drawPhoto(photoFrame(0, gain * 1.05, 1.0), A_CX, A_CY, size, a);
      bloom(A_CX, A_CY, 420 * size / 1100, [92, 255, 168], a * 0.5 * k * on);
      ctx.restore();
    }
    revealWords(wA1, t, 0.1, 0.06, 0.55);
    revealWords(wA2, t, 1.4, 0.09, 0.5);
    const aOut = 1 - E.in2(P(t, TB - 0.3, 0.2));
    setBlock($("a-l1"), aOut, -26 * (1 - aOut));
    setBlock($("a-l2"), aOut * (t >= 1.35 ? 1 : 0), -26 * (1 - aOut));

    // ---------- B: reveal -- x-ray through the cover, then the camera settles ----------
    const cam = spr(t, TB + 0.2, "heavy");
    const zoom = E.in3(P(t, TC - 0.36, 0.44));
    const zoomMove = E.inOut3(P(t, TC - 0.36, 0.5));
    const drift = 1 + 0.02 * P(t, TB + 1.0, TC - TB - 1.0);
    const bx = lerp(XR.cx, 1320, cam), by = lerp(XR.cy, 600, cam), bs = lerp(XR.s, 7.0, cam) * drift;
    BT = { cx: lerp(bx, 600, zoomMove), cy: lerp(by, 560, zoomMove), s: bs * (1 + 2.4 * zoom), rot: 0 };
    const bAlpha = 1 - E.inOut3(P(t, TC - 0.3, 0.26));
    if (t >= IRIS_T && t < TC + 0.1 && bAlpha > 0) {
      const sc = BT.s / RS;
      ctx.save();
      if (t < TB + 0.7) { ctx.beginPath(); ctx.arc(XR.cx, XR.cy, iris, 0, 2 * Math.PI); ctx.clip(); }
      ctx.globalAlpha = bAlpha;
      ctx.translate(BT.cx, BT.cy); ctx.scale(sc, sc);
      ctx.shadowColor = "rgba(0,0,0,0.65)"; ctx.shadowBlur = 70; ctx.shadowOffsetY = 34;
      ctx.drawImage(boardCan, -RCX, -RCY);
      ctx.restore();
      // light sweep once the camera has settled
      const sw = P(t, TB + 0.6, 1.5);
      if (sw > 0 && sw < 1) {
        sweepCtx.globalCompositeOperation = "source-over"; sweepCtx.clearRect(0, 0, BW, BH);
        sweepCtx.drawImage(boardCan, 0, 0);
        sweepCtx.globalCompositeOperation = "source-in";
        const x0 = lerp(-BW * 0.6, BW * 1.3, E.inOutSine(sw));
        const gr = sweepCtx.createLinearGradient(x0, 0, x0 + BW * 0.45, BH * 0.35);
        gr.addColorStop(0, "rgba(255,255,255,0)"); gr.addColorStop(0.5, "rgba(255,255,255,0.32)"); gr.addColorStop(1, "rgba(255,255,255,0)");
        sweepCtx.fillStyle = gr; sweepCtx.fillRect(0, 0, BW, BH);
        ctx.save(); ctx.globalAlpha = bAlpha; ctx.globalCompositeOperation = "screen";
        ctx.translate(BT.cx, BT.cy); ctx.scale(sc, sc); ctx.drawImage(sweepCan, -RCX, -RCY); ctx.restore();
      }
      const gOut = 1 - E.in2(P(t, TC - 0.34, 0.22));
      drawGhost("SENS1", E.inOut3(P(t, CHIP_T.sen, 0.6)), 0.75 * gOut);
      drawGhost("MOD1", E.inOut3(P(t, CHIP_T.esp, 0.6)), 0.75 * gOut);
      drawGhost("LDR1", E.inOut3(P(t, CHIP_T.radar, 0.6)), 0.75 * gOut);
      // the ring wakes up just before the zoom into it
      const ledA = smooth(TC - 1.1, TC - 0.6, t) * bAlpha;
      drawBoardLeds(k, ledA, [92, 255, 168]);
      // x-ray edge: the iris rim glows while it opens
      const rimA = (1 - E.in2(P(t, IRIS_T + 0.15, 0.5))) * clamp(iris / 30);
      if (rimA > 0.001) {
        ctx.save(); ctx.globalCompositeOperation = "lighter";
        ctx.beginPath(); ctx.arc(XR.cx, XR.cy, iris, 0, 2 * Math.PI);
        ctx.strokeStyle = `rgba(92,255,168,${0.85 * rimA})`; ctx.lineWidth = 2.5;
        ctx.shadowColor = "rgba(92,255,168,0.9)"; ctx.shadowBlur = 24; ctx.stroke();
        ctx.restore();
      }
    }
    setBlock($("b-label"), clamp(inOutS(t, TB + 0.12, "def", TC - 0.44, 0.26)), 16 * (1 - spr(t, TB + 0.12, "def")));
    revealWords(wBT, t, TB + 0.22, 0.085, 0.6);
    setBlock($("b-title"), 1 - E.in2(P(t, TC - 0.44, 0.26)), -20 * E.in2(P(t, TC - 0.44, 0.26)));
    setBlock($("b-sub"), clamp(inOutS(t, TB + 0.55, "def", TC - 0.4, 0.26)), 22 * (1 - spr(t, TB + 0.55, "def")));
    // SEN66 tag sits in the cut-out where the module drops in
    {
      const el = $("sen-tag"), q = clamp(inOutS(t, CHIP_T.sen + 0.18, "ui", TC - 0.34, 0.22));
      const [x0, y0] = b2s(20.5, -33.95), [x1, y1] = b2s(47.85, 23.0);
      el.style.left = (x0 + x1) / 2 - el.offsetWidth / 2 + "px"; el.style.top = (y0 + y1) / 2 - el.offsetHeight / 2 - 6 + "px";
      setBlock(el, q, 12 * (1 - spr(t, CHIP_T.sen + 0.18, "ui")));
    }
    placeChip($("chip-esp"), "esp", [-6.3, -39.4], [842, 112], "bottom", t);
    placeChip($("chip-radar"), "radar", [-31.9, 22.4], [596, 872], "right", t);

    // B -> C: flying into the ring means flying into its light
    {
      const u = P(t, TC - 0.34, 0.62);
      if (u > 0 && u < 1) {
        const a = Math.sin(Math.PI * u) ** 1.6 * 0.55, rad = lerp(160, 1500, E.out3(u));
        const cx = lerp(BT.cx, 600, u), cy = lerp(BT.cy, 560, u);
        ctx.save(); ctx.globalCompositeOperation = "screen";
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rad);
        g.addColorStop(0, `rgba(160,255,205,${a})`); g.addColorStop(0.35, `rgba(92,255,168,${a * 0.55})`); g.addColorStop(1, "rgba(92,255,168,0)");
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
        ctx.restore();
      }
    }

    // ---------- C: in use ----------
    const tc = t - TC;
    const co2 = co2At(tc);
    const aqi = Math.max(PM_AQI, co2Aqi(co2));
    const fw = aqiColor(aqi);
    if (t > TC - 0.15 && t < TD + 0.5) {
      const cin = E.out3(P(t, TC - 0.03, 0.6));
      const cout = E.inOut3(P(t, TD - 0.05, 0.45));    // fades while its rim is traced over it
      const sc = lerp(1.32, 1.0, spr(t, TC - 0.05, "heavy"));
      const dh = displayHue(rgbHue(...fw)) - PHOTO_HUE;
      const gain = (0.25 + 0.75 * Math.pow(k, 1 / 2.2)) * (1 - 0.35 * smooth(TD - 0.45, TD, t));
      const a = cin * (1 - cout);
      const hsv = hsv2rgb(displayHue(rgbHue(...fw)), 0.75, 1).map((v) => Math.round(v * 255));
      drawPhoto(photoFrame(dh, gain * 1.05, 1.0 + 0.12 * clamp(Math.abs(dh) / 60)), 600, 560, 1000 * sc, a);
      bloom(600, 560, 400 * sc, hsv, a * 0.55 * k);
    }
    revealWords(wC, t, TC + 0.22, 0.06, 0.55);
    setBlock($("c-head"), 1 - E.in2(P(t, TD - 0.34, 0.3)), -20 * E.in2(P(t, TD - 0.34, 0.3)));
    {
      const q = clamp(inOutS(t, TC + 0.36, "def", TD - 0.3, 0.3));
      setBlock($("c-card"), q, 30 * (1 - spr(t, TC + 0.36, "def")) + 20 * E.in2(P(t, TD - 0.3, 0.3)));
      $("v-co2").textContent = Math.round(co2);
      $("v-aqi").textContent = Math.round(aqi);
      $("v-dot").style.background = `rgb(${fw[0]},${fw[1]},${fw[2]})`;
      $("v-dot").style.boxShadow = `0 0 14px rgba(${fw[0]},${fw[1]},${fw[2]},0.8)`;
      if (q > 0) drawSpark(tc, fw, 1);
      const TT = TC + 5 * BEAT; // 10.3125
      const tq = clamp(1.5 * inOutS(t, TT, "snappy", TD - 0.3, 0.3));
      setBlock($("c-toast"), tq, 0, ` translateX(${(1 - spr(t, TT, "snappy")) * 40}px)`);
      $("fan-g").setAttribute("transform", `rotate(${Math.max(0, t - TT) * 520} 17 17)`);
    }

    // ---------- D: the brag -- rim traced over the cover, then the camera settles ----------
    const dcam = spr(t, TD + 0.3, "heavy");
    const DT = { cx: lerp(TR.cx, 560, dcam), cy: lerp(TR.cy, 592, dcam), s: lerp(TR.s, 7.0, dcam) };
    const boardOut = E.inOut3(P(t, TE - 0.42, 0.34));   // everything but the seven LEDs leaves
    if (t > TD - 0.26 && t < TE + 0.1) {
      const boost = 1 + 1.3 * Math.exp(-Math.max(0, t - PASS_T) / 0.28) * (t >= PASS_T ? 1 : 0);
      drawBlueprint(t, DT.cx, DT.cy, DT.s, 1 - boardOut, boost);
    }
    revealWords(wD1, t, TD + 0.12, 0.07, 0.55);
    revealWords(wD2, t, TD + 0.86, 0.07, 0.55);
    setBlock($("d-head"), 1 - E.in2(P(t, TE - 0.3, 0.28)), -20 * E.in2(P(t, TE - 0.3, 0.28)));
    {
      const q = clamp(inOutS(t, TD + 0.18, "def", TE - 0.3, 0.28));
      setBlock($("d-term"), q, 26 * (1 - spr(t, TD + 0.18, "def")) + 16 * E.in2(P(t, TE - 0.3, 0.28)));
      const typed = Math.floor(clamp((t - (TD + 0.28)) / 0.3) * CMD.length);
      $("cmd").textContent = CMD.slice(0, typed);
      $("caret").style.opacity = t < stageEls[0].t0 ? (Math.floor(t * 3) % 2 === 0 ? 1 : 0.2) : 0;
      let count = 0, newest = -1;
      tLines.forEach((el, i) => {
        const vis = t >= el.t0;
        el.style.visibility = vis ? "visible" : "hidden";
        el.style.opacity = vis ? E.out3(P(t, el.t0, 0.08)) : 0;
        if (vis) { count = i + 1; newest = el.t0; }
      });
      const frac = newest >= 0 ? E.out3(P(t, newest, 0.07)) : 1;
      const scroll = Math.max(0, count - VISIBLE - 1 + frac);
      term.style.transform = `translateY(${-scroll * LINE_H}px)`;
      const pulse = t >= PASS_T ? Math.exp(-(t - PASS_T) / 0.5) : 0;
      totEl.style.textShadow = `0 0 ${18 * pulse + 6}px rgba(92,255,168,${0.35 + 0.5 * pulse})`;
      setBlock($("d-cap"), clamp(inOutS(t, TD + 1.4, "def", TE - 0.3, 0.28)), 10 * (1 - spr(t, TD + 1.4, "def")));
    }

    // ---------- D -> E: the seven LEDs leave the board and land as the logomark ----------
    if (t > FLY_T - 0.25) {
      const lit = smooth(FLY_T - 0.25, FLY_T + 0.05, t);
      LED_ORDER.forEach((L, i) => {
        const q = spr(t, FLY_T + i * 0.05, "def");
        const s = lerp(DT.s, LOGO.s, q);
        drawLed(lerp(DT.cx + L.x * DT.s, LOGO.cx + L.x * LOGO.s, q), lerp(DT.cy + L.y * DT.s, LOGO.cy + L.y * LOGO.s, q), Math.atan2(L.y, L.x), s, k, lit);
      });
      drawMarkBase(LOGO.cx, LOGO.cy, LOGO.s, k, smooth(TE + 0.15, TE + 0.7, t));
      drawHalo(LOGO.cx, LOGO.cy, k, TE + 0.3, t);
    }

    // ---------- E: outro ----------
    revealWords(wE, t, TE + 0.35, 0.09, 0.62);
    setBlock($("e-word"), t > TE + 0.3 ? 1 : 0);
    setBlock($("e-tag"), clamp(spr(t, TE + 0.8, "def")), 18 * (1 - spr(t, TE + 0.8, "def")));
    setBlock($("e-url"), clamp(spr(t, TE + 1.1, "def")), 14 * (1 - spr(t, TE + 1.1, "def")));
    setBlock($("e-meta"), clamp(spr(t, TE + 1.3, "def")), 10 * (1 - spr(t, TE + 1.3, "def")));
  };

  window.renderAt(0);
  window.__ready = true;
})();
