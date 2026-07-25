"use client";

import Image from "next/image";
import {
  ArrowRight, Check, ChevronDown, CirclePlay, Globe2, Leaf, MilkOff,
  ShieldCheck, Sparkles, Volume2, WheatOff,
} from "lucide-react";
import { useState } from "react";

const preferences = [
  { label: "Peanut-free", icon: WheatOff, color: "butter" },
  { label: "Vegetarian", icon: Leaf, color: "basil" },
  { label: "Mild spice", icon: Sparkles, color: "tomato" },
  { label: "No dairy", icon: MilkOff, color: "sky" },
];

const steps = [
  { eyebrow: "In your words", title: "Tell us what feels good.", copy: "Speak naturally. SafePlate understands your language, preferences, allergies, and the way you like your food." },
  { eyebrow: "On the menu", title: "See only what fits.", copy: "We translate every dish, check its ingredients, and surface options that match you—not an average diner." },
  { eyebrow: "With the kitchen", title: "Confirm before you order.", copy: "When a label is not enough, your companion asks the kitchen. If it cannot verify a dish, it never guesses." },
];

function Brand() {
  return <span className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>SafePlate</span>;
}

export function HomeLanding() {
  const [selected, setSelected] = useState(["Peanut-free"]);
  const toggle = (label: string) => setSelected((items) => items.includes(label) ? items.filter((item) => item !== label) : [...items, label]);

  return (
    <div id="top" className="landing">
      <header className="landing-header">
        <a href="#top" aria-label="SafePlate home"><Brand /></a>
        <nav className="desktop-nav" aria-label="Main navigation">
          <a href="#how">How it works</a><a href="#restaurants">For restaurants</a><a href="#safety">Safety</a>
        </nav>
        <div className="header-actions">
          <label className="language"><Globe2 size={17} /><span className="sr-only">Language</span>
            <select defaultValue="English" aria-label="Choose language">
              <option>English</option><option>日本語</option><option>Français</option><option>Español</option><option>العربية</option>
            </select><ChevronDown size={15} aria-hidden="true" />
          </label>
          <a className="header-cta" href="/order">Try SafePlate</a>
        </div>
      </header>

      <main>
        <section className="home-hero">
          <div className="hero-copy">
            <p className="kicker"><span />Your food companion, anywhere</p>
            <h1>Order like a local.<br /><em>Feel at home.</em></h1>
            <p className="hero-intro">Your companion translates the menu, remembers what you avoid, and checks with the kitchen before you order.</p>
            <div className="hero-actions">
              <a className="primary-action" href="/order">Find my plate <ArrowRight size={20} /></a>
              <a className="watch-action" href="#how"><CirclePlay size={21} /> Watch 45 sec</a>
            </div>
            <div className="preference-picker" aria-label="Food preferences">
              <p>Make it yours</p>
              <div className="preference-row">
                {preferences.map(({ label, icon: Icon, color }) => {
                  const active = selected.includes(label);
                  return <button type="button" key={label} className={`preference preference-${color} ${active ? "is-selected" : ""}`} aria-pressed={active} onClick={() => toggle(label)}>
                    <span>{active ? <Check size={15} /> : <Icon size={15} />}</span>{label}
                  </button>;
                })}
              </div>
            </div>
          </div>

          <div className="hero-visual">
            <Image src="/safeplate-friends-dining.png" alt="Three friends enjoying lunch together in a bright restaurant" fill priority sizes="(max-width: 900px) 100vw, 55vw" />
            <div className="conversation-card" aria-label="Live translation">
              <div className="message-line"><span className="avatar">R</span><div><small>You said</small><strong>No peanuts, please.</strong></div><Volume2 size={18} /></div>
              <div className="message-line translated"><span>한</span><div><small>Translated for the kitchen</small><strong>땅콩은 빼주세요.</strong></div><Volume2 size={18} /></div>
              <div className="confirmation"><span><Check size={20} strokeWidth={3} /></span><div><strong>Kitchen confirmed</strong><small>Safe to order</small></div></div>
            </div>
            <div className="photo-caption"><span>Lunch in Seoul</span><span>12:42 local time</span></div>
          </div>
        </section>

        <section id="safety" className="trust-strip" aria-label="SafePlate benefits">
          <div><Globe2 /><span><strong>100+ languages</strong><small>Speak the way you do</small></span></div>
          <div><ShieldCheck /><span><strong>14 major allergens</strong><small>Checked dish by dish</small></span></div>
          <div><Check /><span><strong>Never guesses</strong><small>Kitchen-confirmed answers</small></span></div>
        </section>

        <section id="how" className="how-section">
          <div className="section-heading">
            <p className="kicker"><span />One conversation, three safeguards</p>
            <h2>Good food. Zero guesswork.</h2>
            <p>SafePlate stays with your order from the first question to the first bite.</p>
          </div>
          <div className="steps">
            {steps.map((step, index) => <article key={step.title}>
              <div className="step-number">0{index + 1}</div><p>{step.eyebrow}</p><h3>{step.title}</h3><span>{step.copy}</span>
            </article>)}
          </div>
        </section>

        <section id="restaurants" className="restaurant-banner">
          <div><p>Built for welcoming restaurants</p><h2>One menu. A world of guests.</h2></div>
          <p>Give every guest a personal ordering companion—without replacing the human care that makes hospitality matter.</p>
          <a href="mailto:hello@safeplate.ai">Bring SafePlate to your tables <ArrowRight size={19} /></a>
        </section>
      </main>

      <footer className="landing-footer">
        <a href="#top"><Brand /></a><p>Food should feel familiar, wherever you are.</p><span>Prototype · Always confirm serious allergies with staff.</span>
      </footer>
    </div>
  );
}
