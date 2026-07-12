"use client";

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Check, X, AlertTriangle, MessageSquare, ChevronRight, Edit3 } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function WorkbenchPage() {
  const [activeTask, setActiveTask] = useState(0);

  const tasks = [
    {
      id: 'TASK-8429',
      docTitle: 'SEBI Guidelines on Anti-Money Laundering',
      domain: 'SEBI',
      urgency: 'High',
      reason: 'Complex nested condition detected in clause 4.2(b)',
      clauseText: 'Intermediaries shall ensure that records of all transactions are maintained and preserved for a period of five years from the date of transaction between the client and intermediary. However, in cases where the records relate to ongoing investigations, they must be retained until the investigation is concluded.',
      extracted: {
        actor: 'Intermediaries',
        action: 'maintain and preserve records of all transactions',
        object: 'transaction records',
        deadline: 'five years from date of transaction',
        exceptions: 'ongoing investigations require retention until conclusion',
        risk: 'High'
      }
    },
    {
      id: 'TASK-8430',
      docTitle: 'RBI Cyber Security Framework',
      domain: 'RBI',
      urgency: 'Critical',
      reason: 'Low confidence score (0.42) on Actor extraction',
      clauseText: 'The competent authority must report any cyber incident to CERT-In within 6 hours of noticing the incident.',
      extracted: {
        actor: 'competent authority',
        action: 'report cyber incident',
        object: 'CERT-In',
        deadline: 'within 6 hours of noticing',
        exceptions: 'None',
        risk: 'Critical'
      }
    }
  ];

  const current = tasks[activeTask];

  return (
    <div className="space-y-6 pb-12 h-[calc(100vh-4rem)] flex flex-col">
      <div className="flex justify-between items-end mb-4">
        <div>
          <h1 className="text-4xl font-bold font-outfit tracking-tight">Review Workbench</h1>
          <p className="text-slate-400 mt-2">Human-in-the-loop review queue for AI extractions</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-right">
            <p className="text-sm text-slate-400">Queue Status</p>
            <p className="text-lg font-bold text-slate-200">2 Pending</p>
          </div>
        </div>
      </div>

      <div className="flex flex-1 gap-6 min-h-0">
        {/* Task List Sidebar */}
        <div className="w-80 flex flex-col space-y-3 overflow-y-auto pr-2">
          {tasks.map((task, idx) => (
            <div 
              key={task.id}
              onClick={() => setActiveTask(idx)}
              className={cn(
                "p-4 rounded-xl border transition-all cursor-pointer",
                activeTask === idx 
                  ? "bg-slate-800/80 border-blue-500/50 shadow-lg shadow-blue-500/10" 
                  : "bg-slate-900/40 border-slate-800/50 hover:border-slate-700 hover:bg-slate-800/40"
              )}
            >
              <div className="flex justify-between items-start mb-2">
                <span className="text-xs font-mono text-slate-400">{task.id}</span>
                <span className={cn(
                  "text-[10px] uppercase font-bold px-2 py-0.5 rounded",
                  task.urgency === 'Critical' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'
                )}>
                  {task.urgency}
                </span>
              </div>
              <p className="text-sm font-medium text-slate-200 line-clamp-2 mb-2">{task.docTitle}</p>
              <div className="flex items-center text-xs text-slate-500 space-x-1">
                <AlertTriangle size={12} className="text-amber-400" />
                <span className="truncate">{task.reason}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Task Detail Main Area */}
        <Card className="flex-1 flex flex-col border-slate-800/60 shadow-2xl overflow-hidden">
          <div className="p-4 border-b border-slate-800/50 bg-slate-900/50 flex justify-between items-center">
            <div className="flex items-center space-x-3">
              <span className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs font-semibold text-slate-300">
                {current.domain}
              </span>
              <h2 className="font-semibold text-slate-200">{current.docTitle}</h2>
            </div>
            <div className="text-xs font-mono text-slate-500">{current.id}</div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* AI Reasoning Flag */}
            <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-start space-x-3">
              <AlertTriangle className="text-amber-400 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-semibold text-amber-400">AI Review Flag</h4>
                <p className="text-sm text-slate-300 mt-1">{current.reason}</p>
              </div>
            </div>

            {/* Split View: Source vs Extraction */}
            <div className="grid grid-cols-2 gap-6">
              {/* Source Text */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Source Clause</h3>
                <div className="p-4 bg-slate-950/50 rounded-lg border border-slate-800 text-sm leading-relaxed text-slate-300 font-serif">
                  {current.clauseText}
                </div>
              </div>

              {/* Extracted Data */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Extracted Obligation</span>
                  <button className="text-blue-400 hover:text-blue-300 flex items-center text-xs space-x-1">
                    <Edit3 size={14} />
                    <span>Edit</span>
                  </button>
                </h3>
                <div className="space-y-3">
                  {Object.entries(current.extracted).map(([key, value]) => (
                    <div key={key} className="p-3 bg-slate-800/30 border border-slate-700/50 rounded-lg flex flex-col">
                      <span className="text-[10px] uppercase text-slate-500 font-bold mb-1">{key}</span>
                      <span className={cn(
                        "text-sm",
                        key === 'risk' && value === 'Critical' ? 'text-red-400 font-bold' :
                        key === 'risk' && value === 'High' ? 'text-orange-400 font-bold' :
                        'text-slate-200'
                      )}>
                        {value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="p-4 border-t border-slate-800/50 bg-slate-900/80 flex justify-between items-center backdrop-blur-md">
            <button className="flex items-center space-x-2 px-4 py-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors">
              <MessageSquare size={18} />
              <span>Add Comment</span>
            </button>
            <div className="flex items-center space-x-3">
              <button className="flex items-center space-x-2 px-4 py-2 bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 rounded-lg transition-colors">
                <X size={18} />
                <span>Reject</span>
              </button>
              <button className="flex items-center space-x-2 px-6 py-2 bg-emerald-600 text-white shadow-lg shadow-emerald-500/20 hover:bg-emerald-500 rounded-lg transition-colors">
                <Check size={18} />
                <span>Approve Extraction</span>
              </button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
