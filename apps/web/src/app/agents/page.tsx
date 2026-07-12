"use client";

import React from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Cpu, Activity, Clock, DollarSign, Database, CheckCircle2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

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
          <h1 className="text-4xl font-bold font-outfit tracking-tight">Agent Traces</h1>
          <p className="text-slate-400 mt-2">Monitor LangGraph node executions, latency, and costs</p>
        </div>
        <div className="flex space-x-4">
          <div className="text-right">
            <p className="text-sm text-slate-400">Total API Cost (24h)</p>
            <p className="text-xl font-bold text-slate-200 font-mono">$12.45</p>
          </div>
          <div className="text-right pl-4 border-l border-slate-700">
            <p className="text-sm text-slate-400">Total Tokens (24h)</p>
            <p className="text-xl font-bold text-slate-200 font-mono">2.4M</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        {[
          { label: 'Success Rate', value: '99.2%', icon: <CheckCircle2 className="text-emerald-400" /> },
          { label: 'Avg Latency', value: '1.2s', icon: <Clock className="text-blue-400" /> },
          { label: 'Avg Cost / Doc', value: '$0.14', icon: <DollarSign className="text-amber-400" /> },
          { label: 'Active Agents', value: '3', icon: <Cpu className="text-purple-400" /> },
        ].map((stat, i) => (
          <Card key={i} className="bg-slate-900/40 border-slate-800/50">
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">{stat.label}</p>
                <p className="text-2xl font-bold font-outfit mt-1">{stat.value}</p>
              </div>
              <div className="p-3 bg-slate-800/50 rounded-lg">
                {stat.icon}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="border-slate-800/60 shadow-2xl">
        <div className="p-4 border-b border-slate-800/50 flex justify-between items-center bg-slate-900/50 rounded-t-xl">
          <h3 className="font-semibold text-slate-200 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-blue-400" />
            Live Execution Traces
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900/30 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800/50">
                <th className="px-6 py-4 font-medium">Run ID</th>
                <th className="px-6 py-4 font-medium">Document Context</th>
                <th className="px-6 py-4 font-medium">Agent Node</th>
                <th className="px-6 py-4 font-medium">Model</th>
                <th className="px-6 py-4 font-medium">Latency</th>
                <th className="px-6 py-4 font-medium">Tokens</th>
                <th className="px-6 py-4 font-medium">Cost</th>
                <th className="px-6 py-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-sm font-mono">
              {traces.map((trace, i) => (
                <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-6 py-4 text-slate-400">{trace.id}</td>
                  <td className="px-6 py-4 font-sans max-w-[200px] truncate text-slate-300" title={trace.doc}>
                    {trace.doc}
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded font-sans text-xs font-semibold">
                      {trace.agent}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-400">{trace.model}</td>
                  <td className="px-6 py-4 text-slate-300">{trace.latency}</td>
                  <td className="px-6 py-4 text-slate-300">{trace.tokens.toLocaleString()}</td>
                  <td className="px-6 py-4 text-emerald-400">{trace.cost}</td>
                  <td className="px-6 py-4">
                    {trace.status === 'success' ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-500" />
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
