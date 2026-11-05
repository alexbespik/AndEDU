// Extra tabs for the Languages workspace. LanguageLab maps over this list: each tab is
// {id, label, icon (lucide component), render(topics)}, where topics are the language lessons.
import { createElement as h } from 'react';
import { BookOpenText, Languages, MessagesSquare, Lightbulb } from 'lucide-react';
import { StoriesTab, AlphabetsTab, DialoguesTab, GrammarTipsTab } from './LanguageExtraTabs';

export const EXTRA_LANGUAGE_TABS = [
  { id: 'stories', label: 'Stories', icon: BookOpenText, render: (topics) => h(StoriesTab, { topics }) },
  { id: 'alphabets', label: 'Alphabets', icon: Languages, render: () => h(AlphabetsTab) },
  { id: 'dialogues', label: 'Dialogues', icon: MessagesSquare, render: (topics) => h(DialoguesTab, { topics }) },
  { id: 'grammar', label: 'Grammar tips', icon: Lightbulb, render: (topics) => h(GrammarTipsTab, { topics }) },
];
