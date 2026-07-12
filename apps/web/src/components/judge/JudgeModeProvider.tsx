"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Play, Pause, SkipBack, SkipForward, X, RotateCcw, Volume2, VolumeX } from 'lucide-react';
import { cn } from '@/lib/utils';

// --- Types ---
export type VisualizationState = {
  activeAgent?: string;
  activeDoc?: string;
  activeObligation?: string;
  diffStatus?: 'idle' | 'showing_diff' | 'showing_impact';
};

export type JudgeSceneDefinition = {
  id: string;
  startMs: number;
  endMs: number;
  title: string;
  narrative: string;
  requiredData: string[];
  visualizationState: VisualizationState;
};

// 20 Second choreography (20000ms total)
export const JUDGE_SCENES: JudgeSceneDefinition[] = [
  { id: 'scene-1', startMs: 0, endMs: 2000, title: 'THE PROBLEM', narrative: "REGULATORY CHANGE DOESN'T ARRIVE AS STRUCTURED DATA.\nA NEW CIRCULAR LANDS.", requiredData: ['source_circular'], visualizationState: { activeDoc: 'circular_raw' } },
  { id: 'scene-2', startMs: 2000, endMs: 4500, title: 'DOCUMENT TO STRUCTURE', narrative: "CIRCULAROS RECONSTRUCTS THE REGULATION.", requiredData: ['parsed_clauses'], visualizationState: { activeDoc: 'clause_graph' } },
  { id: 'scene-3', startMs: 4500, endMs: 7500, title: 'AGENTIC EXTRACTION', narrative: "AI PROPOSES.\nVALIDATORS VERIFY.\nCRITICS TRY TO BREAK IT.", requiredData: ['agent_traces'], visualizationState: { activeAgent: 'Obligation Extractor' } },
  { id: 'scene-4', startMs: 7500, endMs: 10000, title: 'PROVENANCE', narrative: "NO CITATION.\nNO CLAIM.", requiredData: ['obligation_citation'], visualizationState: { activeObligation: 'OBL-001' } },
  { id: 'scene-5', startMs: 10000, endMs: 13000, title: 'REGULATORY DIFF', narrative: "CIRCULAROS DOESN'T JUST READ REGULATION.\nIT UNDERSTANDS WHAT CHANGED.", requiredData: ['diff_data'], visualizationState: { diffStatus: 'showing_diff' } },
  { id: 'scene-6', startMs: 13000, endMs: 16000, title: 'OPERATIONAL IMPACT', narrative: "ONE VERIFIED CHANGE.\nEVERY AFFECTED PROCESS UPDATED.", requiredData: ['control_mapping'], visualizationState: { diffStatus: 'showing_impact' } },
  { id: 'scene-7', startMs: 16000, endMs: 18500, title: 'SUPTECH MIRROR', narrative: "THE INTERMEDIARY SEES WHAT TO FIX.\nTHE REGULATOR SEES WHERE RISK IS BUILDING.", requiredData: ['suptech_metrics'], visualizationState: {} },
  { id: 'scene-8', startMs: 18500, endMs: 20000, title: 'FINAL POSITIONING', narrative: "FROM REGULATORY TEXT\nTO VERIFIED COMPLIANCE ACTION.\nCIRCULAROS.", requiredData: [], visualizationState: {} },
];

const TOTAL_DURATION_MS = 20000;

// --- Context ---
type JudgeModeContextType = {
  isActive: boolean;
  startJudgeMode: () => void;
  stopJudgeMode: () => void;
};

const JudgeModeContext = createContext<JudgeModeContextType | undefined>(undefined);

// --- Provider ---
export function JudgeModeProvider({ children }: { children: React.ReactNode }) {
  const [isActive, setIsActive] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const startJudgeMode = () => setIsActive(true);
  const stopJudgeMode = () => setIsActive(false);

  return (
    <JudgeModeContext.Provider value={{ isActive, startJudgeMode, stopJudgeMode }}>
      {children}
      {isMounted && isActive && createPortal(
        <JudgeModeOverlay onClose={stopJudgeMode} />,
        document.body
      )}
    </JudgeModeContext.Provider>
  );
}

export function useJudgeMode() {
  const context = useContext(JudgeModeContext);
  if (context === undefined) throw new Error('useJudgeMode must be used within a JudgeModeProvider');
  return context;
}

// --- Overlay Engine ---
function JudgeModeOverlay({ onClose }: { onClose: () => void }) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [progressMs, setProgressMs] = useState(0);
  const [activeSceneIdx, setActiveSceneIdx] = useState(0);
  const lastTimeRef = useRef<number>(0);
  const reqRef = useRef<number>(0);

  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying(p => !p);
      } else if (e.code === 'Escape') {
        onClose();
      } else if (e.code === 'ArrowRight') {
        const nextScene = Math.min(activeSceneIdx + 1, JUDGE_SCENES.length - 1);
        setProgressMs(JUDGE_SCENES[nextScene].startMs);
      } else if (e.code === 'ArrowLeft') {
        const prevScene = Math.max(activeSceneIdx - 1, 0);
        setProgressMs(JUDGE_SCENES[prevScene].startMs);
      } else if (e.code === 'KeyR') {
        setProgressMs(0);
        setIsPlaying(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeSceneIdx, onClose]);

  // Game loop for deterministic playback
  const tick = useCallback((time: number) => {
    if (lastTimeRef.current !== 0) {
      const delta = time - lastTimeRef.current;
      setProgressMs(prev => {
        const next = prev + delta;
        if (next >= TOTAL_DURATION_MS) {
          setIsPlaying(false);
          return TOTAL_DURATION_MS;
        }
        return next;
      });
    }
    lastTimeRef.current = time;
    if (isPlaying) {
      reqRef.current = requestAnimationFrame(tick);
    }
  }, [isPlaying]);

  useEffect(() => {
    if (isPlaying) {
      lastTimeRef.current = performance.now();
      reqRef.current = requestAnimationFrame(tick);
    } else {
      lastTimeRef.current = 0;
    }
    return () => cancelAnimationFrame(reqRef.current);
  }, [isPlaying, tick]);

  // Determine active scene based on progress
  useEffect(() => {
    const currentSceneIdx = JUDGE_SCENES.findIndex(
      scene => progressMs >= scene.startMs && progressMs < scene.endMs
    );
    if (currentSceneIdx !== -1 && currentSceneIdx !== activeSceneIdx) {
      setActiveSceneIdx(currentSceneIdx);
    } else if (progressMs >= TOTAL_DURATION_MS) {
      setActiveSceneIdx(JUDGE_SCENES.length - 1);
    }
  }, [progressMs, activeSceneIdx]);

  const activeScene = JUDGE_SCENES[activeSceneIdx];
  const progressPercent = (progressMs / TOTAL_DURATION_MS) * 100;

  return (
    <div className="fixed inset-0 z-[100] bg-[var(--background-secondary)] flex flex-col overflow-hidden animate-fade-in font-sans">
      
      {/* Top Header */}
      <header className="h-[64px] border-b border-[var(--border-subtle)] bg-white px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-3">
          <div className="w-6 h-6 rounded-md bg-[var(--primary)] flex items-center justify-center">
            <span className="text-[10px] text-white font-bold tracking-tighter">C-OS</span>
          </div>
          <span className="text-[14px] font-semibold tracking-tight text-[var(--text-primary)]">JUDGE MODE (REPLAYING VERIFIED RUN)</span>
        </div>
        <button onClick={onClose} className="p-2 hover:bg-[var(--surface-hover)] rounded-md transition-colors text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <X size={20} />
        </button>
      </header>

      {/* Main Presentation Area */}
      <main className="flex-1 relative flex items-center justify-center p-10 bg-[var(--surface-subtle)]">
        
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-5">
          <div className="w-[800px] h-[800px] border border-[var(--primary)] rounded-full border-dashed animate-[spin_60s_linear_infinite]"></div>
        </div>

        <div className="z-10 max-w-4xl text-center flex flex-col items-center">
          <div className="mb-6 px-3 py-1 bg-[var(--primary-subtle)] border border-[var(--primary-light)] text-[var(--primary)] rounded-full text-[11px] font-bold tracking-widest uppercase">
            {activeScene.title}
          </div>
          
          <h2 className="text-[48px] md:text-[64px] font-bold tracking-tight text-[var(--text-primary)] whitespace-pre-line leading-[1.1]">
            {activeScene.narrative}
          </h2>
          
          {/* Mock Visualization Data Container */}
          <div className="mt-16 w-full max-w-2xl h-[200px] bg-white border border-[var(--border-subtle)] rounded-xl shadow-lg flex items-center justify-center relative overflow-hidden">
             <div className="absolute top-3 left-3 flex space-x-1.5">
               <div className="w-2.5 h-2.5 rounded-full bg-[#EF4444]"></div>
               <div className="w-2.5 h-2.5 rounded-full bg-[#F59E0B]"></div>
               <div className="w-2.5 h-2.5 rounded-full bg-[#10B981]"></div>
             </div>
             <p className="text-[var(--text-muted)] font-mono text-[13px] tracking-widest">
               [ Visualization Render: {activeScene.id} ]
             </p>
          </div>
        </div>
      </main>

      {/* Bottom Timeline & Controls */}
      <footer className="h-[80px] bg-white border-t border-[var(--border-subtle)] flex flex-col shrink-0">
        <div className="h-1.5 w-full bg-[var(--surface-hover)] relative">
          <div className="h-full bg-[var(--primary)] transition-all duration-75 ease-linear" style={{ width: `${progressPercent}%` }}></div>
        </div>
        
        <div className="flex-1 flex items-center justify-between px-6">
          <div className="flex items-center space-x-6 text-[13px] font-mono text-[var(--text-secondary)]">
            <span>{(progressMs / 1000).toFixed(1)}s / 20.0s</span>
          </div>

          <div className="flex items-center space-x-4">
            <button onClick={() => {
              const prevScene = Math.max(activeSceneIdx - 1, 0);
              setProgressMs(JUDGE_SCENES[prevScene].startMs);
            }} className="p-2 hover:bg-[var(--surface-hover)] rounded-md text-[var(--text-primary)]">
              <SkipBack size={18} />
            </button>
            <button onClick={() => setIsPlaying(!isPlaying)} className="w-10 h-10 bg-[var(--primary)] text-white rounded-full flex items-center justify-center hover:bg-[var(--primary-hover)] shadow-sm">
              {isPlaying ? <Pause size={18} className="fill-white" /> : <Play size={18} className="fill-white ml-0.5" />}
            </button>
            <button onClick={() => {
              const nextScene = Math.min(activeSceneIdx + 1, JUDGE_SCENES.length - 1);
              setProgressMs(JUDGE_SCENES[nextScene].startMs);
            }} className="p-2 hover:bg-[var(--surface-hover)] rounded-md text-[var(--text-primary)]">
              <SkipForward size={18} />
            </button>
            <button onClick={() => {
              setProgressMs(0);
              setIsPlaying(true);
            }} className="p-2 hover:bg-[var(--surface-hover)] rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] ml-4">
              <RotateCcw size={16} />
            </button>
          </div>

          <div className="flex items-center">
            <button className="p-2 text-[var(--text-muted)] hover:text-[var(--text-primary)]">
              <VolumeX size={18} />
            </button>
          </div>
        </div>
      </footer>

    </div>
  );
}
