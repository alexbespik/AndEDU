// Built-in offline script tables for the Alphabets tab (the only built-in language content; each table < 3 KB).
// Entries are "glyph=romanization" or "glyph=romanization=spoken", separated by spaces. The spoken form is what the
// voice reads when a bare letter would be read by its name (Hangul jamo are read with the vowel ㅏ or the silent ㅇ).

const TABLES = {
  hiragana: { label: 'Hiragana', lang: 'ja', data: 'あ=a い=i う=u え=e お=o か=ka き=ki く=ku け=ke こ=ko さ=sa し=shi す=su せ=se そ=so た=ta ち=chi つ=tsu て=te と=to な=na に=ni ぬ=nu ね=ne の=no は=ha ひ=hi ふ=fu へ=he ほ=ho ま=ma み=mi む=mu め=me も=mo や=ya ゆ=yu よ=yo ら=ra り=ri る=ru れ=re ろ=ro わ=wa を=wo ん=n' },
  katakana: { label: 'Katakana', lang: 'ja', data: 'ア=a イ=i ウ=u エ=e オ=o カ=ka キ=ki ク=ku ケ=ke コ=ko サ=sa シ=shi ス=su セ=se ソ=so タ=ta チ=chi ツ=tsu テ=te ト=to ナ=na ニ=ni ヌ=nu ネ=ne ノ=no ハ=ha ヒ=hi フ=fu ヘ=he ホ=ho マ=ma ミ=mi ム=mu メ=me モ=mo ヤ=ya ユ=yu ヨ=yo ラ=ra リ=ri ル=ru レ=re ロ=ro ワ=wa ヲ=wo ン=n' },
  cyrillic: { label: 'Cyrillic (Russian)', lang: 'ru', data: 'Аа=a Бб=b Вв=v Гг=g Дд=d Ее=ye Ёё=yo Жж=zh Зз=z Ии=i Йй=y Кк=k Лл=l Мм=m Нн=n Оо=o Пп=p Рр=r Сс=s Тт=t Уу=u Фф=f Хх=kh Цц=ts Чч=ch Шш=sh Щщ=shch Ъъ=ʺ Ыы=ɨ Ьь=ʹ Ээ=e Юю=yu Яя=ya' },
  hangul: { label: 'Hangul', lang: 'ko', data: 'ㄱ=g=가 ㄴ=n=나 ㄷ=d=다 ㄹ=r/l=라 ㅁ=m=마 ㅂ=b=바 ㅅ=s=사 ㅇ=ng=아 ㅈ=j=자 ㅊ=ch=차 ㅋ=k=카 ㅌ=t=타 ㅍ=p=파 ㅎ=h=하 ㅏ=a=아 ㅑ=ya=야 ㅓ=eo=어 ㅕ=yeo=여 ㅗ=o=오 ㅛ=yo=요 ㅜ=u=우 ㅠ=yu=유 ㅡ=eu=으 ㅣ=i=이' },
  greek: { label: 'Greek', lang: 'el', data: 'Αα=a Ββ=v Γγ=g Δδ=d Εε=e Ζζ=z Ηη=ē Θθ=th Ιι=i Κκ=k Λλ=l Μμ=m Νν=n Ξξ=x Οο=o Ππ=p Ρρ=r Σσ=s Ττ=t Υυ=y Φφ=f Χχ=ch Ψψ=ps Ωω=ō' },
  arabic: { label: 'Arabic', lang: 'ar', data: 'ا=ā ب=b ت=t ث=th ج=j ح=ḥ خ=kh د=d ذ=dh ر=r ز=z س=s ش=sh ص=ṣ ض=ḍ ط=ṭ ظ=ẓ ع=ʿ غ=gh ف=f ق=q ك=k ل=l م=m ن=n ه=h و=w ي=y' },
  devanagari: { label: 'Devanagari', lang: 'hi', data: 'अ=a आ=ā इ=i ई=ī उ=u ऊ=ū ऋ=ṛ ए=e ऐ=ai ओ=o औ=au क=ka ख=kha ग=ga घ=gha ङ=ṅa च=ca छ=cha ज=ja झ=jha ञ=ña ट=ṭa ठ=ṭha ड=ḍa ढ=ḍha ण=ṇa त=ta थ=tha द=da ध=dha न=na प=pa फ=pha ब=ba भ=bha म=ma य=ya र=ra ल=la व=va श=śa ष=ṣa स=sa ह=ha' },
};

export const SCRIPT_IDS = Object.keys(TABLES);

/** {id, label, lang, letters: [{glyph, roman, say}]} for one script, or null. */
export function scriptTable(id) {
  const t = TABLES[id];
  if (!t) return null;
  const letters = t.data.split(' ').map((e) => { const [glyph, roman, say] = e.split('='); return { glyph, roman, say: say || [...glyph][0] }; });  // "Аа" is read once
  return { id, label: t.label, lang: t.lang, letters };
}

/** A script_match item with `count` random letters whose romanizations are all different. */
export function scriptDrill(id, count = 6) {
  const t = scriptTable(id);
  const pool = [...t.letters];
  for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
  const seen = new Set();
  const picked = pool.filter((l) => !seen.has(l.roman) && seen.add(l.roman)).slice(0, count);
  return {
    id: `drill-${id}-${Date.now()}`, type: 'script_match', script: id, lang: t.lang, prompt: `Match each ${t.label} letter to its sound`,
    explanation: '', pairs: picked.map((l) => [l.glyph, l.roman]), say: Object.fromEntries(picked.map((l) => [l.glyph, l.say])),
  };
}
