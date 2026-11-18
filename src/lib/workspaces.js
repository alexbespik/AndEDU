// Subject workspaces that open a course class inside their own lab (not Lab, Math or the IDE).
// Keep the two arrays below as plain literals: tests parse them and compare with server.WORKSPACES.
export const KIT_MODES = ['literature', 'music', 'art_history', 'classics', 'rhetoric', 'polity'];
export const SUBJECT_MODES = ['history', 'language', 'philosophy', 'psychology', 'literature', 'music', 'art_history', 'classics', 'rhetoric', 'polity'];

// Name and one-line description of each kit (navbar menu, KitWorkspace header)
export const KIT_META = {
  literature: { label: 'Literature', blurb: 'Read closely: meter, devices, themes and how a text is built.' },
  music: { label: 'Music', blurb: 'Train the ear and the eye: intervals, rhythm, chords and form.' },
  art_history: { label: 'Art history', blurb: 'Look carefully: period, composition, symbols and context.' },
  classics: { label: 'Classics', blurb: 'Read Greek and Latin: morphology, scansion and translation.' },
  rhetoric: { label: 'Rhetoric', blurb: 'Persuasion: appeals, tropes, stasis and structure of a speech.' },
  polity: { label: 'Polity', blurb: 'How institutions decide: voting, power and constitutions.' },
};
