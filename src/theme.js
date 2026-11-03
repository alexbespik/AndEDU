// ---------------------------------------------------------------------------
// &.edu theme bridge for inline styles (IDE, simulation chrome).
// Every value is a CSS custom property defined in src/styles/lab.css, so inline
// styles follow light/dark mode automatically. Canvas code can't read var(),
// so it uses canvasPalette(), which resolves the same tokens once per frame.
// ---------------------------------------------------------------------------
const v = (name) => `var(--${name})`;

export const theme = {
  // Surfaces
  bgApp: v('paper'),
  bgPanel: v('surface'),
  bgSidebar: v('sunk'),
  bgEditor: v('surface'),
  bgActivity: v('sunk'),
  bgHeader: v('sunk'),        // IDE panel headers: a neutral surface, readable in both themes
  bgCard: v('surface'),
  bgCardAlt: v('sunk'),
  bgCardHover: v('accent-tint'),
  bgHighlight: v('accent-tint'),
  bgInput: v('surface'),
  bgGlass: v('surface'),

  // Rules
  border: v('rule'),
  borderHover: v('rule-strong'),
  borderActive: v('accent'),
  borderContrast: v('rule-strong'),
  borderLight: v('rule'),
  borderGlow: v('accent-tint-2'),

  // Text
  textMain: v('ink'),
  textBright: v('ink'),
  textDim: v('ink-soft'),
  textMuted: v('muted'),
  textSubtle: v('muted'),
  textOnBrand: v('on-accent'),

  // Accents (names kept for existing components)
  accent: v('accent'),
  accentGreen: v('accent'),
  accentForestLight: v('accent'),
  accentEmerald: v('accent'),
  accentGreenGlow: v('accent-tint-2'),
  accentGreenBg: v('accent-tint'),
  accentGreenBorder: v('accent-tint-2'),

  accentGold: v('gold-text'),
  accentYellow: v('gold-text'),
  accentGoldFill: v('gold'),
  accentGoldGlow: v('gold-tint'),
  accentGoldBg: v('gold-tint'),
  accentGoldBorder: v('gold-rule'),

  accentPink: v('bad'),
  accentPinkBg: v('bad-tint'),
  accentBlue: v('info'),
  accentCyan: v('info'),
  accentCyanBg: v('info-tint'),
  accentOrange: v('rust'),
  accentOrangeBg: v('gold-tint'),
  accentPurple: v('plum'),
  accentPurpleBg: v('sunk'),

  success: v('ok'),
  successBg: v('ok-tint'),
  error: v('bad'),
  errorBg: v('bad-tint'),
  warning: v('gold-text'),
  info: v('info'),

  // Type & geometry
  fontDisplay: 'var(--font-display)',
  fontMono: 'var(--font-mono)',
  fontSans: 'var(--font-body)',
  radiusSm: '3px',
  radiusMd: '6px',
  radiusLg: '8px',
  radiusFull: '9999px',

  // Elevation: quiet, no glows
  shadowSm: v('shadow'),
  shadowMd: v('shadow'),
  shadowLg: v('shadow-raised'),
  shadowGlowGreen: 'none',
  shadowGlowGold: 'none',
};

const CANVAS_TOKENS = ['surface', 'sunk', 'rule', 'rule-strong', 'ink', 'ink-soft', 'muted', 'accent', 'gold', 'gold-text', 'bad', 'info', 'plum'];
let cache = { key: null, colors: null };

/** Resolved token colors for canvas drawing; cheap to call every frame. */
export function canvasPalette() {
  const root = document.documentElement;
  const key = `${root.dataset.theme || ''}|${window.matchMedia?.('(prefers-color-scheme: dark)').matches}`;
  if (cache.key !== key) {
    const cs = getComputedStyle(root);
    const colors = {};
    for (const t of CANVAS_TOKENS) colors[t] = cs.getPropertyValue(`--${t}`).trim() || '#808080';
    cache = { key, colors };
  }
  return cache.colors;
}
