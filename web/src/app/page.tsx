import type { Metadata } from "next";
import { HomeLanding } from "@/components/home-landing";

export const metadata: Metadata = {
  title: "SafePlate — order like a local, feel at home",
  description:
    "A Gemma 4 agent that hears a diner in their own language, checks the dish against its real label, asks the kitchen what no label can answer, and refuses when it cannot be sure.",
};

export default function Home() {
  return <HomeLanding />;
}
