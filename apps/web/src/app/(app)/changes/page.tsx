"use client";

import React from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { BellRing, GitCommit, ArrowRight, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function ChangesPage() {
  const diffs = [
    { 
      id: 'DIFF-881', 
      title: 'Amendment to Margin Requirements', 
      source: 'SEBI Circular', 
      date: '2 hours ago',
      impact: 'High',
      changes: [
        { type: 'added', text: 'New obligation: Intraday margin monitoring required every 15 minutes.' },
        { type: 'modified', text: 'Reporting deadline shifted from T+1 to T+0 (EOD).' }
      ]
    },
    { 
      id: 'DIFF-882', 
      title: 'Relaxation of KYC Norms for FPIs', 
      source: 'RBI Notification', 
      date: 'Yesterday',
      impact: 'Medium',
      changes: [
        { type: 'removed', text: 'Physical signature requirement waived for Category I FPIs.' },
        { type: 'modified', text: 'Digital verification validity extended to 3 years.' }
      ]
    }
  ];

  return (
    <div className="space-y-6 pb-12">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-[32px] font-semibold tracking-tight text-[var(--text-primary)]">Regulatory Changes</h1>
          <p className="text-[var(--text-secondary)] mt-1">AI-driven diffs of new regulations against your existing controls</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
        <Card className="bg-white border-[var(--border-default)] shadow-sm">
          <CardContent className="p-5 flex flex-col justify-center h-full">
            <div className="flex items-center space-x-2 text-[var(--primary)] mb-2">
              <BellRing size={18} />
              <span className="text-[14px] font-semibold">New Alerts</span>
            </div>
            <p className="text-[32px] font-bold text-[var(--text-primary)]">12</p>
          </CardContent>
        </Card>
        <Card className="bg-white border-[var(--border-default)] shadow-sm">
          <CardContent className="p-5 flex flex-col justify-center h-full">
            <div className="flex items-center space-x-2 text-[#D97706] mb-2">
              <AlertTriangle size={18} />
              <span className="text-[14px] font-semibold">Impactful Changes</span>
            </div>
            <p className="text-[32px] font-bold text-[var(--text-primary)]">4</p>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-[2px] before:bg-gradient-to-b before:from-transparent before:via-[var(--border-default)] before:to-transparent">
        {diffs.map((diff, idx) => (
          <div key={idx} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
            {/* Timeline dot */}
            <div className="flex items-center justify-center w-10 h-10 rounded-full border-4 border-[var(--background-secondary)] bg-white text-[var(--text-muted)] group-hover:text-[var(--primary)] group-hover:border-[var(--primary-light)] shadow-sm shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10 transition-all">
              <GitCommit size={18} />
            </div>
            
            {/* Content Card */}
            <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-5 rounded-2xl border border-[var(--border-subtle)] bg-white shadow-sm hover:border-[var(--primary)] hover:shadow-md transition-all">
              <div className="flex items-center justify-between mb-3">
                <span className={cn(
                  "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider",
                  diff.impact === 'High' ? 'bg-[#FEF2F2] text-[#DC2626]' : 'bg-[#FFFBEB] text-[#D97706]'
                )}>
                  {diff.impact} Impact
                </span>
                <span className="text-[12px] text-[var(--text-muted)] font-mono">{diff.date}</span>
              </div>
              <h3 className="font-semibold text-[16px] text-[var(--text-primary)] mb-1">{diff.title}</h3>
              <p className="text-[13px] text-[var(--text-secondary)] mb-4">{diff.source}</p>
              
              <div className="space-y-2 bg-[var(--surface-subtle)] rounded-xl p-4 border border-[var(--border-subtle)]">
                {diff.changes.map((change, cIdx) => (
                  <div key={cIdx} className="flex items-start space-x-3 text-[14px]">
                    <div className="mt-[2px] shrink-0">
                      {change.type === 'added' ? <span className="text-[#10B981] font-bold">+</span> :
                       change.type === 'removed' ? <span className="text-[#EF4444] font-bold">-</span> :
                       <span className="text-[#3B82F6] font-bold">~</span>}
                    </div>
                    <span className={cn(
                      "font-medium",
                      change.type === 'added' ? 'text-[#064E3B]' :
                      change.type === 'removed' ? 'text-[#7F1D1D] line-through opacity-70' :
                      'text-[#1E3A8A]'
                    )}>
                      {change.text}
                    </span>
                  </div>
                ))}
              </div>
              
              <div className="mt-5 pt-4 border-t border-[var(--border-subtle)] flex justify-end">
                <button className="flex items-center space-x-1 text-[13px] text-[var(--primary)] hover:text-[var(--primary-hover)] font-medium transition-colors">
                  <span>View Impact Analysis</span>
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
