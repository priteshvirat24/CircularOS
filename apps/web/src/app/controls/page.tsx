"use client";

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Search, Plus, Filter, ShieldCheck, Link2, FileUp } from 'lucide-react';

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
          <h1 className="text-4xl font-bold font-outfit tracking-tight">Control Library & Evidence</h1>
          <p className="text-slate-400 mt-2">Map obligations to internal controls and upload compliance evidence</p>
        </div>
        <div className="flex space-x-3">
          <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 border border-blue-500 rounded-lg text-white hover:bg-blue-500 transition-colors shadow-lg shadow-blue-500/20">
            <Plus size={18} />
            <span>New Control</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card className="h-full border-slate-800/60 shadow-2xl">
            <div className="p-4 border-b border-slate-800/50 flex justify-between items-center bg-slate-900/50 rounded-t-xl">
              <div className="relative w-72">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 w-4 h-4" />
                <input 
                  type="text" 
                  placeholder="Search controls..." 
                  className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-900/30 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800/50">
                    <th className="px-6 py-4 font-medium">Control Code</th>
                    <th className="px-6 py-4 font-medium">Description</th>
                    <th className="px-6 py-4 font-medium">Framework</th>
                    <th className="px-6 py-4 font-medium">Mapped Obs</th>
                    <th className="px-6 py-4 text-right font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50 text-sm">
                  {controls.map((ctrl, i) => (
                    <tr key={ctrl.id} className="hover:bg-slate-800/40 transition-colors cursor-pointer">
                      <td className="px-6 py-4 font-mono text-blue-400 font-medium">{ctrl.code}</td>
                      <td className="px-6 py-4 text-slate-200">{ctrl.desc}</td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-1 bg-slate-800 rounded text-xs text-slate-300 border border-slate-700">
                          {ctrl.framework}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-300">
                        <div className="flex items-center space-x-1">
                          <Link2 size={14} className="text-slate-500" />
                          <span>{ctrl.obligations}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button className="text-xs px-3 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded hover:bg-emerald-500/20 transition-colors">
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
          <Card className="h-full border-slate-800/60 shadow-2xl">
            <CardHeader className="border-b border-slate-800/50 bg-slate-900/50 rounded-t-xl">
              <CardTitle>Evidence Ledger</CardTitle>
              <CardDescription>Recent compliance artifacts uploaded</CardDescription>
            </CardHeader>
            <CardContent className="pt-6 space-y-4">
              <button className="w-full py-4 border-2 border-dashed border-slate-700 hover:border-blue-500/50 rounded-xl flex flex-col items-center justify-center text-slate-400 hover:text-blue-400 hover:bg-blue-500/5 transition-all group">
                <FileUp className="w-8 h-8 mb-2 opacity-50 group-hover:opacity-100" />
                <span className="text-sm font-medium">Upload Evidence</span>
              </button>
              
              <div className="space-y-3 mt-4">
                {[
                  { name: 'Q1_Audit_Report.pdf', ctrl: 'AUD-02', date: 'Today' },
                  { name: 'Inc_Response_Log_March.xlsx', ctrl: 'CYB-04', date: 'Yesterday' },
                  { name: 'Policy_Manual_v3.pdf', ctrl: 'SEC-01', date: 'Last Week' },
                ].map((ev, i) => (
                  <div key={i} className="p-3 bg-slate-900/40 border border-slate-800/50 rounded-lg flex justify-between items-center hover:border-slate-700 transition-colors">
                    <div>
                      <p className="text-sm text-slate-200 font-medium truncate max-w-[200px]">{ev.name}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{ev.date}</p>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-1 bg-slate-800 text-slate-400 rounded">
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
