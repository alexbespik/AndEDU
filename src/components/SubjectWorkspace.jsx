import React from 'react';
import HistoryLab from './HistoryLab';
import LanguageLab from './LanguageLab';

/** History and Languages workspaces: each subject has its own lab with the tools that subject needs. */
export default function SubjectWorkspace(props) {
  return props.kind === 'language' ? <LanguageLab {...props} /> : <HistoryLab {...props} />;
}
