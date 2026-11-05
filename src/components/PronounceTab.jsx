import React, { useEffect, useState } from 'react';
import { Volume2, Mic } from 'lucide-react';
import { LANGUAGES, languageName, voicesFor, pickVoice, setPreferredVoice, speak, noVoiceHelp, canRecognize, recognize, RECOGNITION_NOTICE } from '../lib/speech';
import { similarity } from '../lib/langgrade';

const IPA = [['i', 'see'], ['ɪ', 'sit'], ['e', 'say (fr. été)'], ['ɛ', 'bed'], ['æ', 'cat'], ['ɑ', 'father'], ['ɔ', 'thought'], ['o', 'go (fr. eau)'],
  ['ʊ', 'put'], ['u', 'food'], ['ʌ', 'cup'], ['ə', 'about'], ['θ', 'think'], ['ð', 'this'], ['ʃ', 'she'], ['ʒ', 'vision'], ['ŋ', 'sing'],
  ['tʃ', 'church'], ['dʒ', 'judge'], ['ɲ', 'sp. año'], ['x', 'sp. jota'], ['ʁ', 'fr. rouge'], ['y', 'fr. tu'], ['ø', 'fr. peu'], ['ɦ', 'uk. голова'], ['ɨ', 'uk. син / ru. сын'], ['ʲ', 'soft sign: uk. день'], ['ʋ', 'uk. вода']];

const SAMPLES = { uk: 'Добрий день! Як справи?', es: '¿Dónde está la biblioteca?', fr: 'Où est la bibliothèque ?', de: 'Wo ist die Bibliothek?',
  it: "Dov'è la biblioteca?", pt: 'Onde fica a biblioteca?', pl: 'Gdzie jest biblioteka?', ru: 'Где библиотека?', zh: '图书馆在哪里？',
  ja: '図書館はどこですか？', ko: '도서관이 어디에 있어요?', ar: 'أين المكتبة؟', en: 'Where is the library?' };

function SayItBack({ text, lang }) {
  const [state, setState] = useState(null);  // null | 'listening' | {heard, score} | {error}
  if (!canRecognize()) return null;
  const go = async () => {
    const h = recognize(lang);
    if (!h) return;
    setState('listening');
    const r = await h.result;
    if (!r.ok) return setState({ error: r.reason === 'not-allowed' ? 'Microphone access was blocked.' : "I didn't catch that." });
    const heard = r.transcripts.reduce((b, t) => (similarity(t, text) > similarity(b, text) ? t : b), r.transcripts[0] || '');
    setState({ heard, score: similarity(heard, text) });
  };
  return (
    <div className="stack-sm">
      <div className="btn-row">
        <button type="button" className="btn btn-quiet" onClick={go} disabled={state === 'listening' || !text.trim()}><Mic size={15} /> {state === 'listening' ? 'Listening…' : 'Say it back'}</button>
        {state?.heard !== undefined && <span>I heard <em lang={lang}>{state.heard}</em>: <strong className="num">{Math.round(state.score * 100)}%</strong> match</span>}
        {state?.error && <span className="hint">{state.error}</span>}
      </div>
      <p className="hint">{RECOGNITION_NOTICE}</p>
    </div>
  );
}

export default function PronounceTab() {
  const [lang, setLang] = useState(() => { try { return localStorage.getItem('andedu_pron_lang') || 'uk'; } catch { return 'uk'; } });
  const [text, setText] = useState(SAMPLES[lang] || '');
  const [rate, setRate] = useState(0.9);
  const [voices, setVoices] = useState([]);
  const [voice, setVoice] = useState('');
  const [note, setNote] = useState(null);
  useEffect(() => {
    try { localStorage.setItem('andedu_pron_lang', lang); } catch { /* private mode */ }
    let live = true;
    voicesFor(lang).then((list) => { if (!live) return; setVoices(list); pickVoice(lang).then((v) => live && setVoice(v?.name || '')); });
    return () => { live = false; };
  }, [lang]);
  const changeLang = (l) => { setLang(l); setText(SAMPLES[l] || ''); setNote(null); };
  const say = async () => {
    const r = await speak(text, lang, { rate });
    setNote(r.ok ? null : r.reason === 'no-voice' ? noVoiceHelp(r.language) : 'This browser cannot read text aloud.');
  };
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      <div className="panel stack-sm">
        <h2>Hear it</h2>
        <div className="btn-row">
          <select className="input" style={{ width: 160 }} value={lang} onChange={(e) => changeLang(e.target.value)} aria-label="Language">
            {LANGUAGES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
          <input className="input" style={{ flex: '1 1 280px' }} value={text} onChange={(e) => setText(e.target.value)} aria-label="Text to pronounce" lang={lang} />
          <button type="button" className="btn btn-primary" onClick={say} disabled={!text.trim()}><Volume2 size={15} /> Listen</button>
        </div>
        <SayItBack text={text} lang={lang} />
        <div className="btn-row">
          <label className="field" style={{ minWidth: 240 }}>
            <span className="hint">Voice</span>
            {voices.length ? (
              <select className="input" value={voice} onChange={(e) => { setVoice(e.target.value); setPreferredVoice(lang, e.target.value); }}>
                {voices.map((v) => <option key={v.name} value={v.name}>{v.name} ({v.lang}){v.localService ? '' : ' · online'}</option>)}
              </select>
            ) : <span className="notice notice-bad">No {languageName(lang)} voice installed</span>}
          </label>
          <label className="slider" style={{ minWidth: 220 }}>
            <span className="hint">Speed {rate.toFixed(2)}×</span>
            <input type="range" min={0.5} max={1.3} step={0.05} value={rate} onChange={(e) => setRate(Number(e.target.value))} />
          </label>
        </div>
        {(note || !voices.length) && <p className="notice notice-info">{note || noVoiceHelp(languageName(lang))}</p>}
        <p className="hint">Uses the voices installed on your computer. "Enhanced" and "Premium" voices sound far more natural than the default ones.</p>
      </div>
      <div className="panel stack-sm">
        <h2>IPA quick reference</h2>
        <div className="ipa-grid">
          {IPA.map(([sym, ex]) => <div key={sym} className="ipa-cell"><span className="ipa-sym">{sym}</span><span className="hint">{ex}</span></div>)}
        </div>
      </div>
    </div>
  );
}

