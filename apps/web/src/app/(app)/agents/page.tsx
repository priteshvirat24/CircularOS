"use client";

import React from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Cpu, Activity, Clock, DollarSign, CheckCircle2, XCircle } from 'lucide-react';

export default function AgentsPage() {
  const traces = [
    { id: 'run-9f8a', doc: 'SEBI Master Circular on Surveillance', agent: 'Document Classifier', model: 'gpt-4o-mini', status: 'success', latency: '450ms', tokens: 1050, cost: '$0.0001' },
    { id: 'run-9f8a', doc: 'SEBI Master Circular on Surveillance', agent: 'Clause Classifier', model: 'gpt-4o-mini', status: 'success', latency: '1200ms', tokens: 8400, cost: '$0.0008' },
    { id: 'run-9f8a', doc: 'SEBI Master Circular on Surveillance', agent: 'Obligation Extractor', model: 'gpt-4o', status: 'success', latency: '14500ms', tokens: 42500, cost: '$0.2125' },
    { id: 'run-7b2c', doc: 'RBI Cyber Security Framework', agent: 'Document Classifier', model: 'gpt-4o-mini', status: 'success', latency: '380ms', tokens: 980, cost: '$0.0001' },
    { id: 'run-7b2c', doc: 'RBI Cyber Security Framework', agent: 'Clause Classifier', model: 'gpt-4o-mini', status: 'failed', latency: '5000ms', tokens: 0, cost: '$0.0000' },
  ];

  return (
    <div className="space-y-6 pb-12">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-[32px] font-semibold tracking-tight text-[var(--text-primary)]">Agent Traces</h1>
          <p className="text-[var(--text-secondary)] mt-1">Monitor LangGraph node executions, latency, and costs</p>
        </div>
        <div className="flex space-x-6">
          <div className="text-right">
            <p className="text-sm text-[var(--text-secondary)]">Total API Cost (24h)</p>
            <p className="text-[20px] font-bold text-[var(--text-primary)] font-mono">$12.45</p>
          </div>
          <div className="text-right pl-6 border-l border-[var(--border-default)]">
            <p className="text-sm text-[var(--text-secondary)]">Total Tokens (24h)</p>
            <p className="text-[20px] font-bold text-[var(--text-primary)] font-mono">2.4M</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        {[
          { label: 'Success Rate', value: '99.2%', icon: <CheckCircle2 className="text-[var(--success)]" /> },
          { label: 'Avg Latency', value: '1.2s', icon: <Clock className="text-[var(--primary)]" /> },
          { label: 'Avg Cost / Doc', value: '$0.14', icon: <DollarSign className="text-[#D97706]" /> },
          { label: 'Active Agents', value: '3', icon: <Cpu className="text-[var(--secondary-brand)]" /> },
        ].map((stat, i) => (
          <Card key={i} className="bg-white border-[var(--border-default)] shadow-sm">
            <CardContent className="p-5 flex items-center justify-between">
              <div>
                <p className="text-sm text-[var(--text-secondary)] font-medium">{stat.label}</p>
                <p className="text-[24px] font-semibold text-[var(--text-primary)] mt-1">{stat.value}</p>
              </div>
              <div className="p-3 bg-[var(--surface-subtle)] rounded-xl">
                {stat.icon}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="shadow-sm">
        <div className="p-5 border-b border-[var(--border-subtle)] bg-white rounded-t-2xl flex justify-between items-center">
          <h3 className="font-semibold text-[var(--text-primary)] flex items-center">
            <Activity className="w-5 h-5 mr-2 text-[var(--primary)]" />
            Live Execution Traces
          </h3>
        </div>

        <div className="overflow-x-auto bg-white rounded-b-2xl">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[var(--surface-subtle)] text-[12px] uppercase tracking-wider text-[var(--text-secondary)] border-b border-[var(--border-default)]">
                <th className="px-6 py-3 font-semibold">Run ID</th>
                <th className="px-6 py-3 font-semibold">Document Context</th>
                <th className="px-6 py-3 font-semibold">Agent Node</th>
                <th className="px-6 py-3 font-semibold">Model</th>
                <th className="px-6 py-3 font-semibold">Latency</th>
                <th className="px-6 py-3 font-semibold">Tokens</th>
                <th className="px-6 py-3 font-semibold">Cost</th>
                <th className="px-6 py-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)] text-[14px]">
              {traces.map((trace, i) => (
                <tr key={i} className="hover:bg-[var(--surface-hover)] transition-colors">
                  <td className="px-6 py-4 font-mono text-[var(--text-muted)] font-medium">{trace.id}</td>
                  <td className="px-6 py-4 max-w-[200px] truncate text-[var(--text-primary)] font-medium" title={trace.doc}>
                    {trace.doc}
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2.5 py-1 bg-[var(--primary-subtle)] text-[var(--primary)] border border-[var(--primary-light)] rounded-md text-[12px] font-semibold">
                      {trace.agent}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-[var(--text-secondary)]">{trace.model}</td>
                  <td className="px-6 py-4 text-[var(--text-primary)]">{trace.latency}</td>
                  <td className="px-6 py-4 text-[var(--text-primary)]">{trace.tokens.toLocaleString()}</td>
                  <td className="px-6 py-4 text-[var(--success)] font-medium">{trace.cost}</td>
                  <td className="px-6 py-4">
                    {trace.status === 'success' ? (
                      <CheckCircle2 className="w-5 h-5 text-[#10B981]" />
                    ) : (
                      <XCircle className="w-5 h-5 text-[#EF4444]" />
                    )}
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
