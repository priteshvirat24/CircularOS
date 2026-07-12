"use client";

import React from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { BellRing, GitCommit, ArrowRight, TrendingUp, AlertTriangle } from 'lucide-react';
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
          <h1 className="text-4xl font-bold font-outfit tracking-tight">Regulatory Changes</h1>
          <p className="text-slate-400 mt-2">AI-driven diffs of new regulations against your existing controls</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
        <Card className="bg-gradient-to-br from-blue-900/40 to-slate-900/40 border-blue-800/50">
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <div className="flex items-center space-x-2 text-blue-400 mb-2">
              <BellRing size={16} />
              <span className="text-sm font-medium">New Alerts</span>
            </div>
            <p className="text-3xl font-bold font-outfit text-slate-100">12</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-amber-900/40 to-slate-900/40 border-amber-800/50">
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <div className="flex items-center space-x-2 text-amber-400 mb-2">
              <AlertTriangle size={16} />
              <span className="text-sm font-medium">Impactful Changes</span>
            </div>
            <p className="text-3xl font-bold font-outfit text-slate-100">4</p>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-700 before:to-transparent">
        {diffs.map((diff, idx) => (
          <div key={idx} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
            {/* Timeline dot */}
            <div className="flex items-center justify-center w-10 h-10 rounded-full border-4 border-[#0b0f19] bg-slate-800 text-slate-400 group-hover:text-blue-400 group-hover:bg-slate-700 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10 transition-colors">
              <GitCommit size={18} />
            </div>
            
            {/* Content Card */}
            <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-xl border border-slate-800/60 bg-slate-900/50 shadow-xl backdrop-blur-sm group-hover:border-blue-500/30 transition-all">
              <div className="flex items-center justify-between mb-3">
                <span className={cn(
                  "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                  diff.impact === 'High' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'
                )}>
                  {diff.impact} Impact
                </span>
                <span className="text-xs text-slate-500 font-mono">{diff.date}</span>
              </div>
              <h3 className="font-bold text-lg text-slate-200 mb-1">{diff.title}</h3>
              <p className="text-sm text-slate-400 mb-4">{diff.source}</p>
              
              <div className="space-y-2 bg-slate-950/50 rounded-lg p-3 border border-slate-800">
                {diff.changes.map((change, cIdx) => (
                  <div key={cIdx} className="flex items-start space-x-2 text-sm">
                    <div className="mt-0.5 shrink-0">
                      {change.type === 'added' ? <span className="text-emerald-400 font-bold">+</span> :
                       change.type === 'removed' ? <span className="text-red-400 font-bold">-</span> :
                       <span className="text-blue-400 font-bold">~</span>}
                    </div>
                    <span className={cn(
                      change.type === 'added' ? 'text-emerald-200/80' :
                      change.type === 'removed' ? 'text-red-200/80 line-through' :
                      'text-blue-200/80'
                    )}>
                      {change.text}
                    </span>
                  </div>
                ))}
              </div>
              
              <div className="mt-4 pt-4 border-t border-slate-800/50 flex justify-end">
                <button className="flex items-center space-x-1 text-xs text-blue-400 hover:text-blue-300 font-medium transition-colors">
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
