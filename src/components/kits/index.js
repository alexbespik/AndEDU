import { lazy } from 'react';
import '../../styles/kit_tools.css';

export { runKitTool } from './kitTool';

/** Kit id -> its Tools desk (one lazy chunk each). */
export const KIT_TOOLS = {
  polity: lazy(() => import('./PolityDesk')),
  music: lazy(() => import('./MusicDesk')),
  classics: lazy(() => import('./ClassicsDesk')),
  literature: lazy(() => import('./LiteratureDesk')),
  rhetoric: lazy(() => import('./RhetoricDesk')),
  art_history: lazy(() => import('./ArtHistoryDesk')),
};

// STEM kits: not workspaces. Their desks open from a lesson's Tools tab, the Lab "STEM tools" view and the IDE.
KIT_TOOLS.ee = lazy(() => import('./EeDesk'));
KIT_TOOLS.ai = lazy(() => import('./AiDesk'));
KIT_TOOLS.systems = lazy(() => import('./SystemsDesk'));
KIT_TOOLS.stats = lazy(() => import('./StatsDesk'));
KIT_TOOLS.bio = lazy(() => import('./BioDesk'));

export const STEM_KITS = ['ee', 'ai', 'systems', 'stats', 'bio'];
export const STEM_KIT_LABEL = {
  ee: 'Electrical engineering', ai: 'AI and machine learning', systems: 'Computer systems', stats: 'Statistics', bio: 'Bioinformatics',
};

// Same lists as mcp_tools_kits.KITS (the practice types of each STEM kit).
const STEM_TYPES = {
  ee: ['circuit_kcl_kvl', 'bode_plot_analyzer', 'boolean_gate_minimization', 'opamp_gain_calc'],
  ai: ['backprop_layer_step', 'attention_score_matrix', 'confusion_matrix_metrics', 'loss_gradient_verify'],
  systems: ['page_table_walk', 'cache_tag_index_offset', 'assembly_reg_trace', 'deadlock_bankers'],
  stats: ['hypothesis_test_two_sample', 'bayes_posterior_update', 'mle_parameter_derivation', 'markov_steady_state'],
  bio: ['smith_waterman_align', 'orf_finder_translate', 'restriction_digest_mapper', 'phylogenetic_upgma_step'],
};
const STEM_OF = Object.fromEntries(Object.entries(STEM_TYPES).flatMap(([k, ts]) => ts.map((t) => [t, k])));

/** The STEM kit a lesson belongs to (the kit with most practice items; ties go in the order of STEM_KITS), or null. */
export function stemKitOf(topic) {
  const counts = {};
  for (const item of topic?.practice || []) {
    const k = STEM_OF[item?.type];
    if (k) counts[k] = (counts[k] || 0) + 1;
  }
  let best = null;
  for (const k of STEM_KITS) if (counts[k] && (!best || counts[k] > counts[best])) best = k;
  return best;
}
