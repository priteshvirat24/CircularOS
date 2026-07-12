"use client";

import React from 'react';
import { Database, GitCommit, ShieldCheck, LayoutGrid, Calendar, Search } from 'lucide-react';
import { cn } from '@/lib/utils';

export function LandingCapabilities() {
  const capabilities = [
    {
      title: "MACHINE-ACTIONABLE REGULATION",
      description: "CircularOS converts regulatory prose into versioned, structured, source-backed obligations.",
      icon: <Database size={24} />,
      visual: "Document → Clause → Obligation"
    },
    {
      title: "REGULATORY DIFF",
      description: "Detect created, modified, removed, superseded, deadline-changed, applicability-changed, and evidence-changed obligations.",
      icon: <GitCommit size={24} />,
      visual: "Old regulation vs new amendment"
    },
    {
      title: "AGENTIC VERIFICATION",
      description: "The system is designed around verification and abstention, not blind generation.",
      icon: <ShieldCheck size={24} />,
      visual: "Extractor → Citation Verifier → Entailment Validator → Critic → Human Review"
    },
    {
      title: "EVIDENCE LINEAGE",
      description: "Every compliance state can be traced to the regulatory source and implementation evidence.",
      icon: <LayoutGrid size={24} />,
      visual: "Obligation → Control → Evidence"
    },
    {
      title: "COMPLIANCE OPERATIONS",
      description: "Regulatory change becomes operational work.",
      icon: <Calendar size={24} />,
      visual: "Changed obligation → owner → task → deadline → calendar"
    },
    {
      title: "SUPTECH MIRROR",
      description: "The same machine-actionable regulatory model enables supervisory visibility.",
      icon: <Search size={24} />,
      visual: "Intermediaries → coverage → gaps → systemic patterns"
    }
  ];

  return (
    <section className="bg-white py-32">
      <div className="max-w-[1440px] mx-auto px-6">
        <div className="space-y-32">
          {capabilities.map((cap, idx) => (
            <div key={idx} className={cn(
              "flex flex-col md:flex-row items-center gap-16",
              idx % 2 !== 0 ? "md:flex-row-reverse" : ""
            )}>
              <div className="w-full md:w-1/2">
                <div className="w-12 h-12 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] rounded-xl flex items-center justify-center text-[var(--primary)] mb-6 shadow-sm">
                  {cap.icon}
                </div>
                <h3 className="text-[28px] font-semibold tracking-tight text-[var(--text-primary)] mb-4">{cap.title}</h3>
                <p className="text-[18px] leading-relaxed text-[var(--text-secondary)] mb-8">{cap.description}</p>
                <div className="bg-[var(--surface-subtle)] border border-[var(--border-subtle)] px-4 py-3 rounded-lg inline-block">
                  <p className="font-mono text-[13px] font-semibold text-[var(--text-muted)] tracking-wider uppercase">
                    {cap.visual}
                  </p>
                </div>
              </div>
              <div className="w-full md:w-1/2 aspect-video bg-[var(--background-secondary)] border border-[var(--border-default)] rounded-2xl flex items-center justify-center shadow-inner relative overflow-hidden group">
                <div className="absolute inset-0 bg-gradient-to-br from-transparent to-[var(--surface-subtle)] group-hover:opacity-50 transition-opacity"></div>
                <p className="text-[var(--text-muted)] font-mono text-[12px] uppercase tracking-widest relative z-10">[ Visualization Placeholder ]</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
