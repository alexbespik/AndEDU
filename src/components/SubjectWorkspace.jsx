import React from 'react';
import HistoryLab from './HistoryLab';
import LanguageLab from './LanguageLab';
import PhilosophyLab from './PhilosophyLab';
import PsychologyLab from './PsychologyLab';
import KitWorkspace from './KitWorkspace';
import { KIT_MODES } from '../lib/workspaces';

/** Subject workspaces: each has its own lab with the tools that subject needs (the six kits share KitWorkspace). */
export default function SubjectWorkspace(props) {
  if (props.kind === 'language') return <LanguageLab {...props} />;
  if (props.kind === 'philosophy') return <PhilosophyLab {...props} />;
  if (props.kind === 'psychology') return <PsychologyLab {...props} />;
  if (KIT_MODES.includes(props.kind)) return <KitWorkspace {...props} />;
  return <HistoryLab {...props} />;
}
