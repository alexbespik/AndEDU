// The offline quote bank (content/quotes/*.json). Loading screens show only these, never generated text;
// every quote is checked against its public-domain source by scripts/verify_quotes.py.
import { createContext, useContext } from 'react';
import stoic from '../../content/quotes/stoic.json';
import socrates from '../../content/quotes/socrates.json';

export const LOADING_QUOTES = [...stoic.quotes, ...socrates.quotes].filter((q) => !q.tags.includes('no-loading'));

export const quoteCite = (q) => `${q.author}, ${q.work} ${q.ref}, tr. ${q.translator}`;

// whether loading screens show quotes: off until the profile's progress has loaded and in Focus mode
export const quotesEnabled = (progress) => Boolean(progress) && !progress.focusMode;

export const LoadingPrefs = createContext({ quotes: false });
export const useLoadingPrefs = () => useContext(LoadingPrefs);
