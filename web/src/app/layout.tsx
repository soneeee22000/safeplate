import type { Metadata } from "next";
import {
  Bricolage_Grotesque,
  IBM_Plex_Mono,
  Public_Sans,
} from "next/font/google";
import "./globals.css";

const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  display: "swap",
});

const publicSans = Public_Sans({
  variable: "--font-public-sans",
  subsets: ["latin"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const SITE_URL = "https://safeplate-ten.vercel.app";
const DEFAULT_TITLE = "SafePlate — the model hears, the code decides";
const DESCRIPTION =
  "SafePlate (hackathon project): an allergen agent on Gemma 4 E2B where the model only hears and speaks and deterministic code decides. It checks the dish and the EU-14 allergens, forces a SerpApi lookup and one question to the kitchen, then answers or refuses with a reason.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: DEFAULT_TITLE,
    template: "%s — SafePlate",
  },
  description: DESCRIPTION,
  openGraph: {
    title: DEFAULT_TITLE,
    description: DESCRIPTION,
    url: "/",
    siteName: "SafePlate",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: DEFAULT_TITLE,
    description: DESCRIPTION,
  },
};

/** Root layout: fonts, global styles, and site-wide metadata. */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${bricolage.variable} ${publicSans.variable} ${plexMono.variable} h-full`}
    >
      <body className="min-h-full antialiased">{children}</body>
    </html>
  );
}
