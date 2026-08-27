import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { COOKIE_NAME, resolveLocale } from "../lib/locale";

export default getRequestConfig(async () => {
  const store = await cookies();
  const hdrs = await headers();
  const locale = resolveLocale(store.get(COOKIE_NAME)?.value, hdrs.get("accept-language"));
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
