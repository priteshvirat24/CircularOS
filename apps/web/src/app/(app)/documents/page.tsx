"use client";

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
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
          <h1 className="text-[32px] font-semibold tracking-tight text-[var(--text-primary)]">Documents</h1>
          <p className="text-[var(--text-secondary)] mt-1">Manage and monitor regulatory document ingestions</p>
        </div>
        <div className="flex space-x-3">
          <button className="flex items-center space-x-2 px-4 py-2 bg-white border border-[var(--border-default)] rounded-lg text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition-colors shadow-sm font-medium">
            <Upload size={18} />
            <span>Upload PDF</span>
          </button>
          <button className="flex items-center space-x-2 px-4 py-2 bg-[var(--primary)] border border-transparent rounded-lg text-white hover:bg-[var(--primary-hover)] transition-colors shadow-sm font-medium">
            <Plus size={18} />
            <span>Ingest URL</span>
          </button>
        </div>
      </div>

      <Card className="shadow-sm">
        <div className="p-4 border-b border-[var(--border-subtle)] flex justify-between items-center bg-white rounded-t-2xl">
          <div className="relative w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] w-4 h-4" />
            <input 
              type="text" 
              placeholder="Search by title, reference number..." 
              className="w-full bg-white border border-[var(--border-default)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-light)] focus:border-[var(--primary)] transition-all shadow-sm"
            />
          </div>
          <button className="flex items-center space-x-2 px-3 py-2 bg-white border border-[var(--border-default)] rounded-lg text-[var(--text-primary)] hover:bg-[var(--surface-hover)] transition-colors text-sm shadow-sm font-medium">
            <Filter size={16} />
            <span>Filter</span>
          </button>
        </div>

        <div className="overflow-x-auto bg-white">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[var(--surface-subtle)] text-[12px] uppercase tracking-wider text-[var(--text-secondary)] border-b border-[var(--border-default)]">
                <th className="px-6 py-3 font-semibold">Document Title</th>
                <th className="px-6 py-3 font-semibold">Domain</th>
                <th className="px-6 py-3 font-semibold">Issued Date</th>
                <th className="px-6 py-3 font-semibold">Quality</th>
                <th className="px-6 py-3 font-semibold">Obligations</th>
                <th className="px-6 py-3 font-semibold">Status</th>
                <th className="px-6 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)] text-[14px]">
              {documents.map((doc, i) => (
                <tr 
                  key={doc.id} 
                  className="hover:bg-[var(--surface-hover)] transition-colors group cursor-pointer bg-white"
                  onMouseEnter={() => setIsHovered(i)}
                  onMouseLeave={() => setIsHovered(null)}
                >
                  <td className="px-6 py-4 max-w-md">
                    <div className="flex items-start space-x-3">
                      <div className="mt-1">
                        <FileText className="text-[var(--text-muted)] w-4 h-4" />
                      </div>
                      <div>
                        <p className="font-medium text-[var(--text-primary)] truncate">{doc.title}</p>
                        <p className="text-[12px] text-[var(--text-secondary)] mt-1 font-mono">{doc.ref}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-[var(--surface-subtle)] border border-[var(--border-subtle)] rounded text-[12px] font-medium text-[var(--text-primary)]">
                      {doc.type}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-[var(--text-secondary)] whitespace-nowrap">
                    {doc.date}
                  </td>
                  <td className="px-6 py-4">
                    {doc.score ? (
                      <div className="flex items-center space-x-2">
                        <div className="w-full bg-[var(--border-subtle)] rounded-full h-1.5 w-16 overflow-hidden">
                          <div 
                            className={cn(
                              "h-1.5 rounded-full",
                              doc.score > 0.9 ? "bg-[#10B981]" : doc.score > 0.7 ? "bg-[#F59E0B]" : "bg-[#EF4444]"
                            )}
                            style={{ width: `${doc.score * 100}%` }}
                          ></div>
                        </div>
                        <span className="text-[12px] text-[var(--text-secondary)] font-medium">{(doc.score * 100).toFixed(0)}%</span>
                      </div>
                    ) : (
                      <span className="text-[12px] text-[var(--text-muted)] font-medium">N/A</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "font-mono font-medium",
                      doc.obl === '-' ? "text-[var(--text-muted)]" : "text-[var(--primary)]"
                    )}>
                      {doc.obl}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "inline-flex items-center px-2.5 py-1 rounded-md text-[12px] font-medium border",
                      doc.status === 'Extracted' ? 'bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]' :
                      doc.status === 'Processing' ? 'bg-[#EFF6FF] text-[#2563EB] border-[#BFDBFE]' :
                      doc.status === 'Failed' ? 'bg-[#FEF2F2] text-[#DC2626] border-[#FECACA]' :
                      'bg-[#FFFBEB] text-[#D97706] border-[#FDE68A]'
                    )}>
                      {doc.status === 'Processing' && (
                        <div className="w-1.5 h-1.5 rounded-full bg-[#3B82F6] mr-2 animate-pulse"></div>
                      )}
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] rounded-md transition-colors">
                      <MoreVertical size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-4 border-t border-[var(--border-subtle)] flex items-center justify-between text-sm text-[var(--text-secondary)] bg-[var(--surface-subtle)] rounded-b-2xl">
          <div>Showing 1 to 5 of 1,248 entries</div>
          <div className="flex space-x-1">
            <button className="px-3 py-1 bg-white border border-[var(--border-default)] text-[var(--text-muted)] rounded-md shadow-sm disabled:opacity-50" disabled>Prev</button>
            <button className="px-3 py-1 bg-[var(--primary-light)] border border-[var(--primary-subtle)] text-[var(--primary)] font-medium rounded-md">1</button>
            <button className="px-3 py-1 bg-white border border-[var(--border-default)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] rounded-md shadow-sm">2</button>
            <button className="px-3 py-1 bg-white border border-[var(--border-default)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] rounded-md shadow-sm">3</button>
            <button className="px-3 py-1 bg-white border border-[var(--border-default)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)] rounded-md shadow-sm">Next</button>
          </div>
        </div>
      </Card>
    </div>
  );
}
