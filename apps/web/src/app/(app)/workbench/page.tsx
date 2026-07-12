"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Check, X, AlertTriangle, MessageSquare, Edit3 } from 'lucide-react';
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
          <h1 className="text-[32px] font-semibold tracking-tight text-[var(--text-primary)]">Review Workbench</h1>
          <p className="text-[var(--text-secondary)] mt-1">Human-in-the-loop review queue for AI extractions</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-right">
            <p className="text-sm text-[var(--text-secondary)]">Queue Status</p>
            <p className="text-[18px] font-semibold text-[var(--text-primary)]">2 Pending</p>
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
                  ? "bg-[var(--surface-selected)] border-[var(--primary)] shadow-sm" 
                  : "bg-white border-[var(--border-subtle)] hover:border-[var(--border-default)] hover:bg-[var(--surface-hover)]"
              )}
            >
              <div className="flex justify-between items-start mb-2">
                <span className="text-[12px] font-mono text-[var(--text-muted)]">{task.id}</span>
                <span className={cn(
                  "text-[10px] uppercase font-bold px-2 py-0.5 rounded",
                  task.urgency === 'Critical' ? 'bg-[#FEF2F2] text-[#DC2626]' : 'bg-[#FFF7ED] text-[#EA580C]'
                )}>
                  {task.urgency}
                </span>
              </div>
              <p className="text-[14px] font-medium text-[var(--text-primary)] line-clamp-2 mb-2">{task.docTitle}</p>
              <div className="flex items-center text-[12px] text-[var(--text-secondary)] space-x-1">
                <AlertTriangle size={14} className="text-[var(--warning)]" />
                <span className="truncate">{task.reason}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Task Detail Main Area */}
        <Card className="flex-1 flex flex-col shadow-sm border-[var(--border-default)]">
          <div className="p-5 border-b border-[var(--border-subtle)] bg-white flex justify-between items-center rounded-t-2xl">
            <div className="flex items-center space-x-3">
              <span className="px-2 py-1 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] rounded text-[12px] font-medium text-[var(--text-primary)]">
                {current.domain}
              </span>
              <h2 className="font-semibold text-[var(--text-primary)]">{current.docTitle}</h2>
            </div>
            <div className="text-[13px] font-mono text-[var(--text-muted)]">{current.id}</div>
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 space-y-8 bg-white">
            {/* AI Reasoning Flag */}
            <div className="p-4 bg-[#FFFBEB] border border-[#FDE68A] rounded-xl flex items-start space-x-3">
              <AlertTriangle className="text-[#D97706] shrink-0 mt-0.5 w-5 h-5" />
              <div>
                <h4 className="text-[14px] font-semibold text-[#D97706]">AI Review Flag</h4>
                <p className="text-[14px] text-[#92400E] mt-1">{current.reason}</p>
              </div>
            </div>

            {/* Split View: Source vs Extraction */}
            <div className="grid grid-cols-2 gap-8">
              {/* Source Text */}
              <div className="space-y-4">
                <h3 className="text-[12px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Source Clause</h3>
                <div className="p-5 bg-[var(--surface-subtle)] rounded-xl border border-[var(--border-subtle)] text-[15px] leading-relaxed text-[var(--text-primary)] font-serif">
                  {current.clauseText}
                </div>
              </div>

              {/* Extracted Data */}
              <div className="space-y-4">
                <h3 className="text-[12px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider flex items-center justify-between">
                  <span>Extracted Obligation</span>
                  <button className="text-[var(--primary)] hover:text-[var(--primary-hover)] flex items-center text-[13px] space-x-1 font-medium">
                    <Edit3 size={14} />
                    <span>Edit</span>
                  </button>
                </h3>
                <div className="space-y-3">
                  {Object.entries(current.extracted).map(([key, value]) => (
                    <div key={key} className="p-4 bg-white border border-[var(--border-default)] rounded-xl flex flex-col">
                      <span className="text-[11px] uppercase text-[var(--text-muted)] font-semibold mb-1">{key}</span>
                      <span className={cn(
                        "text-[14px]",
                        key === 'risk' && value === 'Critical' ? 'text-[var(--danger)] font-semibold' :
                        key === 'risk' && value === 'High' ? 'text-[#EA580C] font-semibold' :
                        'text-[var(--text-primary)] font-medium'
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
          <div className="p-5 border-t border-[var(--border-subtle)] bg-[var(--surface-subtle)] flex justify-between items-center rounded-b-2xl">
            <button className="flex items-center space-x-2 px-4 py-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--border-subtle)] rounded-lg transition-colors text-sm font-medium">
              <MessageSquare size={18} />
              <span>Add Comment</span>
            </button>
            <div className="flex items-center space-x-3">
              <button className="flex items-center space-x-2 px-5 py-2 bg-white text-[var(--danger)] border border-[#FECACA] hover:bg-[#FEF2F2] rounded-lg transition-colors text-sm font-medium shadow-sm">
                <X size={18} />
                <span>Reject</span>
              </button>
              <button className="flex items-center space-x-2 px-6 py-2 bg-[var(--success)] text-white hover:bg-[#059669] rounded-lg transition-colors text-sm font-medium shadow-sm">
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
