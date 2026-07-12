"use client";

import React from 'react';
import { Shield, Target, UserCheck, BarChart4 } from 'lucide-react';

export function LandingTrust() {
  return (
    <section id="trust" className="bg-white py-32 border-t border-[var(--border-subtle)]">
      <div className="max-w-[1440px] mx-auto px-6">
        <div className="text-center mb-24">
          <h2 className="text-[32px] md:text-[40px] font-semibold tracking-tight text-[var(--text-primary)] mb-2">
            PROBABILISTIC MODELS.
          </h2>
          <h3 className="text-[32px] md:text-[40px] font-semibold tracking-tight text-[var(--primary)]">
            DETERMINISTIC GUARDRAILS.
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 max-w-5xl mx-auto mb-24">
          
          <div className="flex flex-col items-start p-8 rounded-2xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center text-[var(--primary)] border border-[var(--border-default)] shadow-sm mb-6">
              <Shield size={24} />
            </div>
            <h4 className="text-[20px] font-semibold text-[var(--text-primary)] tracking-tight mb-4">
              PROVENANCE FIRST
            </h4>
            <p className="text-[16px] text-[var(--text-secondary)] leading-relaxed">
              Every compliance assertion traces to its source. No claim is made without a direct semantic link to the exact clause, paragraph, and page of the official regulatory text.
            </p>
          </div>

          <div className="flex flex-col items-start p-8 rounded-2xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center text-[var(--primary)] border border-[var(--border-default)] shadow-sm mb-6">
              <Target size={24} />
            </div>
            <h4 className="text-[20px] font-semibold text-[var(--text-primary)] tracking-tight mb-4">
              VALIDATION BEFORE ACCEPTANCE
            </h4>
            <p className="text-[16px] text-[var(--text-secondary)] leading-relaxed">
              Extracted obligations pass citation, entailment, consistency, and critic checks before persisting. The architecture is designed for abstention in high-uncertainty scenarios.
            </p>
          </div>

          <div className="flex flex-col items-start p-8 rounded-2xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center text-[var(--primary)] border border-[var(--border-default)] shadow-sm mb-6">
              <UserCheck size={24} />
            </div>
            <h4 className="text-[20px] font-semibold text-[var(--text-primary)] tracking-tight mb-4">
              HUMAN CONTROL
            </h4>
            <p className="text-[16px] text-[var(--text-secondary)] leading-relaxed">
              Material regulatory changes require explicit review. The AI acts as a high-bandwidth analyst, but governance and operational sign-off remain firmly human.
            </p>
          </div>

          <div className="flex flex-col items-start p-8 rounded-2xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center text-[var(--primary)] border border-[var(--border-default)] shadow-sm mb-6">
              <BarChart4 size={24} />
            </div>
            <h4 className="text-[20px] font-semibold text-[var(--text-primary)] tracking-tight mb-4">
              MEASURED, NOT CLAIMED
            </h4>
            <p className="text-[16px] text-[var(--text-secondary)] leading-relaxed">
              Extraction, citation, retrieval, and regulatory-diff quality are evaluated against real gold datasets. Accuracy is a measured metric, not a marketing claim.
            </p>
          </div>

        </div>

        {/* Real Evaluation Results Metric */}
        <div className="max-w-3xl mx-auto bg-[#17151F] rounded-2xl p-8 border border-[#302B63] shadow-2xl relative overflow-hidden text-center">
          <div className="absolute inset-0 bg-gradient-to-br from-[var(--primary)]/20 to-transparent pointer-events-none"></div>
          <h4 className="text-[12px] font-bold text-white/60 tracking-widest uppercase mb-4 relative z-10">LATEST EVALUATION RUN</h4>
          <p className="text-[16px] text-white/80 font-mono relative z-10 mb-6">NO EVALUATION RUN AVAILABLE</p>
          <p className="text-[14px] text-white/50 relative z-10">System is awaiting first production RAGAS evaluation suite run.</p>
        </div>

      </div>
    </section>
  );
}
