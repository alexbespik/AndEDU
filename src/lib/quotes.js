// The offline quote bank (content/quotes/*.json). Loading screens show only these, never generated text;
// every quote is checked against its public-domain source by scripts/verify_quotes.py.
import { createContext, useContext } from 'react';

// every bank in content/quotes/ is picked up automatically (a new author is just a new file)
const BANKS = import.meta.glob('../../content/quotes/*.json', { eager: true, import: 'default' });

export const LOADING_QUOTES = Object.values(BANKS)
  .flatMap((bank) => bank.quotes)
  .filter((q) => !q.tags.includes('no-loading'));

export const quoteCite = (q) => `${q.author}, ${q.work} ${q.ref}${q.translator ? `, tr. ${q.translator}` : ''}`;

// whether loading screens show quotes: off until the profile's progress has loaded and in Focus mode
export const quotesEnabled = (progress) => Boolean(progress) && !progress.focusMode;

export const LoadingPrefs = createContext({ quotes: false });
export const useLoadingPrefs = () => useContext(LoadingPrefs);
