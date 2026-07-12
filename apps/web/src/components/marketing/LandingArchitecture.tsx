"use client";

import React, { useState } from 'react';
import { Settings2, Cpu, Activity, AlertTriangle, FileCheck2, ArrowDown } from 'lucide-react';
import { cn } from '@/lib/utils';

const ARCHITECTURE_LAYERS = [
  { id: 'source', name: 'OFFICIAL SOURCES', tech: 'External', inputs: 'PDFs, Web', outputs: 'Raw Files' },
  { id: 'acq', name: 'DOCUMENT ACQUISITION', tech: 'Python, httpx', inputs: 'URLs', outputs: 'Raw PDFs' },
  { id: 'ver', name: 'INTEGRITY VERIFICATION', tech: 'SHA-256', inputs: 'Raw PDFs', outputs: 'Verified PDFs' },
  { id: 'parse', name: 'PARSING + OCR', tech: 'Marker, LlamaParse', inputs: 'Verified PDFs', outputs: 'Markdown' },
  { id: 'recon', name: 'HIERARCHICAL RECONSTRUCTION', tech: 'Custom Python', inputs: 'Markdown', outputs: 'Structured JSON' },
  { id: 'kg', name: 'REGULATORY KNOWLEDGE GRAPH', tech: 'Neo4j / NetworkX', inputs: 'Structured JSON', outputs: 'Graph Entities' },
  { id: 'sup', name: 'LANGGRAPH SUPERVISOR', tech: 'LangGraph', inputs: 'User Intent, Graph', outputs: 'Agent Routing' },
  { id: 'sub', name: 'SPECIALIZED AGENT SUBGRAPHS', tech: 'LangGraph', inputs: 'Routed Context', outputs: 'Draft Extractions' },
  { id: 'det', name: 'DETERMINISTIC VALIDATORS', tech: 'Pydantic, Regex', inputs: 'Draft Extractions', outputs: 'Validated Data' },
  { id: 'hitl', name: 'HUMAN REVIEW INTERRUPTS', tech: 'FastAPI, Postgres', inputs: 'Validated Data', outputs: 'Approved State' },
  { id: 'reg', name: 'VERSIONED OBLIGATION REGISTRY', tech: 'Postgres', inputs: 'Approved State', outputs: 'DB Records' },
  { id: 'diff', name: 'REGULATORY DIFF ENGINE', tech: 'Custom Python', inputs: 'Old vs New', outputs: 'Change Events' },
  { id: 'map', name: 'CONTROL + EVIDENCE MAPPING', tech: 'Vector DB', inputs: 'Obligations', outputs: 'Linked Controls' },
  { id: 'ops', name: 'COMPLIANCE OPERATIONS', tech: 'Celery / API', inputs: 'Linked Controls', outputs: 'Tasks, Alerts' },
  { id: 'suptech', name: 'SUPTECH ANALYTICS', tech: 'SQL Aggregates', inputs: 'Tasks, Alerts', outputs: 'Systemic Metrics' },
];

export function LandingArchitecture() {
  const [activeLayer, setActiveLayer] = useState(ARCHITECTURE_LAYERS[6]); // default to Supervisor

  return (
    <section id="architecture" className="bg-[var(--background-secondary)] py-32 border-t border-[var(--border-subtle)]">
      <div className="max-w-[1440px] mx-auto px-6">
        <div className="text-center mb-20">
          <h2 className="text-[32px] md:text-[40px] font-semibold tracking-tight text-[var(--text-primary)] mb-2">
            NOT A CHATBOT OVER PDFs.
          </h2>
          <h3 className="text-[32px] md:text-[40px] font-semibold tracking-tight text-[var(--primary)]">
            A REGULATORY INTELLIGENCE SYSTEM.
          </h3>
        </div>

        <div className="flex flex-col lg:flex-row items-start justify-center gap-16 max-w-6xl mx-auto">
          
          {/* Pipeline */}
          <div className="w-full lg:w-1/2 flex flex-col items-center">
            {ARCHITECTURE_LAYERS.map((layer, idx) => (
              <React.Fragment key={layer.id}>
                <button
                  onClick={() => setActiveLayer(layer)}
                  className={cn(
                    "w-full max-w-md py-3 px-6 rounded-lg font-mono text-[13px] font-semibold tracking-widest text-center transition-all duration-200 border",
                    activeLayer.id === layer.id 
                      ? "bg-[var(--primary)] text-white border-[var(--primary-hover)] shadow-md scale-[1.02]" 
                      : "bg-white text-[var(--text-secondary)] border-[var(--border-default)] hover:border-[var(--primary-light)] hover:text-[var(--primary)] shadow-sm"
                  )}
                >
                  {layer.name}
                </button>
                {idx < ARCHITECTURE_LAYERS.length - 1 && (
                  <ArrowDown size={16} className="text-[var(--border-strong)] my-1.5" />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Details Panel */}
          <div className="w-full lg:w-1/2 sticky top-32">
            <div className="bg-white border border-[var(--border-subtle)] rounded-2xl p-8 shadow-xl">
              <h4 className="text-[24px] font-semibold text-[var(--text-primary)] tracking-tight mb-8">
                {activeLayer.name}
              </h4>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <p className="flex items-center text-[12px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    <Settings2 size={14} className="mr-2" /> Technology
                  </p>
                  <p className="text-[15px] font-medium text-[var(--text-primary)]">{activeLayer.tech}</p>
                </div>
                <div>
                  <p className="flex items-center text-[12px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    <Activity size={14} className="mr-2" /> Observability
                  </p>
                  <p className="text-[15px] font-medium text-[var(--text-primary)]">LangSmith / DataDog</p>
                </div>
                <div>
                  <p className="flex items-center text-[12px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    <ArrowDown size={14} className="mr-2" /> Inputs
                  </p>
                  <p className="text-[15px] font-medium text-[var(--text-primary)]">{activeLayer.inputs}</p>
                </div>
                <div>
                  <p className="flex items-center text-[12px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    <ArrowDown size={14} className="mr-2 rotate-180" /> Outputs
                  </p>
                  <p className="text-[15px] font-medium text-[var(--text-primary)]">{activeLayer.outputs}</p>
                </div>
                <div className="col-span-full">
                  <p className="flex items-center text-[12px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    <AlertTriangle size={14} className="mr-2" /> Failure Handling
                  </p>
                  <p className="text-[15px] font-medium text-[var(--text-primary)]">Circuit breaker pattern with exponential backoff. Manual fallback queued.</p>
                </div>
                <div className="col-span-full">
                  <p className="flex items-center text-[12px] font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    <FileCheck2 size={14} className="mr-2" /> Evaluation
                  </p>
                  <p className="text-[15px] font-medium text-[var(--text-primary)]">RAGAS evaluation suite against ground-truth datasets.</p>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
