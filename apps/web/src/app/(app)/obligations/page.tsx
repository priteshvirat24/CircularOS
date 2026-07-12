"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { 
  Search, Filter, AlertCircle, ArrowUpRight, 
  MoreHorizontal, ChevronDown, CheckCircle2,
  X, ExternalLink, Calendar, FileText, Database
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useJudgeMode } from '@/components/judge/JudgeModeProvider';

export default function ObligationsPage() {
  const { startJudgeMode } = useJudgeMode();
  const [selectedRow, setSelectedRow] = useState<string | null>(null);

  const obligations = [
    { id: 'OBL-9182', actor: 'Depository Participant', action: 'Submit concurrent audit report', object: 'Audit Report', deadline: 'Quarterly', risk: 'High', status: 'Active', source: 'SEBI/HO/MIRSD', evidence: 'Mapped', review: 'Approved', updated: '2h ago' },
    { id: 'OBL-9183', actor: 'Stock Broker', action: 'Maintain client funds segregation', object: 'Client Funds', deadline: 'Daily', risk: 'Critical', status: 'Active', source: 'SEBI/HO/MIRSD', evidence: 'Gap', review: 'Pending', updated: '1d ago' },
    { id: 'OBL-9184', actor: 'Listed Entity', action: 'Disclose material events', object: 'Stock Exchanges', deadline: 'Within 24 hours', risk: 'Critical', status: 'Active', source: 'LODR Reg 30', evidence: 'Mapped', review: 'Approved', updated: '1d ago' },
    { id: 'OBL-9185', actor: 'Clearing Member', action: 'Report margin shortfalls', object: 'Clearing Corporation', deadline: 'T+1 day', risk: 'Medium', status: 'Active', source: 'NSE/CMPT/2026', evidence: 'Gap', review: 'Approved', updated: '3d ago' },
  ];

  return (
    <div className="flex h-[calc(100vh-140px)]">
      {/* Main Content Area */}
      <div className={cn(
        "flex flex-col transition-all duration-300",
        selectedRow ? "w-2/3 pr-6" : "w-full"
      )}>
        
        {/* Page Header */}
        <div className="flex justify-between items-end mb-6 shrink-0">
          <div>
            <p className="text-[11px] font-bold tracking-widest text-[var(--text-muted)] uppercase mb-1">
              REGULATORY INTELLIGENCE / OBLIGATIONS
            </p>
            <h1 className="text-[32px] font-semibold tracking-tight text-[var(--text-primary)]">Obligation Registry</h1>
            <p className="text-[var(--text-secondary)] mt-1">Versioned, source-backed regulatory obligations extracted from approved regulatory documents.</p>
          </div>
          <button 
            onClick={startJudgeMode}
            className="flex items-center space-x-2 bg-[var(--surface-subtle)] border border-[var(--border-strong)] text-[var(--text-primary)] px-4 py-2 rounded-lg hover:border-[var(--primary)] hover:text-[var(--primary)] transition-all font-medium text-[13px] shadow-sm"
          >
            <span>Run Judge Mode</span>
          </button>
        </div>

        {/* Compact Intelligence Strip */}
        <div className="flex items-center space-x-4 mb-6 shrink-0">
          {[
            { label: 'Active Obligations', value: '14,204' },
            { label: 'Pending Review', value: '12', alert: true },
            { label: 'High-Risk Gaps', value: '4', alert: true },
            { label: 'Evidence Gaps', value: '38' },
            { label: 'Recently Changed', value: '145' },
          ].map((metric, i) => (
            <div key={i} className="flex-1 bg-white border border-[var(--border-subtle)] rounded-lg p-3 shadow-sm flex items-center justify-between">
              <span className="text-[12px] font-medium text-[var(--text-secondary)]">{metric.label}</span>
              <span className={cn(
                "text-[16px] font-bold font-mono",
                metric.alert ? "text-[#EF4444]" : "text-[var(--text-primary)]"
              )}>{metric.value}</span>
            </div>
          ))}
        </div>

        <Card className="flex-1 flex flex-col shadow-sm min-h-0">
          
          {/* Integrated Filter Toolbar */}
          <div className="p-3 border-b border-[var(--border-subtle)] bg-white rounded-t-2xl flex items-center space-x-3 shrink-0 overflow-x-auto">
            <div className="relative w-64 shrink-0">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] w-4 h-4" />
              <input 
                type="text" 
                placeholder="Search obligations..." 
                className="w-full bg-[var(--surface-subtle)] border border-[var(--border-default)] rounded-md pl-9 pr-3 py-1.5 text-[13px] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--primary)] transition-all"
              />
            </div>
            
            <FilterSelect label="Actor" />
            <FilterSelect label="Entity Type" />
            <FilterSelect label="Risk" />
            <FilterSelect label="Evidence" />
            <FilterSelect label="Review State" />
            
            <button className="flex items-center space-x-1 px-3 py-1.5 text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--primary)] transition-colors shrink-0">
              <Filter size={14} />
              <span>More Filters</span>
            </button>
          </div>

          {/* High-Density Table */}
          <div className="flex-1 overflow-auto bg-white rounded-b-2xl">
            <table className="w-full text-left border-collapse whitespace-nowrap">
              <thead className="sticky top-0 bg-[var(--surface-subtle)] z-10">
                <tr className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] border-b border-[var(--border-default)]">
                  <th className="px-4 py-3 font-semibold">Obligation & Source</th>
                  <th className="px-4 py-3 font-semibold">Actor & Action</th>
                  <th className="px-4 py-3 font-semibold">Deadline</th>
                  <th className="px-4 py-3 font-semibold">Risk</th>
                  <th className="px-4 py-3 font-semibold">Evidence</th>
                  <th className="px-4 py-3 font-semibold">Review</th>
                  <th className="px-4 py-3 font-semibold">Updated</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)] text-[13px]">
                {obligations.map((obl, i) => (
                  <tr 
                    key={obl.id} 
                    onClick={() => setSelectedRow(obl.id)}
                    className={cn(
                      "transition-colors group cursor-pointer border-l-2",
                      selectedRow === obl.id 
                        ? "bg-[var(--surface-selected)] border-[var(--primary)]" 
                        : "hover:bg-[var(--surface-hover)] border-transparent"
                    )}
                  >
                    <td className="px-4 py-3">
                      <div className="font-mono text-[var(--primary)] font-medium text-[12px]">{obl.id}</div>
                      <div className="text-[11px] text-[var(--text-muted)] mt-0.5 truncate max-w-[150px]" title={obl.source}>{obl.source}</div>
                    </td>
                    <td className="px-4 py-3 max-w-[200px] truncate">
                      <div className="font-medium text-[var(--text-primary)]">{obl.actor}</div>
                      <div className="text-[12px] text-[var(--text-secondary)] mt-0.5 truncate">{obl.action}</div>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{obl.deadline}</td>
                    <td className="px-4 py-3">
                      <StatusBadge type="risk" value={obl.risk} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge type="evidence" value={obl.evidence} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge type="review" value={obl.review} />
                    </td>
                    <td className="px-4 py-3 text-[var(--text-muted)] text-[12px]">{obl.updated}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                        <button className="p-1 text-[var(--text-muted)] hover:text-[var(--primary)] transition-colors">
                          <MoreHorizontal size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Context Panel Drawer */}
      {selectedRow && (
        <div className="w-1/3 bg-white border border-[var(--border-subtle)] rounded-2xl shadow-xl flex flex-col overflow-hidden animate-slide-left">
          <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--surface-subtle)]">
            <h3 className="font-mono text-[14px] font-bold text-[var(--primary)]">{selectedRow}</h3>
            <button onClick={() => setSelectedRow(null)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
              <X size={18} />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div>
              <p className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-2">Normalized Obligation</p>
              <p className="text-[15px] font-medium text-[var(--text-primary)] leading-relaxed">
                The {obligations.find(o => o.id === selectedRow)?.actor} shall {obligations.find(o => o.id === selectedRow)?.action.toLowerCase()} regarding {obligations.find(o => o.id === selectedRow)?.object}.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-[var(--border-subtle)]">
              <div>
                <p className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1">Actor</p>
                <p className="text-[13px] font-medium text-[var(--text-primary)]">{obligations.find(o => o.id === selectedRow)?.actor}</p>
              </div>
              <div>
                <p className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1">Action</p>
                <p className="text-[13px] font-medium text-[var(--text-primary)]">{obligations.find(o => o.id === selectedRow)?.action}</p>
              </div>
              <div>
                <p className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1">Deadline</p>
                <p className="text-[13px] font-medium text-[var(--text-primary)]">{obligations.find(o => o.id === selectedRow)?.deadline}</p>
              </div>
              <div>
                <p className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1">Risk</p>
                <StatusBadge type="risk" value={obligations.find(o => o.id === selectedRow)?.risk || ''} />
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border-subtle)]">
              <p className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-2">Source Citation</p>
              <div className="bg-[var(--surface-subtle)] border border-[var(--border-default)] rounded-lg p-3">
                <div className="flex items-center space-x-2 text-[13px] font-mono text-[var(--text-secondary)] mb-2">
                  <Database size={14} className="text-[var(--primary)]" />
                  <span>{obligations.find(o => o.id === selectedRow)?.source} • Clause 4.2.1</span>
                </div>
                <p className="text-[12px] text-[var(--text-secondary)] italic border-l-2 border-[var(--primary-light)] pl-3">
                  "...shall ensure that client funds are segregated and maintained on a daily basis..."
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-[var(--border-subtle)] flex space-x-4">
              <div className="flex items-center space-x-2">
                <CheckCircle2 size={16} className="text-[#10B981]" />
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">Validation Passed</span>
              </div>
              <div className="flex items-center space-x-2">
                <CheckCircle2 size={16} className="text-[#10B981]" />
                <span className="text-[12px] font-medium text-[var(--text-secondary)]">Citation Verified</span>
              </div>
            </div>
          </div>
          
          <div className="p-4 border-t border-[var(--border-subtle)] bg-[var(--surface-subtle)]">
            <button className="w-full flex items-center justify-center space-x-2 bg-white border border-[var(--border-strong)] text-[var(--text-primary)] px-4 py-2 rounded-lg hover:border-[var(--primary)] hover:text-[var(--primary)] transition-all font-medium text-[13px] shadow-sm">
              <span>Open Full Obligation</span>
              <ExternalLink size={14} />
            </button>
          </div>
        </div>
      )}

    </div>
  );
}

function FilterSelect({ label }: { label: string }) {
  return (
    <button className="flex items-center space-x-1.5 px-3 py-1.5 border border-[var(--border-default)] rounded-md bg-white hover:bg-[var(--surface-hover)] transition-colors shrink-0">
      <span className="text-[12px] font-medium text-[var(--text-secondary)]">{label}</span>
      <ChevronDown size={14} className="text-[var(--text-muted)]" />
    </button>
  );
}

function StatusBadge({ type, value }: { type: string, value: string }) {
  let colors = "";
  if (type === 'risk') {
    if (value === 'Critical') colors = 'bg-[#FEF2F2] text-[#DC2626] border-[#FCA5A5]';
    else if (value === 'High') colors = 'bg-[#FFF7ED] text-[#EA580C] border-[#FDBA74]';
    else colors = 'bg-[#FFFBEB] text-[#D97706] border-[#FDE68A]';
  } else if (type === 'evidence') {
    if (value === 'Mapped') colors = 'bg-[#F0FDF4] text-[#16A34A] border-[#86EFAC]';
    else colors = 'bg-[#FEF2F2] text-[#DC2626] border-[#FCA5A5]';
  } else if (type === 'review') {
    if (value === 'Approved') colors = 'bg-[var(--primary-subtle)] text-[var(--primary)] border-[var(--primary-light)]';
    else colors = 'bg-[#F8FAFC] text-[#475569] border-[#CBD5E1]';
  }

  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-[10px] uppercase font-bold border", colors)}>
      {type === 'risk' && value === 'Critical' && <AlertCircle size={10} className="mr-1" />}
      {value}
    </span>
  );
}
