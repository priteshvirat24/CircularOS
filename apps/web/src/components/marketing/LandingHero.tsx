"use client";

import React, { Suspense } from 'react';
import dynamic from 'next/dynamic';
import { Play, ArrowRight, ShieldCheck } from 'lucide-react';
import { useJudgeMode } from '../judge/JudgeModeProvider';

// Dynamically import the 3D component with SSR disabled
const RegulatoryCore3D = dynamic(() => import('./RegulatoryCore3D'), { 
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-[var(--surface-subtle)] rounded-3xl border border-[var(--border-subtle)]">
      <div className="animate-pulse text-[var(--text-muted)] text-[13px] tracking-wider uppercase font-semibold">
        Initializing Core...
      </div>
    </div>
  )
});

export function LandingHero() {
  const { startJudgeMode } = useJudgeMode();

  return (
    <section className="relative pt-[120px] pb-20 min-h-[900px] flex items-center overflow-hidden">
      <div className="max-w-[1440px] mx-auto px-6 lg:px-10 w-full grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
        
        {/* Left Content */}
        <div className="flex flex-col items-start z-10 max-w-2xl">
          <div className="flex items-center space-x-2 px-3 py-1 bg-[var(--primary-subtle)] border border-[var(--primary-light)] rounded-full mb-8 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-[var(--primary)] animate-pulse"></span>
            <span className="text-[11px] font-bold text-[var(--primary)] tracking-widest uppercase">
              Agentic Regulatory Intelligence
            </span>
          </div>

          <h1 className="text-[56px] leading-[1.05] font-semibold text-[var(--text-primary)] tracking-tight mb-8">
            A CIRCULAR CHANGES.<br />
            YOUR ENTIRE COMPLIANCE SYSTEM SHOULD KNOW.
          </h1>

          <p className="text-[18px] leading-relaxed text-[var(--text-secondary)] mb-10 max-w-xl">
            CircularOS converts regulatory documents into verified, clause-cited obligations, detects what changed, maps affected controls and evidence, and gives regulators a supervisory view of implementation.
          </p>

          <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-4 mb-12 w-full sm:w-auto">
            <button 
              onClick={startJudgeMode}
              className="w-full sm:w-auto flex items-center justify-center space-x-2 bg-gradient-to-r from-[var(--primary)] to-[var(--secondary-brand)] text-white px-8 py-4 rounded-xl font-semibold text-[15px] hover:shadow-lg hover:-translate-y-0.5 transition-all group"
            >
              <Play size={18} className="fill-white" />
              <span>RUN 20s JUDGE MODE</span>
            </button>
            <a 
              href="#how-it-works"
              className="w-full sm:w-auto flex items-center justify-center space-x-2 bg-white border border-[var(--border-strong)] text-[var(--text-primary)] px-8 py-4 rounded-xl font-semibold text-[15px] hover:border-[var(--primary)] hover:bg-[var(--surface-hover)] transition-all group shadow-sm"
            >
              <span>EXPLORE THE PLATFORM</span>
              <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform text-[var(--text-muted)] group-hover:text-[var(--primary)]" />
            </a>
          </div>

          <div className="flex items-center space-x-3 text-[13px] font-medium text-[var(--text-muted)] bg-[var(--surface-subtle)] px-4 py-3 rounded-lg border border-[var(--border-subtle)]">
            <ShieldCheck size={16} className="text-[var(--success)]" />
            <p>
              <span className="text-[var(--text-primary)]">AI proposes.</span> Validators verify. Humans approve. Every decision remains auditable.
            </p>
          </div>
        </div>

        {/* Right Content - 3D Core */}
        <div className="relative h-[600px] w-full z-0 lg:scale-110 xl:scale-125 origin-center">
          <RegulatoryCore3D />
          
          {/* Subtle background glow for the 3D core */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-[var(--primary)] opacity-[0.03] blur-[100px] rounded-full pointer-events-none -z-10"></div>
        </div>

      </div>
    </section>
  );
}
