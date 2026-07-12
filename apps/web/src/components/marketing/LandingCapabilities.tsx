"use client";

import React from 'react';
import { Database, GitCommit, ShieldCheck, LayoutGrid, Calendar, Search, FileText, CheckCircle2, AlertCircle, FileBarChart } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

function CapabilityVisualizer({ index }: { index: number }) {
  switch (index) {
    case 0:
      return (
        <div className="w-full h-full p-8 flex items-center justify-between">
          <div className="flex-1 h-32 bg-white rounded-lg shadow-sm border border-[var(--border-subtle)] p-4 flex flex-col justify-center space-y-2 opacity-50">
             <div className="w-3/4 h-2 bg-gray-200 rounded"></div>
             <div className="w-full h-2 bg-gray-200 rounded"></div>
             <div className="w-5/6 h-2 bg-[var(--primary)]/30 rounded"></div>
          </div>
          <div className="w-16 h-px bg-[var(--primary-light)] relative">
             <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 bg-[var(--primary)] rounded-full"></div>
          </div>
          <div className="flex-1 h-32 bg-[var(--primary)]/5 border border-[var(--primary)]/30 rounded-lg shadow-sm p-4 flex flex-col justify-center items-center">
             <Database className="text-[var(--primary)] mb-2" size={24} />
             <div className="w-full h-2 bg-[var(--primary)]/40 rounded mt-2"></div>
          </div>
        </div>
      );
    case 1:
      return (
        <div className="w-full h-full p-8 flex flex-col justify-center space-y-4">
          <div className="w-full bg-[#FEF2F2] border border-[#FCA5A5] p-3 rounded flex items-center space-x-3">
             <div className="w-3 h-3 bg-[#DC2626] rounded-full shrink-0"></div>
             <div className="h-2 bg-[#DC2626]/40 rounded w-full line-through"></div>
          </div>
          <div className="w-full bg-[#F0FDF4] border border-[#86EFAC] p-3 rounded flex items-center space-x-3 shadow-sm">
             <div className="w-3 h-3 bg-[#16A34A] rounded-full shrink-0"></div>
             <div className="h-2 bg-[#16A34A]/60 rounded w-full"></div>
          </div>
        </div>
      );
    case 2:
      return (
        <div className="w-full h-full p-8 flex items-center justify-center relative">
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-full h-px bg-[var(--border-strong)] border-dashed border-t"></div>
          </div>
          <div className="flex justify-between w-full z-10 px-4">
             {[ShieldCheck, CheckCircle2, ShieldCheck, AlertCircle].map((Icon, i) => (
               <div key={i} className={cn("w-12 h-12 rounded-full flex items-center justify-center border-2 bg-white", i === 3 ? "border-[#F59E0B] text-[#F59E0B]" : "border-[var(--primary)] text-[var(--primary)] shadow-sm")}>
                 <Icon size={20} />
               </div>
             ))}
          </div>
        </div>
      );
    case 3:
      return (
        <div className="w-full h-full p-8 flex flex-col items-center justify-center">
          <div className="w-32 bg-[var(--primary)]/10 border border-[var(--primary)]/40 text-[var(--primary)] rounded px-4 py-2 text-[10px] font-bold text-center mb-4">OBLIGATION</div>
          <div className="w-px h-6 bg-[var(--border-strong)]"></div>
          <div className="w-64 h-px bg-[var(--border-strong)]"></div>
          <div className="flex justify-between w-64 pt-6">
             <div className="flex flex-col items-center">
               <div className="w-px h-6 bg-[var(--border-strong)] -mt-6"></div>
               <div className="w-24 bg-white border border-[var(--border-default)] rounded px-2 py-2 text-[10px] text-center font-medium shadow-sm mb-4">CONTROL A</div>
               <div className="w-px h-4 bg-[var(--border-subtle)]"></div>
               <div className="w-20 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] rounded px-2 py-1 text-[9px] text-center text-[var(--text-muted)]">Evidence 1</div>
             </div>
             <div className="flex flex-col items-center">
               <div className="w-px h-6 bg-[var(--border-strong)] -mt-6"></div>
               <div className="w-24 bg-white border border-[var(--border-default)] rounded px-2 py-2 text-[10px] text-center font-medium shadow-sm mb-4">CONTROL B</div>
               <div className="w-px h-4 bg-[var(--border-subtle)]"></div>
               <div className="w-20 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] rounded px-2 py-1 text-[9px] text-center text-[var(--text-muted)]">Evidence 2</div>
             </div>
          </div>
        </div>
      );
    case 4:
      return (
        <div className="w-full h-full p-8 flex flex-col justify-center">
          <div className="w-full bg-white rounded-lg shadow-sm border border-[var(--border-default)] overflow-hidden">
             <div className="bg-[var(--surface-subtle)] border-b border-[var(--border-subtle)] p-2 flex items-center space-x-2">
               <Calendar size={14} className="text-[var(--text-muted)]" />
               <span className="text-[10px] font-bold tracking-widest text-[var(--text-secondary)]">COMPLIANCE CALENDAR</span>
             </div>
             <div className="p-4 space-y-3">
               <div className="flex items-center space-x-3">
                 <div className="w-8 h-8 rounded bg-[#FEF2F2] flex items-center justify-center text-[#DC2626] font-bold text-[10px]">T-2</div>
                 <div className="flex-1 h-3 bg-gray-100 rounded"></div>
               </div>
               <div className="flex items-center space-x-3">
                 <div className="w-8 h-8 rounded bg-[#FFFBEB] flex items-center justify-center text-[#D97706] font-bold text-[10px]">T-7</div>
                 <div className="flex-1 h-3 bg-gray-100 rounded"></div>
               </div>
             </div>
          </div>
        </div>
      );
    case 5:
      return (
        <div className="w-full h-full p-8 flex items-end space-x-2 justify-center">
           {[40, 70, 30, 90, 60, 100, 50].map((h, i) => (
             <div key={i} className="flex-1 flex flex-col items-center group">
               <div className={cn("w-full rounded-t", h > 80 ? "bg-[var(--primary)]" : "bg-[var(--primary-light)]")} style={{ height: `${h}px` }}></div>
             </div>
           ))}
        </div>
      );
    default:
      return null;
  }
}


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
                <div className="absolute inset-0 bg-gradient-to-br from-transparent to-[var(--surface-subtle)] group-hover:opacity-50 transition-opacity z-0"></div>
                <div className="relative z-10 w-full h-full">
                  <CapabilityVisualizer index={idx} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
