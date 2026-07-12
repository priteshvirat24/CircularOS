"use client";

import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Search, Filter, ShieldCheck, AlertCircle, ArrowUpRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function ObligationsPage() {
  const obligations = [
    { id: 'OBL-9182', actor: 'Depository Participant', action: 'Submit concurrent audit report', object: 'Audit Report', deadline: 'Quarterly', risk: 'High', status: 'Active', source: 'SEBI/HO/MIRSD' },
    { id: 'OBL-9183', actor: 'Stock Broker', action: 'Maintain client funds segregation', object: 'Client Funds', deadline: 'Daily', risk: 'Critical', status: 'Active', source: 'SEBI/HO/MIRSD' },
    { id: 'OBL-9184', actor: 'Listed Entity', action: 'Disclose material events', object: 'Stock Exchanges', deadline: 'Within 24 hours', risk: 'Critical', status: 'Active', source: 'LODR Reg 30' },
    { id: 'OBL-9185', actor: 'Clearing Member', action: 'Report margin shortfalls', object: 'Clearing Corporation', deadline: 'T+1 day', risk: 'Medium', status: 'Active', source: 'NSE/CMPT/2026' },
  ];

  return (
    <div className="space-y-6 pb-12">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-4xl font-bold font-outfit tracking-tight">Obligation Registry</h1>
          <p className="text-slate-400 mt-2">Master ledger of all active regulatory obligations</p>
        </div>
      </div>

      <Card className="border-slate-800/60 shadow-2xl">
        <div className="p-4 border-b border-slate-800/50 flex justify-between items-center bg-slate-900/50 rounded-t-xl">
          <div className="relative w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 w-4 h-4" />
            <input 
              type="text" 
              placeholder="Search obligations, actors, or actions..." 
              className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
            />
          </div>
          <button className="flex items-center space-x-2 px-3 py-1.5 bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-300 hover:bg-slate-700/50 transition-colors text-sm">
            <Filter size={16} />
            <span>Filter</span>
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900/30 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800/50">
                <th className="px-6 py-4 font-medium">Obligation ID</th>
                <th className="px-6 py-4 font-medium">Actor</th>
                <th className="px-6 py-4 font-medium">Action</th>
                <th className="px-6 py-4 font-medium">Deadline / Frequency</th>
                <th className="px-6 py-4 font-medium">Risk Level</th>
                <th className="px-6 py-4 text-right font-medium">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-sm">
              {obligations.map((obl, i) => (
                <tr key={obl.id} className="hover:bg-slate-800/40 transition-colors group cursor-pointer">
                  <td className="px-6 py-4">
                    <div className="font-mono text-blue-400">{obl.id}</div>
                    <div className="text-xs text-slate-500 mt-1">{obl.source}</div>
                  </td>
                  <td className="px-6 py-4 font-medium text-slate-200">{obl.actor}</td>
                  <td className="px-6 py-4 text-slate-300 max-w-sm">
                    {obl.action} <span className="text-slate-500 italic">({obl.object})</span>
                  </td>
                  <td className="px-6 py-4 text-slate-400">{obl.deadline}</td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "inline-flex items-center px-2 py-1 rounded text-[10px] uppercase font-bold",
                      obl.risk === 'Critical' ? 'bg-red-500/20 text-red-400' :
                      obl.risk === 'High' ? 'bg-orange-500/20 text-orange-400' :
                      'bg-yellow-500/20 text-yellow-400'
                    )}>
                      {obl.risk === 'Critical' && <AlertCircle size={10} className="mr-1" />}
                      {obl.risk}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-slate-400 hover:text-blue-400 transition-colors">
                      <ArrowUpRight size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
