"use client";

import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Search, Plus, Filter, FileText, MoreVertical, Upload } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function DocumentsPage() {
  const [isHovered, setIsHovered] = useState<number | null>(null);

  // Mock data for display
  const documents = [
    { id: '1', title: 'Master Circular on Surveillance of Securities Market', ref: 'SEBI/HO/ISD/ISD/CIR/P/2021/22', date: 'Mar 23, 2026', type: 'SEBI', status: 'Extracted', score: 0.98, pages: 42, obl: 145 },
    { id: '2', title: 'Master Direction - Information Technology Framework', ref: 'RBI/2021-22/76', date: 'Apr 15, 2026', type: 'RBI', status: 'Processing', score: null, pages: 112, obl: '-' },
    { id: '3', title: 'Trading Halt due to Index limit breach', ref: 'NSE/CMTR/49333', date: 'May 02, 2026', type: 'NSE', status: 'Pending Review', score: 0.95, pages: 5, obl: 12 },
    { id: '4', title: 'Filing of disclosures under SEBI Regulations', ref: 'BSE/LIST/2022-23/04', date: 'May 10, 2026', type: 'BSE', status: 'Extracted', score: 0.99, pages: 18, obl: 34 },
    { id: '5', title: 'Guidelines for Anti-Money Laundering', ref: 'PFRDA/2022/28/REG-MA/1', date: 'Jun 05, 2026', type: 'PFRDA', status: 'Failed', score: 0.23, pages: 56, obl: '-' },
  ];

  return (
    <div className="space-y-6 pb-12">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-4xl font-bold font-outfit tracking-tight">Documents</h1>
          <p className="text-slate-400 mt-2">Manage and monitor regulatory document ingestions</p>
        </div>
        <div className="flex space-x-3">
          <button className="flex items-center space-x-2 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:text-white hover:bg-slate-700 transition-colors">
            <Upload size={18} />
            <span>Upload PDF</span>
          </button>
          <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 border border-blue-500 rounded-lg text-white hover:bg-blue-500 transition-colors shadow-lg shadow-blue-500/20">
            <Plus size={18} />
            <span>Ingest URL</span>
          </button>
        </div>
      </div>

      <Card className="border-slate-800/60 shadow-2xl">
        <div className="p-4 border-b border-slate-800/50 flex justify-between items-center bg-slate-900/50 rounded-t-xl">
          <div className="relative w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 w-4 h-4" />
            <input 
              type="text" 
              placeholder="Search by title, reference number..." 
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
                <th className="px-6 py-4 font-medium">Document Title</th>
                <th className="px-6 py-4 font-medium">Domain</th>
                <th className="px-6 py-4 font-medium">Issued Date</th>
                <th className="px-6 py-4 font-medium">Quality</th>
                <th className="px-6 py-4 font-medium">Obligations</th>
                <th className="px-6 py-4 font-medium">Status</th>
                <th className="px-6 py-4 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-sm">
              {documents.map((doc, i) => (
                <tr 
                  key={doc.id} 
                  className="hover:bg-slate-800/40 transition-colors group cursor-pointer"
                  onMouseEnter={() => setIsHovered(i)}
                  onMouseLeave={() => setIsHovered(null)}
                >
                  <td className="px-6 py-4 max-w-md">
                    <div className="flex items-start space-x-3">
                      <div className="mt-1">
                        <FileText className="text-slate-500 w-4 h-4" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-200 truncate">{doc.title}</p>
                        <p className="text-xs text-slate-500 mt-1 font-mono">{doc.ref}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs font-semibold text-slate-300">
                      {doc.type}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-400 whitespace-nowrap">
                    {doc.date}
                  </td>
                  <td className="px-6 py-4">
                    {doc.score ? (
                      <div className="flex items-center space-x-2">
                        <div className="w-full bg-slate-800 rounded-full h-1.5 w-16">
                          <div 
                            className={cn(
                              "h-1.5 rounded-full",
                              doc.score > 0.9 ? "bg-emerald-500" : doc.score > 0.7 ? "bg-amber-500" : "bg-red-500"
                            )}
                            style={{ width: `${doc.score * 100}%` }}
                          ></div>
                        </div>
                        <span className="text-xs text-slate-400">{(doc.score * 100).toFixed(0)}%</span>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-500">N/A</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "font-mono",
                      doc.obl === '-' ? "text-slate-500" : "text-blue-400 font-bold"
                    )}>
                      {doc.obl}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border",
                      doc.status === 'Extracted' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                      doc.status === 'Processing' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                      doc.status === 'Failed' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                      'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    )}>
                      {doc.status === 'Processing' && (
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-400 mr-2 animate-pulse"></div>
                      )}
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-md transition-colors">
                      <MoreVertical size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-4 border-t border-slate-800/50 flex items-center justify-between text-sm text-slate-400 bg-slate-900/30 rounded-b-xl">
          <div>Showing 1 to 5 of 1,248 entries</div>
          <div className="flex space-x-1">
            <button className="px-3 py-1 bg-slate-800 border border-slate-700 rounded-md hover:bg-slate-700 disabled:opacity-50" disabled>Prev</button>
            <button className="px-3 py-1 bg-blue-600/20 border border-blue-500/30 text-blue-400 rounded-md">1</button>
            <button className="px-3 py-1 bg-slate-800 border border-slate-700 rounded-md hover:bg-slate-700">2</button>
            <button className="px-3 py-1 bg-slate-800 border border-slate-700 rounded-md hover:bg-slate-700">3</button>
            <button className="px-3 py-1 bg-slate-800 border border-slate-700 rounded-md hover:bg-slate-700">Next</button>
          </div>
        </div>
      </Card>
    </div>
  );
}
