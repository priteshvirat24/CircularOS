"use client";

import React, { useState } from 'react';
import { FileText, Database, ShieldCheck, UserCheck, GitCommit, Search, LayoutGrid, CheckCircle, Cpu } from 'lucide-react';
import { cn } from '@/lib/utils';

export function LandingSolution() {
  const [activeStep, setActiveStep] = useState(0);

  const pipeline = [
    { name: 'OFFICIAL CIRCULAR', icon: <FileText size={20} />, description: 'Acquires raw regulatory text via official sources.', agent: 'Document Ingestion' },
    { name: 'DOCUMENT INTELLIGENCE', icon: <Search size={20} />, description: 'Parses structure, OCR, and extracts metadata.', agent: 'Document Classifier' },
    { name: 'CLAUSE GRAPH', icon: <Database size={20} />, description: 'Decomposes document into a hierarchical knowledge graph.', agent: 'Clause Analyst' },
    { name: 'AGENTIC EXTRACTION', icon: <CheckCircle size={20} />, description: 'Identifies actionable obligations and deadlines.', agent: 'Obligation Extractor' },
    { name: 'CRITIC + VALIDATION', icon: <ShieldCheck size={20} />, description: 'Verifies citations and tests for hallucination.', agent: 'Regulatory Critic' },
    { name: 'HUMAN APPROVAL', icon: <UserCheck size={20} />, description: 'Flags material changes for human-in-the-loop review.', agent: 'Compliance Officer' },
    { name: 'OBLIGATION REGISTRY', icon: <Database size={20} />, description: 'Persists structured, versioned regulatory duties.', agent: 'System' },
    { name: 'REGULATORY DIFF', icon: <GitCommit size={20} />, description: 'Calculates exact semantic changes from previous versions.', agent: 'Diff Engine' },
    { name: 'CONTROLS + EVIDENCE', icon: <LayoutGrid size={20} />, description: 'Maps obligations to internal policies and artifacts.', agent: 'Mapping Agent' },
    { name: 'SUPERVISORY INTELLIGENCE', icon: <Search size={20} />, description: 'Aggregates implementation metrics for Regulators.', agent: 'SupTech Engine' }
  ];

  return (
    <section id="how-it-works" className="bg-[var(--surface-subtle)] py-32 border-t border-[var(--border-subtle)]">
      <div className="max-w-[1440px] mx-auto px-6">
        <div className="text-center mb-20">
          <h2 className="text-[32px] md:text-[40px] font-semibold tracking-tight text-[var(--text-primary)] mb-2">
            ONE CIRCULAR IN.
          </h2>
          <h3 className="text-[32px] md:text-[40px] font-semibold tracking-tight text-[var(--primary)]">
            A VERIFIED COMPLIANCE SYSTEM OUT.
          </h3>
        </div>

        <div className="flex flex-col lg:flex-row items-start justify-between gap-16 max-w-6xl mx-auto">
          
          {/* Pipeline Interactive List */}
          <div className="w-full lg:w-1/2 space-y-2 relative before:absolute before:inset-0 before:left-[19px] before:w-[2px] before:bg-[var(--border-default)]">
            {pipeline.map((step, idx) => {
              const isActive = activeStep === idx;
              return (
                <div 
                  key={idx}
                  onMouseEnter={() => setActiveStep(idx)}
                  className={cn(
                    "relative flex items-center space-x-4 p-4 rounded-xl cursor-pointer transition-all duration-300",
                    isActive ? "bg-white border border-[var(--primary)] shadow-md" : "hover:bg-[var(--surface-hover)] border border-transparent"
                  )}
                >
                  <div className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center shrink-0 z-10 transition-colors",
                    isActive ? "bg-[var(--primary)] text-white" : "bg-white border border-[var(--border-strong)] text-[var(--text-muted)]"
                  )}>
                    {step.icon}
                  </div>
                  <div>
                    <h4 className={cn(
                      "text-[14px] font-bold tracking-widest uppercase transition-colors",
                      isActive ? "text-[var(--primary)]" : "text-[var(--text-secondary)]"
                    )}>
                      {step.name}
                    </h4>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Contextual Information Panel */}
          <div className="w-full lg:w-1/2 sticky top-32">
            <div className="bg-white border border-[var(--border-subtle)] rounded-2xl p-8 shadow-xl min-h-[400px] flex flex-col justify-center">
              <div className="w-12 h-12 bg-[var(--primary-subtle)] text-[var(--primary)] rounded-xl flex items-center justify-center mb-6 border border-[var(--primary-light)]">
                {pipeline[activeStep].icon}
              </div>
              <h4 className="text-[12px] font-bold text-[var(--primary)] tracking-widest uppercase mb-2">Stage {activeStep + 1}</h4>
              <h3 className="text-[28px] font-semibold text-[var(--text-primary)] tracking-tight mb-4">{pipeline[activeStep].name}</h3>
              <p className="text-[18px] text-[var(--text-secondary)] leading-relaxed mb-8">
                {pipeline[activeStep].description}
              </p>
              
              <div className="pt-6 border-t border-[var(--border-subtle)]">
                <p className="text-[12px] text-[var(--text-muted)] uppercase tracking-wider font-semibold mb-2">Actor</p>
                <div className="inline-flex items-center space-x-2 bg-[var(--surface-subtle)] border border-[var(--border-default)] px-3 py-1.5 rounded-lg text-[14px] font-medium text-[var(--text-primary)]">
                  <Cpu size={16} className="text-[var(--primary)]" />
                  <span>{pipeline[activeStep].agent}</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
