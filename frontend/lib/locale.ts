export const LOCALES = ["en", "es"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
export const COOKIE_NAME = "NEXT_LOCALE";

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value);
}

export function parseAcceptLanguage(header: string | null): Locale | null {
  if (!header) return null;
  const tags = header
    .split(",")
    .map((part) => {
      const [tag, ...params] = part.trim().split(";");
      const q = params.find((p) => p.trim().startsWith("q="));
      const quality = q ? Number(q.trim().slice(2)) : 1;
      const lang = tag.trim().toLowerCase().split("-")[0] ?? "";
      return { lang, quality: Number.isFinite(quality) ? quality : 0 };
    })
    .sort((a, b) => b.quality - a.quality);
  for (const { lang } of tags) {
    if (isLocale(lang)) return lang;
  }
  return null;
}

export function resolveLocale(cookie: string | undefined, acceptLanguage: string | null): Locale {
  if (cookie && isLocale(cookie)) return cookie;
  return parseAcceptLanguage(acceptLanguage) ?? DEFAULT_LOCALE;
}
