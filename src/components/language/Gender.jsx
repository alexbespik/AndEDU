// German noun genders: der (blue), die (red), das (green), plural die (amber). The article is always shown as text
// too, so the colour is a memory aid, never the only signal.
import React, { useEffect, useRef } from 'react';
import { genderOf, GENDER_LABEL, GERMAN_NOUN as NOUN } from './util';
const base = (lang) => String(lang || '').toLowerCase().split(/[-_]/)[0];

/** A word with its article coloured by gender ("der" in blue + "Apfel"); plain text when it has no gender. */
export function ArticleWord({ text, lang, gender, back }) {
  const g = genderOf(text, lang, { gender, back });
  const m = g && NOUN.exec(String(text).trim());
  if (!m) return <span lang={lang || undefined}>{text}</span>;
  return (
    <span className="de-noun" data-gender={g} lang={lang || undefined} title={GENDER_LABEL[g]}>
      <span className="de-article">{m[1]}</span> {m[2]}
    </span>
  );
}

/**
 * Tags German nouns inside children (flashcards, match pairs) with data-gender, so lab.css can colour them.
 * Those components render plain text, so this watches their DOM instead of changing them.
 */
export function GenderTint({ lang, selector = '.flash-text, .match-item', children }) {
  const ref = useRef(null);
  useEffect(() => {
    const root = ref.current;
    if (!root || base(lang) !== 'de') return undefined;
    const tag = () => root.querySelectorAll(selector).forEach((el) => {
      const g = genderOf(el.textContent, 'de');
      if (g) el.setAttribute('data-gender', g); else el.removeAttribute('data-gender');
    });
    tag();
    const obs = new MutationObserver(tag);  // attributes are not observed, so tagging never re-triggers itself
    obs.observe(root, { childList: true, subtree: true, characterData: true });
    return () => obs.disconnect();
  }, [lang, selector]);
  return <div ref={ref} className="de-tint">{children}</div>;
}
