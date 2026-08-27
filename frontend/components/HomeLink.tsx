"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

export function HomeLink() {
  const t = useTranslations("common");
  return (
    <Link href="/" className="home-link" aria-label={t("home")} title={t("home")}>
      ⌂
    </Link>
  );
}
