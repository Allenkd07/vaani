/** Primary ISO 639 subtag of a BCP-47 code: "hi-IN" -> "hi". */
export const primaryLanguage = (code: string) => code.split(/[-_]/)[0].toLowerCase();

const displayNames = new Intl.DisplayNames(undefined, { type: "language" });

export function languageName(code: string): string {
  try {
    return displayNames.of(code) ?? code;
  } catch {
    return code;
  }
}

export const formatLanguages = (languages: string | null) =>
  languages ? languages.split(",").map(languageName).join(", ") : "";

/** Appends a language (as its primary subtag) to an ordered, de-duplicated list. */
export function addLanguage(languages: string[], code: string | null | undefined): string[] {
  if (!code) return languages;
  const language = primaryLanguage(code);
  return languages.includes(language) ? languages : [...languages, language];
}

// Fallback when the provider reports no language: a script suggests its most common language.
// Scripts shared by several languages (Devanagari, Latin, Arabic, Cyrillic) can only give a best guess.
const SCRIPTS: [RegExp, string][] = [
  [/[ऀ-ॿ]/, "hi"],
  [/[ঀ-৿]/, "bn"],
  [/[਀-੿]/, "pa"],
  [/[઀-૿]/, "gu"],
  [/[଀-୿]/, "or"],
  [/[஀-௿]/, "ta"],
  [/[ఀ-౿]/, "te"],
  [/[ಀ-೿]/, "kn"],
  [/[ഀ-ൿ]/, "ml"],
  [/[؀-ۿ]/, "ar"],
  [/[֐-׿]/, "he"],
  [/[Ѐ-ӿ]/, "ru"],
  [/[Ͱ-Ͽ]/, "el"],
  [/[฀-๿]/, "th"],
  [/[가-힯]/, "ko"],
  [/[぀-ヿ]/, "ja"],
  [/[一-鿿]/, "zh"],
  [/[A-Za-z]/, "en"],
];

/** Languages guessed from the scripts in the text, in order of first appearance. */
export function detectScriptLanguages(text: string): string[] {
  return SCRIPTS.map(([pattern, language]) => ({ language, index: text.search(pattern) }))
    .filter(({ index }) => index >= 0)
    .sort((a, b) => a.index - b.index)
    .map(({ language }) => language);
}

const MAX_STORED_LANGUAGES = 12; // keeps the stored list within the 50-character column

export function toStoredLanguages(languages: string[]): string | null {
  return languages.length ? languages.slice(0, MAX_STORED_LANGUAGES).join(",") : null;
}

export function formatDuration(totalSec: number | null): string {
  if (totalSec == null) return "—";
  const minutes = Math.floor(totalSec / 60);
  const seconds = totalSec % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
