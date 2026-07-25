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

export const metadata: Metadata = {
  title:
    "SafePlate — allergen verification that refuses when it cannot be sure",
  description:
    "A Gemma 4 agent that reads a food label, checks it against the EU-14 allergen table, searches the manufacturer's declaration, asks the kitchen about cross-contact, and refuses to clear a dish it cannot verify.",
  openGraph: {
    title: "SafePlate",
    description:
      "Allergen verification that refuses when it cannot be sure. Gemma 4 Hackathon Paris — Track 2, Autonomous Agents.",
    type: "website",
  },
};

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
