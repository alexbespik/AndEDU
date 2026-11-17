// Practice types rendered outside PracticeDeck.jsx. Subject files export {TYPE: Body} maps whose bodies take
// {item, onResult(ok, given), retry}; add a subject by importing its maps here (ARCHITECTURE.md §3.1.1).
import { LANGUAGE_RENDER, LANGUAGE_LABEL } from './language';
import { HISTORY_RENDER, HISTORY_LABEL } from './history';
import { GENERAL_RENDER, GENERAL_LABEL } from './general';
import { LANGUAGE_EXTRA_RENDER, LANGUAGE_EXTRA_LABEL } from './language_extra';
import { PHILOSOPHY_RENDER, PHILOSOPHY_LABEL } from './philosophy';
import { LIBERAL_ARTS_RENDER, LIBERAL_ARTS_LABEL } from './liberal_arts';
import { STEM_KITS_RENDER, STEM_KITS_LABEL } from './stem_kits';

export const EXTRA_RENDER = { ...LANGUAGE_RENDER, ...HISTORY_RENDER, ...LANGUAGE_EXTRA_RENDER, ...GENERAL_RENDER, ...PHILOSOPHY_RENDER, ...LIBERAL_ARTS_RENDER, ...STEM_KITS_RENDER };
export const EXTRA_LABEL = { ...LANGUAGE_LABEL, ...HISTORY_LABEL, ...LANGUAGE_EXTRA_LABEL, ...GENERAL_LABEL, ...PHILOSOPHY_LABEL, ...LIBERAL_ARTS_LABEL, ...STEM_KITS_LABEL };
