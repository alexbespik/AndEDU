import React, { useEffect, useState } from 'react';
import { BookOpen, GraduationCap, ListChecks } from 'lucide-react';
import { CoursesTab } from './MathLab';
import WorkspaceShell from './WorkspaceShell';
import { KIT_META } from '../lib/workspaces';
import { EXTRA_LABEL } from '../practice/registry';

// Practice types each kit's normalizer module produces (practice_<kit>.py); the label comes from the registry
const KIT_TYPES = {
  literature: ['scansion', 'volta_spot', 'rhyme_scheme_audit', 'chronology_unravel'],
  music: ['lint_satb_progression', 'roman_numeral_analysis', 'ear_interval_id', 'figured_bass_realize'],
  art_history: ['composition_vector', 'label_architecture', 'iconography_decode', 'stylistic_taxonomy'],
  classics: ['epigraphy_transcribe', 'harris_matrix_build', 'cursus_honorum_order', 'athenian_sortition_sim'],
  rhetoric: ['stasis_classify', 'trope_hunter', 'dispositio_sort', 'enthymeme_excavator'],
  polity: ['compute_dhondt', 'compute_shapley_shubik_pivotal', 'veto_pipeline', 'instant_runoff_tally'],
};
const humanize = (t) => t.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

/**
 * Shared workspace of the six liberal-arts kits (literature, music, art history, classics, rhetoric, polity).
 * A class opens through renderClass (the lesson viewer), so its practice items reach the server grader with their topic id.
 */
export default function KitWorkspace({ kind, classTopic, topics = [], onOpenTopic, renderClass }) {
  const meta = KIT_META[kind] || { label: kind, blurb: '' };
  const [tab, setTab] = useState(classTopic ? 'class' : 'courses');
  useEffect(() => { if (classTopic) setTab('class'); }, [classTopic?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const tabs = [
    ...(classTopic ? [{ id: 'class', label: `Class ${classTopic.source?.classSeq ?? ''}`.trim(), icon: BookOpen }] : []),
    { id: 'courses', label: 'Courses', icon: GraduationCap },
    { id: 'practice', label: 'Practice types', icon: ListChecks },
  ];
  const current = tabs.some((t) => t.id === tab) ? tab : 'courses';
  return (
    <WorkspaceShell kind={meta.label} title={meta.label} tabs={tabs} current={current} onTab={setTab} intro={meta.blurb}>
      {current === 'class' && classTopic && renderClass(classTopic)}
      {current === 'courses' && (
        <CoursesTab topics={topics} onOpenTopic={onOpenTopic} activeId={classTopic?.id}
          empty={`No ${meta.label.toLowerCase()} courses yet. Start one from My courses: its classes open here.`} />
      )}
      {current === 'practice' && (
        <div className="panel stack-sm" style={{ marginTop: 'var(--space-4)' }}>
          <h2>Practice in {meta.label}</h2>
          <p className="hint">These exercises appear in the Practice tab of a {meta.label.toLowerCase()} class.</p>
          <ul>
            {(KIT_TYPES[kind] || []).map((t) => <li key={t}>{EXTRA_LABEL[t] || humanize(t)}</li>)}
          </ul>
        </div>
      )}
    </WorkspaceShell>
  );
}
