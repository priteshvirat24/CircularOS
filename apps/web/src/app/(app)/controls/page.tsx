"use client";

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Search, Plus, Link2, FileUp } from 'lucide-react';

export default function ControlsPage() {
  const controls = [
    { id: 'CTRL-001', code: 'SEC-01', framework: 'ISO 27001', desc: 'Information Security Policy', obligations: 12, status: 'Active' },
    { id: 'CTRL-002', code: 'AM-01', framework: 'SEBI SCRA', desc: 'Asset Management and Segregation', obligations: 45, status: 'Active' },
    { id: 'CTRL-003', code: 'CYB-04', framework: 'RBI CSF', desc: 'Incident Response and Reporting', obligations: 8, status: 'Needs Review' },
    { id: 'CTRL-004', code: 'AUD-02', framework: 'Internal', desc: 'Quarterly Concurrent Audits', obligations: 3, status: 'Active' },
  ];

  return (
    <div className="space-y-6 pb-12">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-[32px] font-semibold tracking-tight text-[var(--text-primary)]">Control Library & Evidence</h1>
          <p className="text-[var(--text-secondary)] mt-1">Map obligations to internal controls and upload compliance evidence</p>
        </div>
        <div className="flex space-x-3">
          <button className="flex items-center space-x-2 px-4 py-2 bg-[var(--primary)] border border-transparent rounded-lg text-white hover:bg-[var(--primary-hover)] transition-colors shadow-sm font-medium">
            <Plus size={18} />
            <span>New Control</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card className="h-full shadow-sm">
            <div className="p-4 border-b border-[var(--border-subtle)] bg-white rounded-t-2xl">
              <div className="relative w-72">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] w-4 h-4" />
                <input 
                  type="text" 
                  placeholder="Search controls..." 
                  className="w-full bg-white border border-[var(--border-default)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-light)] focus:border-[var(--primary)] transition-all shadow-sm"
                />
              </div>
            </div>

            <div className="overflow-x-auto bg-white rounded-b-2xl">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[var(--surface-subtle)] text-[12px] uppercase tracking-wider text-[var(--text-secondary)] border-b border-[var(--border-default)]">
                    <th className="px-6 py-3 font-semibold">Control Code</th>
                    <th className="px-6 py-3 font-semibold">Description</th>
                    <th className="px-6 py-3 font-semibold">Framework</th>
                    <th className="px-6 py-3 font-semibold">Mapped Obs</th>
                    <th className="px-6 py-3 text-right font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)] text-[14px]">
                  {controls.map((ctrl) => (
                    <tr key={ctrl.id} className="hover:bg-[var(--surface-hover)] transition-colors cursor-pointer">
                      <td className="px-6 py-4 font-mono text-[var(--primary)] font-medium">{ctrl.code}</td>
                      <td className="px-6 py-4 text-[var(--text-primary)] font-medium">{ctrl.desc}</td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-1 bg-[var(--surface-subtle)] rounded text-[12px] text-[var(--text-primary)] border border-[var(--border-subtle)] font-medium">
                          {ctrl.framework}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-[var(--text-secondary)]">
                        <div className="flex items-center space-x-1 font-medium">
                          <Link2 size={14} className="text-[var(--text-muted)]" />
                          <span>{ctrl.obligations}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button className="text-[12px] font-medium px-3 py-1.5 bg-white text-[var(--text-primary)] border border-[var(--border-default)] rounded hover:bg-[var(--surface-hover)] transition-colors shadow-sm">
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="h-full shadow-sm">
            <CardHeader className="border-b border-[var(--border-subtle)] bg-white rounded-t-2xl pb-4">
              <CardTitle>Evidence Ledger</CardTitle>
              <CardDescription>Recent compliance artifacts uploaded</CardDescription>
            </CardHeader>
            <CardContent className="pt-6 space-y-4 bg-white rounded-b-2xl">
              <button className="w-full py-6 border-2 border-dashed border-[var(--border-default)] hover:border-[var(--primary)] hover:bg-[var(--primary-subtle)] rounded-xl flex flex-col items-center justify-center text-[var(--text-muted)] hover:text-[var(--primary)] transition-all group">
                <FileUp className="w-8 h-8 mb-2 opacity-50 group-hover:opacity-100 transition-opacity" />
                <span className="text-sm font-medium">Upload Evidence</span>
              </button>
              
              <div className="space-y-3 mt-4">
                {[
                  { name: 'Q1_Audit_Report.pdf', ctrl: 'AUD-02', date: 'Today' },
                  { name: 'Inc_Response_Log_March.xlsx', ctrl: 'CYB-04', date: 'Yesterday' },
                  { name: 'Policy_Manual_v3.pdf', ctrl: 'SEC-01', date: 'Last Week' },
                ].map((ev, i) => (
                  <div key={i} className="p-3 bg-white border border-[var(--border-subtle)] rounded-lg flex justify-between items-center hover:border-[var(--border-default)] hover:bg-[var(--surface-subtle)] transition-colors cursor-pointer">
                    <div>
                      <p className="text-[13px] text-[var(--text-primary)] font-medium truncate max-w-[200px]">{ev.name}</p>
                      <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">{ev.date}</p>
                    </div>
                    <span className="text-[10px] font-mono font-medium px-2 py-1 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] text-[var(--text-secondary)] rounded">
                      {ev.ctrl}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
