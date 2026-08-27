import type { ReactNode } from "react";
import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import "./globals.css";
import SwRegister from "./sw-register";
import { LanguageToggle } from "../components/LanguageToggle";

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
});

const ui = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ui",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-mono",
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("meta");
  return { title: t("title"), description: t("description") };
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  return (
    <html lang={locale}>
      <body className={`${display.variable} ${ui.variable} ${mono.variable}`}>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <SwRegister />
          <LanguageToggle />
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
