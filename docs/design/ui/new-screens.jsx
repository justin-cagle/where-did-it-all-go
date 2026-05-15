// ══════════════════════════════════════════════════════════════════════════════
// NEW SCREENS — Monthly Recap, Subscription Audit, Tx Detail (split-expand)
// Depends on globals from dashboard.html: SAMPLE, fmt, pct, catColors, icons,
// Sidebar, Bar, DonutChart, Sparkline, HitlBadge, TxRow.
// ══════════════════════════════════════════════════════════════════════════════

// ─── Extra sample data (named to avoid collisions) ────────────────────────
const RECAP_DATA = {
  month: 'April 2026',
  income: 8400,
  spent: 4218.77,
  saved: 3200,
  unaccounted: 981.23, // the "where did it all go" hook
  // category outflows (must roughly sum to spent + unaccounted)
  flows: [
    { name: 'Housing',       amount: 1850.00, color: 0, prevMonth: 1850.00 },
    { name: 'Groceries',     amount: 612.40,  color: 1, prevMonth: 480.00  },
    { name: 'Dining',        amount: 388.92,  color: 2, prevMonth: 210.00  },
    { name: 'Transport',     amount: 244.18,  color: 5, prevMonth: 180.00  },
    { name: 'Subscriptions', amount: 217.94,  color: 4, prevMonth: 135.00  },
    { name: 'Shopping',      amount: 412.10,  color: 2, prevMonth: 198.00  },
    { name: 'Entertainment', amount: 89.00,   color: 3, prevMonth: 89.00   },
    { name: 'Other',         amount: 404.23,  color: 5, prevMonth: 312.00  },
  ],
  surprise: {
    title: 'Dining doubled',
    body: 'You spent $389 on dining — 85% more than March. The biggest jump: 6 weeknight orders from Sweetgreen totaling $94.',
    delta: +178.92,
    cat: 'Dining',
    catColor: 2,
  },
  weeklyBurn: [
    { week: 'Wk 14', income: 0,    expense: 1124, label: 'Apr 1–7' },
    { week: 'Wk 15', income: 4200, expense: 1488, label: 'Apr 8–14' },
    { week: 'Wk 16', income: 0,    expense: 720,  label: 'Apr 15–21' },
    { week: 'Wk 17', income: 4200, expense: 887,  label: 'Apr 22–28' },
  ],
  topMerchants: [
    { name: 'Sweetgreen',     count: 6,  total: 94.32,  cat: 'Dining',     catColor: 2, trend: +1.4 },
    { name: 'Whole Foods',    count: 4,  total: 287.18, cat: 'Groceries',  catColor: 1, trend: +0.2 },
    { name: 'Amazon',         count: 8,  total: 264.40, cat: 'Shopping',   catColor: 2, trend: +0.8 },
    { name: 'Shell',          count: 3,  total: 174.20, cat: 'Transport',  catColor: 5, trend: -0.1 },
    { name: 'Adobe',          count: 1,  total: 59.99,  cat: 'Subscriptions', catColor: 4, trend: 0 },
  ],
};

const SUBS_DATA = [
  {
    id: 's1', name: 'Adobe Creative Cloud', merchant: 'ADOBE *CRTV CLD', plan: 'All Apps · monthly',
    current: 59.99, currency: 'USD', cycle: 'monthly',
    nextCharge: 'May 15, 2026', daysUntil: 11,
    account: 'Visa ···4821', cat: 'Subscriptions', catColor: 4,
    activeSince: 'Aug 2021',
    lifetimeSpent: 2519.58, // 4y 9m
    lastUsed: '2 days ago',
    ghost: false, priceCreep: true,
    history: [9.99,9.99,9.99,9.99,19.99,19.99,19.99,19.99,29.99,29.99,29.99,29.99,49.99,49.99,49.99,54.99,54.99,54.99,59.99,59.99,59.99,59.99,59.99,59.99],
    historyLabels: ['2021-08','...','2026-04'],
    confidence: 99,
  },
  {
    id: 's2', name: 'Netflix', merchant: 'NETFLIX.COM', plan: 'Premium · monthly',
    current: 22.99, currency: 'USD', cycle: 'monthly',
    nextCharge: 'May 8, 2026', daysUntil: 4,
    account: 'Visa ···4821', cat: 'Subscriptions', catColor: 4,
    activeSince: 'Mar 2018',
    lifetimeSpent: 1738.50,
    lastUsed: 'Yesterday',
    ghost: false, priceCreep: true,
    history: [10.99,10.99,10.99,12.99,12.99,12.99,15.49,15.49,15.49,17.99,17.99,17.99,19.99,19.99,19.99,22.99,22.99,22.99,22.99,22.99],
    confidence: 100,
  },
  {
    id: 's3', name: 'Planet Fitness', merchant: 'PF*GYM 1042', plan: 'Black Card · monthly',
    current: 24.99, currency: 'USD', cycle: 'monthly',
    nextCharge: 'May 28, 2026', daysUntil: 24,
    account: 'Visa ···4821', cat: 'Health', catColor: 1,
    activeSince: 'Jan 2024',
    lifetimeSpent: 674.73,
    lastUsed: '4 months ago',
    ghost: true, priceCreep: false,
    history: [19.99,19.99,19.99,19.99,19.99,19.99,19.99,19.99,19.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99,24.99],
    confidence: 100,
  },
  {
    id: 's4', name: 'Spotify Family', merchant: 'SPOTIFY USA', plan: 'Family · monthly',
    current: 16.99, currency: 'USD', cycle: 'monthly',
    nextCharge: 'May 29, 2026', daysUntil: 25,
    account: 'Visa ···4821', cat: 'Subscriptions', catColor: 4,
    activeSince: 'Nov 2019',
    lifetimeSpent: 1098.30,
    lastUsed: 'Today',
    ghost: false, priceCreep: true,
    history: [14.99,14.99,14.99,14.99,14.99,14.99,14.99,14.99,16.99,16.99,16.99,16.99,16.99,16.99],
    confidence: 100,
  },
  {
    id: 's5', name: 'iCloud+ 2TB', merchant: 'APPLE.COM/BILL', plan: '2TB storage · monthly',
    current: 9.99, currency: 'USD', cycle: 'monthly',
    nextCharge: 'May 12, 2026', daysUntil: 8,
    account: 'Visa ···4821', cat: 'Subscriptions', catColor: 4,
    activeSince: 'Jun 2022',
    lifetimeSpent: 469.53,
    lastUsed: 'Today',
    ghost: false, priceCreep: false,
    history: [9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99,9.99],
    confidence: 100,
  },
  {
    id: 's6', name: 'NYTimes',  merchant: 'NYTIMES *DGTL', plan: 'Digital · monthly',
    current: 17.00, currency: 'USD', cycle: 'monthly',
    nextCharge: 'May 22, 2026', daysUntil: 18,
    account: 'Visa ···4821', cat: 'Subscriptions', catColor: 4,
    activeSince: 'Sep 2023',
    lifetimeSpent: 244.50,
    lastUsed: '3 weeks ago',
    ghost: false, priceCreep: true,
    history: [4,4,4,4,4,4,8,8,8,8,8,8,17,17,17,17,17,17,17,17,17,17,17,17,17,17,17,17,17,17,17],
    confidence: 100,
  },
  {
    id: 's7', name: 'ChatGPT Plus', merchant: 'OPENAI *CHATGPT', plan: 'Plus · monthly',
    current: 20.00, currency: 'USD', cycle: 'monthly',
    nextCharge: 'May 18, 2026', daysUntil: 14,
    account: 'Visa ···4821', cat: 'Subscriptions', catColor: 4,
    activeSince: 'Apr 2023',
    lifetimeSpent: 740.00,
    lastUsed: 'Today',
    ghost: false, priceCreep: false,
    history: [20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20,20],
    confidence: 100,
  },
  {
    id: 's8', name: 'NordVPN', merchant: 'NORDVPN *RECURRING', plan: 'Annual',
    current: 71.88, currency: 'USD', cycle: 'yearly',
    nextCharge: 'Jul 3, 2026', daysUntil: 58,
    account: 'Visa ···4821', cat: 'Subscriptions', catColor: 4,
    activeSince: 'Jul 2022',
    lifetimeSpent: 287.52,
    lastUsed: '8 months ago',
    ghost: true, priceCreep: false,
    history: [71.88,71.88,71.88,71.88],
    confidence: 100,
  },
];

// ─── Tiny inline price-history sparkline with $ start/end labels ──────────
function PriceHistory({ data, t, width = 110, height = 28, accent }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  });
  const path = `M ${pts.join(' L ')}`;
  const fillPath = `${path} L ${width},${height} L 0,${height} Z`;
  const last = data[data.length - 1];
  const first = data[0];
  const trendUp = last > first;
  const color = accent || (trendUp ? t.danger : t.success);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: 'visible' }}>
      <path d={fillPath} fill={color} fillOpacity={0.1} />
      <path d={path} fill="none" stroke={color} strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={width} cy={height - ((last - min) / range) * (height - 4) - 2} r={2.4} fill={color} stroke={t.bgElevated} strokeWidth={1.2} />
    </svg>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// SANKEY — income → categories
// Hand-rolled curves so we keep control. Two-column flow.
// ──────────────────────────────────────────────────────────────────────────────
function SankeyFlow({ t, data, privacy, width = 720, height = 380 }) {
  const cats = catColors(t);
  const total = data.flows.reduce((s, f) => s + f.amount, 0) + data.saved;
  const pad = 8;
  const leftX = 0;
  const leftW = 140;
  const rightX = width - 200;
  const rightW = 200;
  // Left column — single income source. Position centered.
  const leftBlocks = [
    { label: 'Income',  amount: data.income, color: t.success, isIncome: true },
  ];
  const totalOut = data.flows.reduce((s, f) => s + f.amount, 0) + data.saved + data.unaccounted;
  // Build right column blocks (categories + saved + unaccounted)
  const rightItems = [
    ...data.flows.map(f => ({ label: f.name, amount: f.amount, color: cats[f.color] })),
    { label: 'Saved',       amount: data.saved,       color: t.success, dashed: false, kind: 'saved' },
    { label: 'Unaccounted', amount: data.unaccounted, color: t.warning, dashed: true,  kind: 'unaccounted' },
  ];
  // Layout right blocks with proportional heights
  const rightTotal = rightItems.reduce((s, r) => s + r.amount, 0);
  const usableH = height - (rightItems.length - 1) * pad;
  let cy = 0;
  const rightLayout = rightItems.map(r => {
    const h = (r.amount / rightTotal) * usableH;
    const block = { ...r, y: cy, h };
    cy += h + pad;
    return block;
  });
  // Income block fills full height
  const incomeBlock = { y: 0, h: height, ...leftBlocks[0] };

  // Path generator: smooth bezier from leftX+leftW → rightX, varying width
  function flowPath(srcY, srcH, dstY, dstH) {
    const x1 = leftX + leftW;
    const x2 = rightX;
    const cx1 = x1 + (x2 - x1) * 0.5;
    const cx2 = x2 - (x2 - x1) * 0.5;
    const y1Top = srcY;
    const y1Bot = srcY + srcH;
    const y2Top = dstY;
    const y2Bot = dstY + dstH;
    return `M ${x1} ${y1Top} C ${cx1} ${y1Top}, ${cx2} ${y2Top}, ${x2} ${y2Top} L ${x2} ${y2Bot} C ${cx2} ${y2Bot}, ${cx1} ${y1Bot}, ${x1} ${y1Bot} Z`;
  }

  // Source slices on income block (proportional)
  let srcCursor = 0;
  const flowPaths = rightLayout.map(r => {
    const srcH = (r.amount / rightTotal) * height;
    const p = flowPath(srcCursor, srcH, r.y, r.h);
    const path = { d: p, color: r.color, dashed: r.dashed, label: r.label, srcY: srcCursor, srcH, dstY: r.y, dstH: r.h, amount: r.amount, kind: r.kind };
    srcCursor += srcH;
    return path;
  });

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <defs>
        {flowPaths.map((p, i) => (
          <linearGradient key={i} id={`sk-${i}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%"  stopColor={t.success} stopOpacity={0.32} />
            <stop offset="100%" stopColor={p.color} stopOpacity={p.kind === 'unaccounted' ? 0.18 : 0.42} />
          </linearGradient>
        ))}
        <pattern id="sk-warning-stripe" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
          <rect width="6" height="6" fill={t.warning} fillOpacity="0.18" />
          <line x1="0" y1="0" x2="0" y2="6" stroke={t.warning} strokeWidth="1.5" strokeOpacity="0.5" />
        </pattern>
      </defs>

      {/* Flow ribbons */}
      {flowPaths.map((p, i) => (
        <path key={i} d={p.d}
          fill={p.kind === 'unaccounted' ? 'url(#sk-warning-stripe)' : `url(#sk-${i})`}
          stroke={p.kind === 'unaccounted' ? t.warning : 'none'}
          strokeWidth={p.kind === 'unaccounted' ? 1 : 0}
          strokeDasharray={p.kind === 'unaccounted' ? '4,3' : 'none'}
        />
      ))}

      {/* Income block — solid card so text always reads */}
      <rect x={leftX} y={incomeBlock.y} width={leftW} height={incomeBlock.h} fill={t.bgElevated} stroke={t.success} strokeWidth={1.5} rx={6} />
      <rect x={leftX} y={incomeBlock.y} width={leftW} height={incomeBlock.h} fill={t.success} fillOpacity={0.1} rx={6} />
      <rect x={leftX} y={incomeBlock.y} width={3} height={incomeBlock.h} fill={t.success} rx={1.5} />
      <text x={leftX + leftW / 2} y={incomeBlock.h / 2 - 14} textAnchor="middle" fill={t.fgPrimary} fontSize={13} fontWeight={600} fontFamily="'Geist', sans-serif">Income</text>
      <text x={leftX + leftW / 2} y={incomeBlock.h / 2 + 8} textAnchor="middle" fill={t.fgPrimary} fontSize={20} fontWeight={700} fontFamily="'Geist Mono', monospace" letterSpacing="-0.02em">{fmt(data.income, privacy)}</text>
      <text x={leftX + leftW / 2} y={incomeBlock.h / 2 + 26} textAnchor="middle" fill={t.fgMuted} fontSize={10} fontFamily="'Geist Mono', monospace">{data.month.toUpperCase()}</text>

      {/* Right blocks */}
      {rightLayout.map((r, i) => (
        <g key={i}>
          {/* Solid card backing so labels read regardless of theme */}
          <rect x={rightX} y={r.y} width={rightW} height={r.h} fill={t.bgElevated} rx={4} />
          <rect x={rightX} y={r.y} width={rightW} height={r.h}
            fill={r.kind === 'unaccounted' ? `${t.warning}1c` : `${r.color}18`}
            stroke={r.kind === 'unaccounted' ? t.warning : 'none'}
            strokeDasharray={r.kind === 'unaccounted' ? '3,2' : 'none'}
            strokeWidth={1}
            rx={4}
          />
          {/* Color rail */}
          <rect x={rightX} y={r.y} width={3} height={r.h} fill={r.color} rx={1.5} />
          {/* Label */}
          <text x={rightX + 12} y={r.y + Math.min(r.h / 2, r.h - 6) + (r.h < 24 ? 0 : -2)}
            fill={t.fgPrimary} fontSize={r.h < 18 ? 10 : 12} fontWeight={500} fontFamily="'Geist', sans-serif"
            dominantBaseline={r.h < 24 ? 'middle' : 'auto'}
          >{r.label}</text>
          {r.h >= 24 && (
            <text x={rightX + 12} y={r.y + r.h / 2 + 12} fill={t.fgMuted} fontSize={10.5} fontFamily="'Geist Mono', monospace">
              {fmt(r.amount, privacy)} · {Math.round(r.amount / rightTotal * 100)}%
            </text>
          )}
          {r.h < 24 && (
            <text x={rightX + rightW - 8} y={r.y + r.h / 2} textAnchor="end" fill={t.fgMuted} fontSize={10} fontFamily="'Geist Mono', monospace" dominantBaseline="middle">
              {fmt(r.amount, privacy)}
            </text>
          )}
        </g>
      ))}

      {/* "Where did it all go?" arrow callout pointing at unaccounted */}
      {(() => {
        const u = rightLayout.find(r => r.kind === 'unaccounted');
        if (!u) return null;
        const ax = rightX + rightW + 8;
        const ay = u.y + u.h / 2;
        return (
          <g>
            <line x1={ax} y1={ay} x2={ax + 28} y2={ay} stroke={t.warning} strokeWidth={1.2} strokeDasharray="3,2" />
            <text x={ax + 32} y={ay - 4} fill={t.warning} fontSize={11} fontWeight={600} fontFamily="'Geist', sans-serif">where did</text>
            <text x={ax + 32} y={ay + 9} fill={t.warning} fontSize={11} fontWeight={600} fontFamily="'Geist', sans-serif">it all go?</text>
          </g>
        );
      })()}
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────
// WaterfallFlow — Vertical Sankey ("Sankey on its side").
// Each outflow is a continuous ribbon that starts bundled at the top
// (forming the trunk) and curves smoothly outward at its exit point.
// Layout: Needs peel left in order (Housing → Subscriptions),
//         Saved continues straight down through the center,
//         Wants peel right in order (Dining → Other), Unaccounted peels last.
// Trunk visual is composed of stacked lanes; it narrows naturally as
// lanes peel away because each lane's width is proportional to its $.
// ─────────────────────────────────────────────────────────────────
function WaterfallFlow({ t, data, privacy, width = 720, height = 380 }) {
  const cats = catColors(t);

  const padTop = 76;
  const padBot = 86;
  const padX = 30;
  const innerH = height - padTop - padBot;

  // ── Categorize and build lane list ──
  const needsNames = ['Housing', 'Groceries', 'Transport', 'Subscriptions'];
  const wantsNames = ['Dining',  'Shopping',  'Entertainment', 'Other'];
  const byName = Object.fromEntries(data.flows.map(f => [f.name, f]));
  const needs = needsNames.map(n => byName[n]).filter(Boolean);
  const wants = wantsNames.map(n => byName[n]).filter(Boolean);

  // Trunk-left-to-right order: outermost-left peels first.
  const leftLanes = needs.map((f, idx) => ({
    name: f.name, amount: f.amount, color: cats[f.color], dashed: false,
    side: 'left', slot: idx,        // slot 0..3
  }));

  const savedLane = {
    name: 'Saved', amount: data.saved, color: t.success, dashed: false,
    side: 'center', slot: null,
  };

  // Right lanes in TRUNK-LR order (innermost → outermost).
  // Innermost-right (next to Saved) peels LAST (slot 8 = Unaccounted),
  // Outermost-right (furthest from center) peels FIRST (slot 4 = Dining).
  const rightLanes = [
    { name: 'Unaccounted',     amount: data.unaccounted,     color: t.warning,     dashed: true,  side: 'right', slot: 8 },
    { name: wants[3].name,     amount: wants[3].amount,      color: cats[wants[3].color], dashed: false, side: 'right', slot: 7 }, // Other
    { name: wants[2].name,     amount: wants[2].amount,      color: cats[wants[2].color], dashed: false, side: 'right', slot: 6 }, // Entertainment
    { name: wants[1].name,     amount: wants[1].amount,      color: cats[wants[1].color], dashed: false, side: 'right', slot: 5 }, // Shopping
    { name: wants[0].name,     amount: wants[0].amount,      color: cats[wants[0].color], dashed: false, side: 'right', slot: 4 }, // Dining
  ];

  const lanes = [...leftLanes, savedLane, ...rightLanes];

  // ── Trunk sizing ──
  const totalAmount = lanes.reduce((s, l) => s + l.amount, 0); // ≈ data.income
  const trunkW = Math.min(width * 0.42, 380);
  const pxPerDollar = trunkW / totalAmount;

  // Assign x positions in trunk
  let xCursor = (width - trunkW) / 2;
  lanes.forEach(l => {
    l.w  = l.amount * pxPerDollar;
    l.xL = xCursor;
    l.xR = xCursor + l.w;
    xCursor += l.w;
  });

  // ── Peel Y assignment ──
  // 9 slots: 0..3 = needs (left), 4..8 = wants/unaccounted (right) with section gap inserted
  const sectionGap = Math.max(34, innerH * 0.08);
  const peelStep   = (innerH - sectionGap) / 10; // +1 top buffer, +1 bottom buffer → divide by 10
  lanes.forEach(l => {
    if (l.slot === null) return;
    const baseY = padTop + (l.slot + 1) * peelStep;
    l.peelY = l.slot >= 4 ? baseY + sectionGap : baseY;
  });

  // Saved lands at the bottom of the trunk inner area
  const savedBottomY = padTop + innerH;

  // ── Build a lane's outline path ──
  // For exit lanes: top edge curves out to a horizontal ribbon ending at exitX,
  // then the far end (a thin vertical), then the bottom edge curves back into the trunk.
  function lanePath(lane) {
    if (lane.side === 'center') {
      return `M ${lane.xL} ${padTop} L ${lane.xR} ${padTop} L ${lane.xR} ${savedBottomY} L ${lane.xL} ${savedBottomY} Z`;
    }
    const isLeft = lane.side === 'left';
    const exitX = isLeft ? padX : width - padX;
    const ribbonTopY = lane.peelY - lane.w / 2;
    const ribbonBotY = lane.peelY + lane.w / 2;

    const outerX = isLeft ? lane.xL : lane.xR; // outer edge of bend (top of ribbon)
    const innerX = isLeft ? lane.xR : lane.xL; // inner edge of bend (bottom of ribbon)

    // d3-sankey style cubic bezier — midpoint control points create the smooth S-curve.
    // Outer edge curves earlier (smaller midY), inner edge later (larger midY) → wrap-around drape.
    const midY_outer = (padTop + ribbonTopY) / 2;
    const midY_inner = (padTop + ribbonBotY) / 2;

    return `M ${outerX} ${padTop}
            C ${outerX} ${midY_outer}, ${exitX} ${midY_outer}, ${exitX} ${ribbonTopY}
            L ${exitX} ${ribbonBotY}
            C ${exitX} ${midY_inner}, ${innerX} ${midY_inner}, ${innerX} ${padTop}
            Z`;
  }

  const trunkLeftEdge  = lanes[0].xL;
  const trunkRightEdge = lanes[lanes.length - 1].xR;
  const trunkMidX = (trunkLeftEdge + trunkRightEdge) / 2;

  // After-needs subtotal — drawn between the needs and wants peel sections
  const afterNeedsAmt = data.income - leftLanes.reduce((s, l) => s + l.amount, 0);
  const afterNeedsY   = padTop + 4 * peelStep + sectionGap / 2;
  // At afterNeedsY, the remaining trunk = Saved + all 5 right lanes
  const afterNeedsLeftX  = savedLane.xL;
  const afterNeedsRightX = rightLanes[rightLanes.length - 1].xR;

  // Unaccounted, for the callout
  const unaccountedLane = lanes.find(l => l.name === 'Unaccounted');

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id="wf-rain" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"  stopColor={t.accent} stopOpacity="0" />
          <stop offset="100%" stopColor={t.accent} stopOpacity="0.5" />
        </linearGradient>
        <pattern id="wf-hatch-success" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke={t.success} strokeWidth="3.5" />
        </pattern>
      </defs>

      {/* Income header — fades INTO the top of the trunk */}
      <g>
        <text x={trunkMidX} y={padTop - 46} textAnchor="middle"
              fontSize="10" fontWeight="700" fill={t.fgMuted}
              fontFamily="'Geist Mono', monospace"
              style={{ textTransform: 'uppercase', letterSpacing: '0.16em' }}>
          {data.month} · Income
        </text>
        <text x={trunkMidX} y={padTop - 22} textAnchor="middle"
              fontSize="20" fontWeight="700" fill={t.fgPrimary}
              fontFamily="'Geist Mono', monospace" letterSpacing="-0.02em">
          {fmt(data.income, privacy)}
        </text>
        <rect x={trunkLeftEdge} y={padTop - 14} width={trunkRightEdge - trunkLeftEdge} height={14}
              fill="url(#wf-rain)" />
      </g>

      {/* Section labels — anchored to the side they exit toward */}
      <text x={padX + 4} y={padTop + 4}
            fontSize="10" fontWeight="700" fill={t.fgMuted}
            fontFamily="'Geist Mono', monospace"
            style={{ textTransform: 'uppercase', letterSpacing: '0.18em' }}>
        ← NEEDS
      </text>
      <text x={width - padX - 4} y={padTop + 4} textAnchor="end"
            fontSize="10" fontWeight="700" fill={t.fgMuted}
            fontFamily="'Geist Mono', monospace"
            style={{ textTransform: 'uppercase', letterSpacing: '0.18em' }}>
        WANTS →
      </text>

      {/* "After needs" subtotal — sits in the gap between the two peel sections */}
      <g>
        <line x1={afterNeedsLeftX - 6} y1={afterNeedsY}
              x2={afterNeedsRightX + 6} y2={afterNeedsY}
              stroke={t.border} strokeWidth={1} strokeDasharray="3 2" />
        <text x={afterNeedsRightX + 14} y={afterNeedsY - 2}
              fontSize="11" fontWeight="600" fill={t.fgPrimary}
              fontFamily="'Geist Mono', monospace">
          {fmt(afterNeedsAmt, privacy)}
        </text>
        <text x={afterNeedsRightX + 14} y={afterNeedsY + 11}
              fontSize="9" fill={t.fgMuted}
              fontFamily="'Geist Mono', monospace"
              style={{ textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          After needs
        </text>
      </g>

      {/* THE LANES — each is a continuous ribbon from trunk top to exit */}
      {lanes.map((lane, i) => (
        <path key={i}
          d={lanePath(lane)}
          fill={lane.dashed ? 'none' : lane.color}
          fillOpacity={lane.dashed ? 0 : (lane.side === 'center' ? 0.48 : 0.62)}
          stroke={lane.color}
          strokeWidth={lane.dashed ? 1.4 : 0.5}
          strokeOpacity={lane.dashed ? 0.95 : 0.55}
          strokeDasharray={lane.dashed ? '4 3' : ''}
        />
      ))}

      {/* Exit labels — at the far end of each ribbon */}
      {lanes.filter(l => l.side !== 'center').map((lane, i) => {
        const isLeft = lane.side === 'left';
        const labelX = isLeft ? padX - 6 : width - padX + 6;
        return (
          <g key={`lbl-${i}`}>
            <text x={labelX} y={lane.peelY - 3}
                  textAnchor={isLeft ? 'end' : 'start'}
                  fontSize="11.5" fontWeight="600"
                  fill={lane.dashed ? t.warning : t.fgPrimary}
                  fontFamily="'Geist Mono', monospace">
              {fmt(lane.amount, privacy)}
            </text>
            <text x={labelX} y={lane.peelY + 11}
                  textAnchor={isLeft ? 'end' : 'start'}
                  fontSize="10" fill={t.fgMuted}
                  fontFamily="'Geist', sans-serif">
              {lane.name}
            </text>
          </g>
        );
      })}

      {/* Saved landing pad at the bottom — the punchline */}
      <g>
        {(() => {
          const cx = (savedLane.xL + savedLane.xR) / 2;
          const padW = 36;
          return (
            <>
              <rect x={savedLane.xL - 4} y={savedBottomY} width={savedLane.w + 8} height={4}
                    fill="url(#wf-hatch-success)" />
              <rect x={savedLane.xL - padW} y={savedBottomY + 6}
                    width={savedLane.w + 2 * padW} height={48}
                    fill={t.success} fillOpacity={0.14}
                    stroke={t.success} strokeWidth={1} rx={6} />
              <text x={cx} y={savedBottomY + 24} textAnchor="middle"
                    fontSize="10" fontWeight="700" fill={t.success}
                    fontFamily="'Geist Mono', monospace"
                    style={{ textTransform: 'uppercase', letterSpacing: '0.14em' }}>
                Saved
              </text>
              <text x={cx} y={savedBottomY + 45} textAnchor="middle"
                    fontSize="17" fontWeight="700" fill={t.success}
                    fontFamily="'Geist Mono', monospace"
                    letterSpacing="-0.02em">
                {fmt(savedLane.amount, privacy)}
              </text>
            </>
          );
        })()}
      </g>

      {/* "Where did it all go?" callout — under the Unaccounted ribbon */}
      {unaccountedLane && (() => {
        const u = unaccountedLane;
        const ribbonMidX = (u.xR + (width - padX)) / 2;
        const cy = u.peelY + u.w / 2 + 26;
        return (
          <g>
            <text x={ribbonMidX} y={cy} textAnchor="middle"
                  fontSize="11" fontStyle="italic" fontWeight="700"
                  fill={t.warning} fontFamily="'Geist', sans-serif">
              ↑ where did it all go?
            </text>
          </g>
        );
      })()}
    </svg>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// CARD MODAL — standard overlay modal for non-list flows
// (add account, share recap, edit goal, confirm destructive action…)
// ══════════════════════════════════════════════════════════════════════════════
function CardModal({ t, open, onClose, title, subtitle, children, footer, width = 480, kind = 'default' }) {
  const [mounted, setMounted] = React.useState(open);
  const [visible, setVisible] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setMounted(true);
      requestAnimationFrame(() => requestAnimationFrame(() => setVisible(true)));
    } else {
      setVisible(false);
      const timer = setTimeout(() => setMounted(false), 220);
      return () => clearTimeout(timer);
    }
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!mounted) return null;

  const accentByKind = { default: t.accent, danger: t.danger, success: t.success, warning: t.warning };
  const accent = accentByKind[kind] || t.accent;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'absolute', inset: 0, zIndex: 50,
        background: visible ? 'rgba(0,0,0,0.42)' : 'rgba(0,0,0,0)',
        backdropFilter: visible ? 'blur(2px)' : 'blur(0px)',
        WebkitBackdropFilter: visible ? 'blur(2px)' : 'blur(0px)',
        transition: 'background 0.22s ease, backdrop-filter 0.22s ease',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24, fontFamily: "'Geist', sans-serif",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true"
        style={{
          width, maxWidth: '100%', maxHeight: '88%',
          background: t.bgElevated, border: `1px solid ${t.border}`,
          borderTop: `2px solid ${accent}`, borderRadius: 14,
          boxShadow: '0 24px 64px -12px rgba(0,0,0,0.45), 0 8px 24px -8px rgba(0,0,0,0.3)',
          opacity: visible ? 1 : 0,
          transform: visible ? 'translateY(0) scale(1)' : 'translateY(8px) scale(0.97)',
          transition: 'opacity 0.22s ease, transform 0.22s cubic-bezier(0.22, 1, 0.36, 1)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        <div style={{ padding: '18px 22px 14px', display: 'flex', alignItems: 'flex-start', gap: 12, borderBottom: `1px solid ${t.border}` }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: t.fgPrimary, letterSpacing: '-0.01em' }}>{title}</div>
            {subtitle && <div style={{ fontSize: 12, color: t.fgMuted, marginTop: 3, lineHeight: 1.4 }}>{subtitle}</div>}
          </div>
          <button onClick={onClose} aria-label="Close"
            style={{ width: 26, height: 26, border: `1px solid ${t.border}`, background: 'transparent', borderRadius: 6, color: t.fgMuted, cursor: 'pointer', fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, padding: 0, lineHeight: 1 }}
          >×</button>
        </div>
        <div style={{ padding: '16px 22px', overflowY: 'auto', flex: 1 }}>{children}</div>
        {footer && (
          <div style={{ padding: '12px 22px', borderTop: `1px solid ${t.border}`, background: t.bgSecondary, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// MONTHLY RECAP SCREEN — "Where Did It All Go"
// ══════════════════════════════════════════════════════════════════════════════
function MonthlyRecapScreen({ t, privacy }) {
  const cats = catColors(t);
  const d = RECAP_DATA;
  const [period, setPeriod] = React.useState('April');
  const [flowMode, setFlowMode] = React.useState('sankey'); // 'sankey' | 'waterfall'
  const totalOut = d.flows.reduce((s, f) => s + f.amount, 0);
  const savedPct = Math.round((d.saved / d.income) * 100);
  const spentPct = Math.round((d.spent / d.income) * 100);
  const unaccountedPct = Math.round((d.unaccounted / d.income) * 100);
  const [shareOpen, setShareOpen] = React.useState(false);
  const [shareFormat, setShareFormat] = React.useState('image');
  const [includeAmounts, setIncludeAmounts] = React.useState(false);

  return (
    <div style={{ position: 'relative', display: 'flex', height: '100%', background: t.bgPrimary, fontFamily: "'Geist', sans-serif" }}>
      <Sidebar t={t} active="dashboard" />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Topbar */}
        <div style={{ padding: '18px 28px 14px', borderBottom: `1px solid ${t.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <span style={{ fontSize: 11, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Monthly Recap</span>
              <span style={{ fontSize: 11, color: t.fgMuted, fontFamily: "'Geist Mono', monospace" }}>· closed Apr 30</span>
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: t.fgPrimary, marginTop: 2, letterSpacing: '-0.01em' }}>
              Where did it all go in {d.month}?
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {['Mar', 'April', 'YTD'].map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                style={{ padding: '6px 12px', fontSize: 12, borderRadius: 6,
                  border: `1px solid ${period === p ? t.accent : t.border}`,
                  background: period === p ? `${t.accent}15` : 'none',
                  color: period === p ? t.accent : t.fgMuted, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>
                {p}
              </button>
            ))}
            <div style={{ width: 1, height: 18, background: t.border, margin: '0 4px' }} />
            <button onClick={() => setShareOpen(true)} style={{ padding: '6px 12px', fontSize: 12, borderRadius: 6, border: `1px solid ${t.border}`, background: 'none', color: t.fgSecondary, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>Share recap</button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '18px 28px 28px' }}>
          {/* Headline strip — three numbers that tell the story */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 12, marginBottom: 18 }}>
            <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 12, padding: '14px 16px' }}>
              <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Earned</div>
              <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary, marginTop: 4, letterSpacing: '-0.02em' }}>{fmt(d.income, privacy)}</div>
              <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>1 paycheck · 2 dep.</div>
            </div>
            <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 12, padding: '14px 16px' }}>
              <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Spent</div>
              <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary, marginTop: 4, letterSpacing: '-0.02em' }}>{fmt(d.spent, privacy)}</div>
              <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>{spentPct}% of income</div>
            </div>
            <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 12, padding: '14px 16px' }}>
              <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Saved</div>
              <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.success, marginTop: 4, letterSpacing: '-0.02em' }}>{fmt(d.saved, privacy)}</div>
              <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>{savedPct}% rate</div>
            </div>
            <div style={{ background: `${t.warning}10`, border: `1px solid ${t.warning}40`, borderRadius: 12, padding: '14px 16px', position: 'relative' }}>
              <div style={{ fontSize: 10, color: t.warning, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Unaccounted</div>
              <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.warning, marginTop: 4, letterSpacing: '-0.02em' }}>{fmt(d.unaccounted, privacy)}</div>
              <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>{unaccountedPct}% · 14 transactions</div>
            </div>
          </div>

          {/* Sankey card */}
          <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 14, padding: '20px 24px 16px', marginBottom: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: t.fgPrimary }}>Money flow</div>
                <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>Where every dollar earned in {d.month} ended up</div>
              </div>
              <div style={{ display: 'flex', gap: 12, fontSize: 11, color: t.fgMuted, alignItems: 'center' }}>
                {/* Variant toggle */}
                <div style={{ display: 'flex', borderRadius: 6, border: `1px solid ${t.border}`, overflow: 'hidden' }}>
                  {[
                    { k: 'sankey',    l: 'Sankey' },
                    { k: 'waterfall', l: 'Waterfall' },
                  ].map(opt => (
                    <button key={opt.k} onClick={() => setFlowMode(opt.k)}
                      style={{ padding: '5px 10px', fontSize: 11, border: 'none', cursor: 'pointer',
                        background: flowMode === opt.k ? `${t.accent}15` : 'transparent',
                        color: flowMode === opt.k ? t.accent : t.fgMuted, fontFamily: "'Geist', sans-serif",
                        fontWeight: flowMode === opt.k ? 600 : 400 }}>
                      {opt.l}
                    </button>
                  ))}
                </div>
                <div style={{ width: 1, height: 14, background: t.border }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: t.success }} /> saved
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: `${t.warning}80`, border: `1px dashed ${t.warning}` }} /> unaccounted
                </div>
              </div>
            </div>
            {flowMode === 'sankey'
              ? <SankeyFlow t={t} data={d} privacy={privacy} width={1080} height={340} />
              : <WaterfallFlow t={t} data={d} privacy={privacy} width={1080} height={680} />}
          </div>

          {/* AI narrative + biggest surprise + week burn */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr 1fr', gap: 12, marginBottom: 18 }}>
            {/* Narrative */}
            <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <div style={{ width: 22, height: 22, borderRadius: 6, background: `${t.accent}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 11, color: t.accent, fontFamily: "'Geist Mono', monospace", fontWeight: 600 }}>AI</span>
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: t.fgPrimary }}>The story of April</span>
                <span style={{ fontSize: 10, color: t.fgMuted, marginLeft: 'auto' }}>generated 2h ago</span>
              </div>
              <div style={{ fontSize: 13, color: t.fgSecondary, lineHeight: 1.55 }}>
                You earned <span style={{ color: t.fgPrimary, fontWeight: 500 }}>{fmt(d.income, privacy)}</span> in {d.month} and spent <span style={{ color: t.fgPrimary, fontWeight: 500 }}>{fmt(d.spent, privacy)}</span>{' '}— a {savedPct}% savings rate, your best since January.{' '}
                <span style={{ background: `${t.warning}1c`, color: t.fgPrimary, padding: '1px 4px', borderRadius: 3 }}>Dining nearly doubled</span>{' '}vs March, mostly weekday lunch orders.
                You finished the month with <span style={{ color: t.warning, fontWeight: 500 }}>{fmt(d.unaccounted, privacy)} unaccounted</span> — small recurring charges and ATM cash that didn't get categorized.
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
                <button style={{ fontSize: 11, padding: '5px 10px', borderRadius: 6, border: `1px solid ${t.border}`, background: t.bgSecondary, color: t.fgSecondary, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>Drill into dining</button>
                <button style={{ fontSize: 11, padding: '5px 10px', borderRadius: 6, border: `1px solid ${t.border}`, background: t.bgSecondary, color: t.fgSecondary, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>Categorize the unaccounted</button>
              </div>
            </div>

            {/* Biggest surprise */}
            <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Biggest surprise</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 6 }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: t.fgPrimary }}>{d.surprise.title}</span>
                <span style={{ fontSize: 13, color: t.danger, fontFamily: "'Geist Mono', monospace" }}>+{fmt(d.surprise.delta)}</span>
              </div>
              <div style={{ fontSize: 12, color: t.fgSecondary, lineHeight: 1.55, marginTop: 8 }}>{d.surprise.body}</div>
              {/* Mini comparison bar */}
              <div style={{ marginTop: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: t.fgMuted, marginBottom: 4 }}>
                  <span>March</span><span>April</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 60 }}>
                  <div style={{ flex: 1, background: cats[d.surprise.catColor], opacity: 0.4, borderRadius: 4, height: `${(210 / 389) * 100}%`, position: 'relative' }}>
                    <span style={{ position: 'absolute', top: -16, left: 0, right: 0, textAlign: 'center', fontSize: 10, color: t.fgMuted, fontFamily: "'Geist Mono', monospace" }}>$210</span>
                  </div>
                  <div style={{ flex: 1, background: cats[d.surprise.catColor], borderRadius: 4, height: '100%', position: 'relative' }}>
                    <span style={{ position: 'absolute', top: -16, left: 0, right: 0, textAlign: 'center', fontSize: 10, color: t.fgPrimary, fontWeight: 600, fontFamily: "'Geist Mono', monospace" }}>$389</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Week-by-week burn */}
            <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Burn rate by week</div>
              <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 9 }}>
                {d.weeklyBurn.map((w, i) => {
                  const max = 1500;
                  return (
                    <div key={i}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                        <span style={{ color: t.fgSecondary }}>{w.label}</span>
                        <span style={{ color: t.fgMuted, fontFamily: "'Geist Mono', monospace" }}>{fmt(w.expense, privacy)}{w.income > 0 && <span style={{ color: t.success }}> · +{fmt(w.income, privacy)}</span>}</span>
                      </div>
                      <div style={{ position: 'relative', height: 6, background: t.border, borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(w.expense / max) * 100}%`, background: t.danger, opacity: 0.7, borderRadius: 99 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Top merchants */}
          <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 14, padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: t.fgPrimary }}>Top merchants</div>
                <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>Where you sent the most money in {d.month}</div>
              </div>
              <span style={{ fontSize: 11, color: t.accent, cursor: 'pointer' }}>See all →</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
              {d.topMerchants.map((m, i) => (
                <div key={i} style={{ background: t.bgSecondary, border: `1px solid ${t.border}`, borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: cats[m.catColor] }} />
                    <span style={{ fontSize: 11, color: t.fgMuted }}>{m.cat}</span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.fgPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.name}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary, marginTop: 4 }}>{fmt(m.total, privacy)}</div>
                  <div style={{ fontSize: 10, color: t.fgMuted, marginTop: 2 }}>{m.count} {m.count === 1 ? 'visit' : 'visits'} · {m.trend > 0 ? <span style={{ color: t.danger }}>↑{m.trend.toFixed(1)}×</span> : m.trend < 0 ? <span style={{ color: t.success }}>↓</span> : <span>—</span>}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Share recap modal — demonstrates the standard CardModal pattern */}
      <CardModal
        t={t}
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        title={`Share your ${d.month} recap`}
        subtitle="Pick a format. We'll generate it without revealing exact dollar amounts unless you opt in."
        width={460}
        footer={
          <>
            <button onClick={() => setShareOpen(false)}
              style={{ padding: '8px 14px', fontSize: 12, fontWeight: 500, borderRadius: 6, border: `1px solid ${t.border}`, background: 'transparent', color: t.fgSecondary, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>
              Cancel
            </button>
            <button onClick={() => setShareOpen(false)}
              style={{ padding: '8px 14px', fontSize: 12, fontWeight: 600, borderRadius: 6, border: `1px solid ${t.accent}`, background: t.accent, color: '#fff', cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>
              Generate
            </button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <div style={{ fontSize: 11, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, marginBottom: 8 }}>Format</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              {[
                { k: 'image',    l: 'Image card',  s: 'PNG · 1080×1350' },
                { k: 'story',    l: 'Story',       s: 'Vertical · 9:16' },
                { k: 'link',     l: 'Read-only link', s: 'expires in 7d' },
              ].map(opt => (
                <button key={opt.k} onClick={() => setShareFormat(opt.k)}
                  style={{ textAlign: 'left', padding: '10px 12px', borderRadius: 8,
                    border: `1px solid ${shareFormat === opt.k ? t.accent : t.border}`,
                    background: shareFormat === opt.k ? `${t.accent}10` : 'transparent',
                    cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: shareFormat === opt.k ? t.accent : t.fgPrimary }}>{opt.l}</div>
                  <div style={{ fontSize: 10, color: t.fgMuted, marginTop: 2, fontFamily: "'Geist Mono', monospace" }}>{opt.s}</div>
                </button>
              ))}
            </div>
          </div>

          <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px', border: `1px solid ${t.border}`, borderRadius: 8, cursor: 'pointer' }}>
            <input type="checkbox" checked={includeAmounts} onChange={(e) => setIncludeAmounts(e.target.checked)}
              style={{ marginTop: 2, accentColor: t.accent }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 500, color: t.fgPrimary }}>Include exact amounts</div>
              <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2, lineHeight: 1.4 }}>
                Off by default. Recipients see relative bars and percentages only.
              </div>
            </div>
          </label>

          <div style={{ background: t.bgSecondary, border: `1px dashed ${t.border}`, borderRadius: 8, padding: '12px 14px', fontSize: 11, color: t.fgMuted, lineHeight: 1.5 }}>
            <span style={{ color: t.fgSecondary, fontWeight: 600 }}>Preview:</span> The story of {d.month} · {savedPct}% saved · {includeAmounts ? `${fmt(d.unaccounted)} unaccounted` : '~12% unaccounted'}.
          </div>
        </div>
      </CardModal>
    </div>
  );
}
// ══════════════════════════════════════════════════════════════════════════════
function SubscriptionAuditScreen({ t, privacy }) {
  const cats = catColors(t);
  const [expandedId, setExpandedId] = React.useState('s1');
  const [filter, setFilter] = React.useState('all');

  const monthlyTotal = SUBS_DATA
    .filter(s => s.cycle === 'monthly').reduce((sum, s) => sum + s.current, 0)
    + SUBS_DATA.filter(s => s.cycle === 'yearly').reduce((sum, s) => sum + s.current / 12, 0);
  const yearlyTotal = monthlyTotal * 12;
  const lifetimeTotal = SUBS_DATA.reduce((sum, s) => sum + s.lifetimeSpent, 0);
  const ghosts = SUBS_DATA.filter(s => s.ghost);
  const ghostMonthly = ghosts.reduce((sum, s) => sum + (s.cycle === 'monthly' ? s.current : s.current / 12), 0);
  const monthlyBudget = SAMPLE.monthlyBudget;
  const pctOfBudget = Math.round((monthlyTotal / monthlyBudget) * 100);

  const filtered = filter === 'ghosts' ? SUBS_DATA.filter(s => s.ghost)
                 : filter === 'creep'  ? SUBS_DATA.filter(s => s.priceCreep)
                 : SUBS_DATA;

  return (
    <div style={{ display: 'flex', height: '100%', background: t.bgPrimary, fontFamily: "'Geist', sans-serif" }}>
      <Sidebar t={t} active="txn" />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Topbar */}
        <div style={{ padding: '18px 28px 14px', borderBottom: `1px solid ${t.border}`, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexShrink: 0 }}>
          <div>
            <div style={{ fontSize: 11, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Subscription Audit</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: t.fgPrimary, marginTop: 2, letterSpacing: '-0.01em' }}>{SUBS_DATA.length} active subscriptions</div>
          </div>
          <button style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, background: t.accent, color: t.accentFg, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 500 }}>
            {icons.plus} Track new
          </button>
        </div>

        {/* Stat strip */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, background: t.border, borderBottom: `1px solid ${t.border}`, flexShrink: 0 }}>
          <div style={{ background: t.bgPrimary, padding: '14px 24px' }}>
            <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Monthly</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary, marginTop: 4, letterSpacing: '-0.02em' }}>{fmt(monthlyTotal, privacy)}</div>
            <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>{pctOfBudget}% of monthly budget</div>
            <div style={{ position: 'relative', height: 4, background: t.border, borderRadius: 99, overflow: 'hidden', marginTop: 6 }}>
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pctOfBudget}%`, background: t.accent, borderRadius: 99 }} />
            </div>
          </div>
          <div style={{ background: t.bgPrimary, padding: '14px 24px' }}>
            <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Annualized</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary, marginTop: 4, letterSpacing: '-0.02em' }}>{fmt(yearlyTotal, privacy)}</div>
            <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>at current prices</div>
          </div>
          <div style={{ background: t.bgPrimary, padding: '14px 24px' }}>
            <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Lifetime spent</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary, marginTop: 4, letterSpacing: '-0.02em' }}>{fmt(lifetimeTotal, privacy)}</div>
            <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>across {SUBS_DATA.length} services</div>
          </div>
          <div style={{ background: `${t.danger}10`, padding: '14px 24px', borderLeft: `1px solid ${t.danger}40` }}>
            <div style={{ fontSize: 10, color: t.danger, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Ghost subs</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.danger, marginTop: 4, letterSpacing: '-0.02em' }}>{fmt(ghostMonthly, privacy)}</div>
            <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>{ghosts.length} unused · {fmt(ghostMonthly * 12)}/yr if cancelled</div>
          </div>
        </div>

        {/* Filter row */}
        <div style={{ display: 'flex', gap: 6, padding: '12px 28px', borderBottom: `1px solid ${t.border}`, flexShrink: 0 }}>
          {[
            { id: 'all', label: `All (${SUBS_DATA.length})` },
            { id: 'ghosts', label: `Ghosts (${ghosts.length})` },
            { id: 'creep', label: `Price creep (${SUBS_DATA.filter(s => s.priceCreep).length})` },
          ].map(f => (
            <button key={f.id} onClick={() => setFilter(f.id)}
              style={{ padding: '5px 12px', fontSize: 12, borderRadius: 6,
                border: `1px solid ${filter === f.id ? t.accent : t.border}`,
                background: filter === f.id ? `${t.accent}15` : 'none',
                color: filter === f.id ? t.accent : t.fgMuted, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>
              {f.label}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 11, color: t.fgMuted, alignSelf: 'center', fontFamily: "'Geist Mono', monospace" }}>sorted by lifetime spent ↓</span>
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* Column header */}
          <div style={{ display: 'grid', gridTemplateColumns: '32px 2fr 1.4fr 1fr 1.2fr 1.4fr 100px', gap: 16, padding: '10px 28px', borderBottom: `1px solid ${t.border}`, position: 'sticky', top: 0, background: t.bgPrimary, zIndex: 1 }}>
            {['', 'Service', 'Price now · cycle', '% budget', 'Last used', 'Price history (lifetime)', 'Lifetime $'].map((c, i) => (
              <div key={i} style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, textAlign: i === 6 || i === 3 ? 'right' : 'left' }}>{c}</div>
            ))}
          </div>

          {filtered.sort((a, b) => b.lifetimeSpent - a.lifetimeSpent).map((s) => {
            const isExpanded = expandedId === s.id;
            const monthlyEquiv = s.cycle === 'monthly' ? s.current : s.current / 12;
            const subPctBudget = (monthlyEquiv / monthlyBudget) * 100;
            const priceFirst = s.history[0];
            const priceCreep = s.history[s.history.length - 1] - priceFirst;
            const priceCreepPct = Math.round((priceCreep / priceFirst) * 100);
            const yearsActive = (s.lifetimeSpent / (monthlyEquiv * 12)).toFixed(1);

            return (
              <React.Fragment key={s.id}>
                {/* Row */}
                <div
                  onClick={() => setExpandedId(isExpanded ? null : s.id)}
                  style={{
                    display: 'grid', gridTemplateColumns: '32px 2fr 1.4fr 1fr 1.2fr 1.4fr 100px', gap: 16,
                    alignItems: 'center', padding: '14px 28px',
                    borderBottom: `1px solid ${t.border}`,
                    cursor: 'pointer',
                    background: isExpanded ? `${t.accent}08` : 'transparent',
                    transition: 'background 0.12s',
                  }}
                >
                  {/* Status dot */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.ghost ? t.danger : s.priceCreep ? t.warning : t.success, opacity: 0.85 }} />
                  </div>
                  {/* Service */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: t.fgPrimary }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: t.fgMuted, fontFamily: "'Geist Mono', monospace" }}>{s.merchant}</div>
                  </div>
                  {/* Price · cycle */}
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary }}>{fmt(s.current, privacy)}</div>
                    <div style={{ fontSize: 11, color: t.fgMuted }}>{s.cycle} · next {s.nextCharge.replace(', 2026', '')}</div>
                  </div>
                  {/* % budget */}
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 13, fontWeight: 500, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary }}>{subPctBudget.toFixed(1)}%</div>
                    <div style={{ position: 'relative', height: 3, background: t.border, borderRadius: 99, overflow: 'hidden', marginTop: 4 }}>
                      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${Math.min(100, subPctBudget * 8)}%`, background: cats[s.catColor], borderRadius: 99 }} />
                    </div>
                  </div>
                  {/* Last used */}
                  <div>
                    <div style={{ fontSize: 12, color: s.ghost ? t.danger : t.fgPrimary, fontWeight: s.ghost ? 600 : 400 }}>{s.lastUsed}</div>
                    {s.ghost && <div style={{ fontSize: 10, color: t.danger, marginTop: 1 }}>👻 likely unused</div>}
                  </div>
                  {/* Sparkline */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 10, color: t.fgMuted, fontFamily: "'Geist Mono', monospace" }}>{fmt(priceFirst).replace('.00', '')}</span>
                    <PriceHistory data={s.history} t={t} width={90} height={26} />
                    {priceCreep > 0 && (
                      <span style={{ fontSize: 10, color: t.danger, fontFamily: "'Geist Mono', monospace", fontWeight: 500 }}>+{priceCreepPct}%</span>
                    )}
                  </div>
                  {/* Lifetime */}
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary }}>{fmt(s.lifetimeSpent, privacy)}</div>
                    <div style={{ fontSize: 10, color: t.fgMuted }}>over {yearsActive}y</div>
                  </div>
                </div>

                {/* Expansion: split-and-expand inline detail card (animated) */}
                <div style={{
                  display: 'grid',
                  gridTemplateRows: isExpanded ? '1fr' : '0fr',
                  transition: 'grid-template-rows 0.32s cubic-bezier(0.22, 1, 0.36, 1)',
                }}>
                <div style={{ overflow: 'hidden', minHeight: 0 }}>
                <div style={{
                  opacity: isExpanded ? 1 : 0,
                  transform: isExpanded ? 'translateY(0)' : 'translateY(-6px)',
                  transition: 'opacity 0.24s ease 0.06s, transform 0.32s cubic-bezier(0.22, 1, 0.36, 1)',
                }}>
                {isExpanded && (
                  <div style={{
                    background: t.bgSecondary,
                    borderBottom: `1px solid ${t.border}`,
                    boxShadow: `inset 0 1px 0 ${t.accent}40, inset 0 -1px 0 ${t.border}`,
                    padding: '20px 28px 22px',
                    display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr', gap: 16,
                  }}>
                    {/* Big price-history chart */}
                    <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 12, padding: '16px 18px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: t.fgPrimary }}>Price over time</div>
                        <div style={{ fontSize: 10, color: t.fgMuted, fontFamily: "'Geist Mono', monospace" }}>{s.activeSince} → now</div>
                      </div>
                      <BigPriceChart data={s.history} t={t} privacy={privacy} accentColor={cats[s.catColor]} />
                      {priceCreep > 0 && (
                        <div style={{ marginTop: 10, padding: '8px 10px', background: `${t.warning}12`, borderRadius: 6, border: `1px solid ${t.warning}30`, fontSize: 11, color: t.fgSecondary }}>
                          <span style={{ color: t.warning, fontWeight: 600 }}>Price creep:</span> {fmt(priceFirst)} → {fmt(s.history[s.history.length - 1])} (<span style={{ color: t.danger, fontFamily: "'Geist Mono', monospace" }}>+{priceCreepPct}%</span>) over {yearsActive}y.
                        </div>
                      )}
                    </div>

                    {/* "What you've spent" intel */}
                    <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 12, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: t.fgPrimary }}>Intelligence</div>

                      <div>
                        <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>Lifetime spent</div>
                        <div style={{ fontSize: 24, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary, letterSpacing: '-0.02em' }}>{fmt(s.lifetimeSpent, privacy)}</div>
                        <div style={{ fontSize: 11, color: t.fgMuted, marginTop: 2 }}>over {yearsActive} years</div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: `1px solid ${t.border}`, paddingTop: 10 }}>
                        <div>
                          <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>If you cancel</div>
                          <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'Geist Mono', monospace", color: t.success, marginTop: 2 }}>+{fmt(monthlyEquiv * 12)}/yr</div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>5-yr proj.</div>
                          <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary, marginTop: 2 }}>{fmt(monthlyEquiv * 60)}</div>
                        </div>
                      </div>

                      <div style={{ borderTop: `1px solid ${t.border}`, paddingTop: 10 }}>
                        <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>% of monthly budget</div>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                          <span style={{ fontSize: 18, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: cats[s.catColor] }}>{subPctBudget.toFixed(1)}%</span>
                          <span style={{ fontSize: 11, color: t.fgMuted }}>of {fmt(monthlyBudget)}</span>
                        </div>
                      </div>

                      {s.ghost && (
                        <div style={{ background: `${t.danger}10`, border: `1px solid ${t.danger}30`, borderRadius: 8, padding: '8px 10px', fontSize: 11, color: t.fgSecondary, lineHeight: 1.5 }}>
                          <span style={{ fontWeight: 600, color: t.danger }}>👻 Ghost detected.</span> Last activity {s.lastUsed.toLowerCase()}. You've paid <span style={{ color: t.fgPrimary, fontFamily: "'Geist Mono', monospace" }}>{fmt(monthlyEquiv * 4)}</span> since you stopped using it.
                        </div>
                      )}
                    </div>

                    {/* Meta panel — v1 read-only, no destructive actions */}
                    <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 12, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: t.fgPrimary }}>Details</div>
                      {[
                        { l: 'Charged to', v: s.account, mono: true },
                        { l: 'Plan',       v: s.plan },
                        { l: 'Cycle',      v: s.cycle },
                        { l: 'Next charge',v: s.nextCharge + ` (${s.daysUntil}d)` },
                        { l: 'Active since', v: s.activeSince },
                        { l: 'Category',   v: s.cat, swatch: cats[s.catColor] },
                      ].map((row, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: i < 5 ? `1px solid ${t.border}` : 'none' }}>
                          <span style={{ fontSize: 11, color: t.fgMuted }}>{row.l}</span>
                          <span style={{ fontSize: 11, color: t.fgPrimary, fontWeight: 500, fontFamily: row.mono ? "'Geist Mono', monospace" : undefined, display: 'flex', alignItems: 'center', gap: 5 }}>
                            {row.swatch && <div style={{ width: 7, height: 7, borderRadius: '50%', background: row.swatch }} />}
                            {row.v}
                          </span>
                        </div>
                      ))}
                      <div style={{ fontSize: 10, color: t.fgMuted, fontStyle: 'italic', marginTop: 2 }}>Manage actions — coming in v2</div>
                    </div>
                  </div>
                )}
                </div>
                </div>
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Larger, labeled price chart for the expanded sub view
function BigPriceChart({ data, t, privacy, accentColor }) {
  const W = 360, H = 100;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 18) - 10;
    return [x, y, v];
  });
  const path = `M ${pts.map(p => `${p[0]},${p[1]}`).join(' L ')}`;
  const fillPath = `${path} L ${W},${H} L 0,${H} Z`;
  // Detect price step changes
  const steps = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i] !== data[i - 1]) steps.push({ i, from: data[i - 1], to: data[i] });
  }
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id="bp-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={accentColor} stopOpacity="0.22" />
          <stop offset="100%" stopColor={accentColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={fillPath} fill="url(#bp-fill)" />
      <path d={path} fill="none" stroke={accentColor} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
      {/* Step markers */}
      {steps.slice(0, 6).map((s, i) => {
        const p = pts[s.i];
        return (
          <g key={i}>
            <circle cx={p[0]} cy={p[1]} r={3} fill={t.bgElevated} stroke={accentColor} strokeWidth={1.5} />
            <text x={p[0]} y={p[1] - 8} textAnchor="middle" fontSize="9" fill={t.fgMuted} fontFamily="'Geist Mono', monospace">${s.to}</text>
          </g>
        );
      })}
      {/* Start label */}
      <text x={2} y={H - 2} fontSize="9" fill={t.fgMuted} fontFamily="'Geist Mono', monospace">${data[0]}</text>
      {/* End label */}
      <text x={W - 2} y={pts[pts.length - 1][1] - 6} textAnchor="end" fontSize="10" fill={t.fgPrimary} fontWeight="600" fontFamily="'Geist Mono', monospace">${data[data.length - 1]}</text>
    </svg>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SPLIT-AND-EXPAND TX FEED — clicking a row splits the list and expands inline
// (replacing the modal pattern with this where appropriate)
// ══════════════════════════════════════════════════════════════════════════════
function SplitExpandTxFeed({ t, privacy, transactions, expandedTxId, onSelect }) {
  const cats = catColors(t);

  return (
    <div>
      {transactions.map((tx, i) => {
        const isExpanded = expandedTxId === tx.id;
        const color = cats[tx.catColor] || cats[0];
        return (
          <React.Fragment key={tx.id || i}>
            {/* Compact row */}
            <div
              onClick={() => onSelect(isExpanded ? null : tx.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 8px', margin: '0 -8px',
                borderBottom: `1px solid ${t.border}`,
                cursor: 'pointer',
                background: isExpanded ? `${t.accent}10` : 'transparent',
                borderLeft: `2px solid ${isExpanded ? t.accent : 'transparent'}`,
                paddingLeft: isExpanded ? 14 : 8,
                transition: 'all 0.15s',
              }}
            >
              <div style={{ width: 32, height: 32, borderRadius: 8, flexShrink: 0, background: `${color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: t.fgPrimary }}>{tx.merchant}</div>
                <div style={{ fontSize: 11, color: t.fgMuted }}>
                  {tx.cat} · {tx.date}{!tx.posted ? ' · pending' : ''}
                  {tx.aiConfidence !== undefined && (
                    <span style={{ marginLeft: 6, color: tx.aiConfidence < 70 ? t.warning : t.fgMuted }}>
                      · AI {tx.aiConfidence}%
                    </span>
                  )}
                </div>
              </div>
              <div style={{ fontSize: 13, fontWeight: 500, fontFamily: "'Geist Mono', monospace", color: tx.amount > 0 ? t.success : t.fgPrimary, flexShrink: 0 }}>
                {tx.amount > 0 ? '+' : ''}{fmt(tx.amount, privacy)}
              </div>
            </div>

            {/* Inline expansion — splits list */}
            <div
              style={{
                display: 'grid',
                gridTemplateRows: isExpanded ? '1fr' : '0fr',
                transition: 'grid-template-rows 0.32s cubic-bezier(0.22, 1, 0.36, 1)',
              }}
            >
              <div style={{ overflow: 'hidden', minHeight: 0 }}>
                <div
                  style={{
                    opacity: isExpanded ? 1 : 0,
                    transform: isExpanded ? 'translateY(0)' : 'translateY(-6px)',
                    transition: 'opacity 0.24s ease 0.06s, transform 0.32s cubic-bezier(0.22, 1, 0.36, 1)',
                  }}
                >
                  {isExpanded && (
                    <TxDetailExpansion tx={tx} t={t} privacy={privacy} color={color} onClose={() => onSelect(null)} />
                  )}
                </div>
              </div>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

// The actual expanded detail card. Lives between rows.
function TxDetailExpansion({ tx, t, privacy, color, onClose }) {
  const isIncome = tx.amount > 0;
  const aiConf = tx.aiConfidence ?? 92;
  const lowConf = aiConf < 70;
  const cats = catColors(t);
  // Mock similar past transactions
  const similar = [
    { date: 'Apr 23', amount: -86.40 },
    { date: 'Apr 16', amount: -102.18 },
    { date: 'Apr 9',  amount: -78.55 },
    { date: 'Apr 2',  amount: -91.32 },
  ];
  const avgSimilar = similar.reduce((s, x) => s + Math.abs(x.amount), 0) / similar.length;
  const isAbove = Math.abs(tx.amount) > avgSimilar;

  return (
    <div style={{
      background: t.bgSecondary,
      margin: '0 -8px',
      padding: '18px 20px 20px',
      borderBottom: `1px solid ${t.border}`,
      borderLeft: `2px solid ${t.accent}`,
      boxShadow: `inset 0 1px 0 ${t.accent}30`,
    }}>
      {/* Header line */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 11, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>Transaction</div>
          <div style={{ fontSize: 24, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: isIncome ? t.success : t.fgPrimary, marginTop: 2, letterSpacing: '-0.02em' }}>
            {isIncome ? '+' : ''}{fmt(tx.amount, privacy)}
          </div>
          <div style={{ fontSize: 12, color: t.fgMuted, marginTop: 2, fontFamily: "'Geist Mono', monospace" }}>{tx.rawDescriptor || tx.merchant.toUpperCase() + ' #2148'}</div>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: t.fgMuted, fontSize: 16, cursor: 'pointer', padding: 4 }}>✕</button>
      </div>

      {/* 3-column body */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 12 }}>
        {/* HITL "Why this category?" — the differentiator */}
        <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 10, padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <div style={{ width: 18, height: 18, borderRadius: 4, background: `${t.accent}20`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontSize: 9, color: t.accent, fontFamily: "'Geist Mono', monospace", fontWeight: 700 }}>AI</span>
            </div>
            <span style={{ fontSize: 12, fontWeight: 600, color: t.fgPrimary }}>Why this category?</span>
          </div>
          <div style={{ fontSize: 12, color: t.fgSecondary, lineHeight: 1.55 }}>
            Matched <span style={{ background: `${color}22`, color: t.fgPrimary, padding: '1px 5px', borderRadius: 3, fontWeight: 500 }}>{tx.cat}</span> from your rule "<span style={{ color: t.fgPrimary }}>Whole Foods → Groceries</span>" + 14 prior charges at this merchant.
          </div>

          {/* Confidence bar */}
          <div style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: t.fgMuted, marginBottom: 4 }}>
              <span>Confidence</span>
              <span style={{ color: lowConf ? t.warning : t.success, fontWeight: 600, fontFamily: "'Geist Mono', monospace" }}>{aiConf}%</span>
            </div>
            <div style={{ position: 'relative', height: 5, background: t.border, borderRadius: 99, overflow: 'hidden' }}>
              <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${aiConf}%`, background: lowConf ? t.warning : t.success, borderRadius: 99 }} />
            </div>
          </div>

          {/* Recategorize affordance */}
          <div style={{ marginTop: 12, fontSize: 11, color: t.fgMuted }}>Re-categorize as:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 6 }}>
            {['Groceries', 'Dining', 'Shopping', 'Other'].map((c, i) => (
              <button key={i} style={{
                padding: '4px 10px', fontSize: 11, borderRadius: 99,
                border: `1px solid ${c === tx.cat ? t.accent : t.border}`,
                background: c === tx.cat ? `${t.accent}15` : t.bgSecondary,
                color: c === tx.cat ? t.accent : t.fgSecondary,
                cursor: 'pointer', fontFamily: "'Geist', sans-serif",
              }}>{c}</button>
            ))}
          </div>
          <div style={{ fontSize: 10, color: t.fgMuted, marginTop: 8, fontStyle: 'italic' }}>Changing this will retrain the rule on 14 past transactions.</div>
        </div>

        {/* Context: how does this compare? */}
        <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 10, padding: '14px 16px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: t.fgPrimary, marginBottom: 10 }}>In context</div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>vs. avg at this merchant</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ fontSize: 16, fontWeight: 700, fontFamily: "'Geist Mono', monospace", color: t.fgPrimary }}>{fmt(Math.abs(tx.amount))}</span>
              <span style={{ fontSize: 11, color: isAbove ? t.warning : t.success, fontFamily: "'Geist Mono', monospace" }}>
                {isAbove ? '↑' : '↓'} {fmt(Math.abs(Math.abs(tx.amount) - avgSimilar))} vs {fmt(avgSimilar)} avg
              </span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: 10, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Last 4 visits</div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 36 }}>
              {[...similar, { date: 'Today', amount: tx.amount }].map((s, i) => {
                const max = Math.max(...similar.map(x => Math.abs(x.amount)), Math.abs(tx.amount));
                const h = (Math.abs(s.amount) / max) * 100;
                const isCurrent = s.date === 'Today';
                return (
                  <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                    <div style={{ width: '100%', height: `${h}%`, background: isCurrent ? color : `${color}55`, borderRadius: 2 }} />
                    <span style={{ fontSize: 9, color: isCurrent ? t.fgPrimary : t.fgMuted, fontFamily: "'Geist Mono', monospace" }}>{s.date}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div style={{ marginTop: 12, fontSize: 11, color: t.fgSecondary, lineHeight: 1.5 }}>
            This is your <span style={{ color: t.fgPrimary, fontWeight: 500 }}>5th visit</span> in 30 days. Avg ticket: <span style={{ fontFamily: "'Geist Mono', monospace" }}>{fmt(avgSimilar)}</span>.
          </div>
        </div>

        {/* Meta + actions */}
        <div style={{ background: t.bgElevated, border: `1px solid ${t.border}`, borderRadius: 10, padding: '14px 16px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: t.fgPrimary, marginBottom: 10 }}>Details</div>

          {[
            { l: 'Account', v: tx.account || 'Chase Checking ···4821' },
            { l: 'Posted',  v: tx.posted ? 'Yes' : 'Pending', vc: tx.posted ? t.success : t.warning },
            { l: 'Method',  v: 'Card · contactless' },
            { l: 'Location',v: 'San Francisco, CA' },
          ].map((row, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: i < 3 ? `1px solid ${t.border}` : 'none' }}>
              <span style={{ fontSize: 11, color: t.fgMuted }}>{row.l}</span>
              <span style={{ fontSize: 11, color: row.vc || t.fgPrimary, fontWeight: 500 }}>{row.v}</span>
            </div>
          ))}

          <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
            <button style={{ flex: 1, padding: '7px', borderRadius: 6, border: `1px solid ${t.border}`, background: 'none', color: t.fgSecondary, fontSize: 11, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>Split</button>
            <button style={{ flex: 1, padding: '7px', borderRadius: 6, border: `1px solid ${t.border}`, background: 'none', color: t.fgSecondary, fontSize: 11, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>Receipt</button>
            <button style={{ flex: 1, padding: '7px', borderRadius: 6, border: `1px solid ${t.border}`, background: 'none', color: t.fgSecondary, fontSize: 11, cursor: 'pointer', fontFamily: "'Geist', sans-serif" }}>Hide</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// TX DETAIL DEMO SCREEN — shows the split-and-expand pattern in a transactions list
// ══════════════════════════════════════════════════════════════════════════════
function TxDetailScreen({ t, privacy }) {
  const [expandedTxId, setExpandedTxId] = React.useState('tx2');

  const txs = [
    { id: 'tx1', merchant: 'Trader Joe\'s',   amount: -62.14, cat: 'Groceries',     catColor: 1, date: 'Today',  posted: true, aiConfidence: 99, account: 'Chase Checking ···4821', rawDescriptor: 'TJOE #128 SAN FRANCISCO CA' },
    { id: 'tx2', merchant: 'Whole Foods',     amount: -94.32, cat: 'Groceries',     catColor: 1, date: 'Today',  posted: true, aiConfidence: 96, account: 'Chase Checking ···4821', rawDescriptor: 'WHOLEFDS SF 10428' },
    { id: 'tx3', merchant: 'Sweetgreen',      amount: -18.40, cat: 'Dining',        catColor: 2, date: 'Today',  posted: false, aiConfidence: 64, account: 'Visa ···4821' },
    { id: 'tx4', merchant: 'Lyft',            amount: -18.50, cat: 'Transport',     catColor: 5, date: 'Yesterday', posted: true, aiConfidence: 100, account: 'Chase Checking ···4821' },
    { id: 'tx5', merchant: 'Apple One',       amount: -32.95, cat: 'Subscriptions', catColor: 4, date: 'Yesterday', posted: true, aiConfidence: 100, account: 'Visa ···4821' },
    { id: 'tx6', merchant: 'Employer Direct', amount: +4200,  cat: 'Income',        catColor: 1, date: 'May 1',  posted: true, aiConfidence: 100, account: 'Chase Checking ···4821' },
    { id: 'tx7', merchant: 'REI',             amount: -124.00,cat: 'Shopping',      catColor: 2, date: 'Apr 30', posted: true, aiConfidence: 88,  account: 'Visa ···4821' },
  ];

  return (
    <div style={{ display: 'flex', height: '100%', background: t.bgPrimary, fontFamily: "'Geist', sans-serif" }}>
      <Sidebar t={t} active="txn" />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '18px 28px 14px', borderBottom: `1px solid ${t.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div>
            <div style={{ fontSize: 11, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Transactions · split-expand pattern</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: t.fgPrimary, marginTop: 2 }}>Recent activity</div>
          </div>
          <div style={{ fontSize: 12, color: t.fgMuted }}>Click any row to expand inline ·{expandedTxId ? ' 1 expanded' : ' all collapsed'}</div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 28px 24px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.07em', padding: '14px 0 4px' }}>Today</div>
          <SplitExpandTxFeed
            t={t} privacy={privacy}
            transactions={txs.filter(tx => tx.date === 'Today')}
            expandedTxId={expandedTxId} onSelect={setExpandedTxId}
          />
          <div style={{ fontSize: 11, fontWeight: 600, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.07em', padding: '14px 0 4px' }}>Yesterday</div>
          <SplitExpandTxFeed
            t={t} privacy={privacy}
            transactions={txs.filter(tx => tx.date === 'Yesterday')}
            expandedTxId={expandedTxId} onSelect={setExpandedTxId}
          />
          <div style={{ fontSize: 11, fontWeight: 600, color: t.fgMuted, textTransform: 'uppercase', letterSpacing: '0.07em', padding: '14px 0 4px' }}>Earlier</div>
          <SplitExpandTxFeed
            t={t} privacy={privacy}
            transactions={txs.filter(tx => tx.date !== 'Today' && tx.date !== 'Yesterday')}
            expandedTxId={expandedTxId} onSelect={setExpandedTxId}
          />
        </div>
      </div>
    </div>
  );
}

// Expose to global scope so dashboard.html's main script can use them
Object.assign(window, {
  MonthlyRecapScreen,
  SubscriptionAuditScreen,
  TxDetailScreen,
  SplitExpandTxFeed,
  TxDetailExpansion,
  CardModal,
  WaterfallFlow,
});
