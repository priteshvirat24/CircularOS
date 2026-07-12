import { LandingHero } from "@/components/marketing/LandingHero";
import { LandingProblem } from "@/components/marketing/LandingProblem";
import { LandingSolution } from "@/components/marketing/LandingSolution";
import { LandingCapabilities } from "@/components/marketing/LandingCapabilities";
import { LandingArchitecture } from "@/components/marketing/LandingArchitecture";
import { LandingTrust } from "@/components/marketing/LandingTrust";
import { MarketingHeader } from "@/components/marketing/MarketingHeader";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--background)] flex flex-col relative overflow-hidden">
      <MarketingHeader />
      <main className="flex-1 flex flex-col">
        <LandingHero />
        <LandingProblem />
        <LandingSolution />
        <LandingCapabilities />
        <LandingArchitecture />
        <LandingTrust />
      </main>
    </div>
  );
}
