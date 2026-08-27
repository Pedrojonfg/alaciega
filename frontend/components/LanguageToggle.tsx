"use client";

import { useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { setLocale } from "../app/actions/set-locale";
import type { Locale } from "../lib/locale";

export function LanguageToggle() {
  const t = useTranslations("language");
  const locale = useLocale();
  const router = useRouter();
  const [, startTransition] = useTransition();

  function pick(next: Locale) {
    if (next === locale) return;
    startTransition(async () => {
      await setLocale(next);
      router.refresh();
    });
  }

  return (
    <details className="lang-toggle">
      <summary className="lang-toggle-btn" aria-label={t("label")}>
        🌐
      </summary>
      <ul className="lang-toggle-menu">
        <li>
          <button type="button" onClick={() => pick("en")}>
            {t("en")}
          </button>
        </li>
        <li>
          <button type="button" onClick={() => pick("es")}>
            {t("es")}
          </button>
        </li>
      </ul>
    </details>
  );
}
