import { Finding } from "@/components/landing/finding";
import { Hero } from "@/components/landing/hero";
import { Layers } from "@/components/landing/layers";
import { Numbers } from "@/components/landing/numbers";
import { ProductNote } from "@/components/landing/product-note";
import { Scene } from "@/components/landing/scene";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";

/** The landing page: one story, told in the order a visitor needs it. */
export default function Home() {
  return (
    <div id="top">
      <SiteHeader />
      <main>
        <Hero />
        <Scene />
        <Finding />
        <Layers />
        <Numbers />
        <ProductNote />
      </main>
      <SiteFooter />
    </div>
  );
}
