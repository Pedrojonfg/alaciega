"use server";

import { cookies } from "next/headers";
import { COOKIE_NAME, isLocale } from "../../lib/locale";

export async function setLocale(locale: string) {
  if (!isLocale(locale)) return;
  const store = await cookies();
  store.set(COOKIE_NAME, locale, { path: "/", maxAge: 60 * 60 * 24 * 365 });
}
