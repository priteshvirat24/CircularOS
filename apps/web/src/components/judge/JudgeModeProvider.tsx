"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Play, Pause, SkipBack, SkipForward, X, RotateCcw, ShieldAlert, GitCommit, Database, Activity, Cpu } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';

// --- Types ---
export type JudgeSceneDefinition = {
  id: string;
  startMs: number;
  endMs: number;
  title: string;
  narrative: string;
};

// 25 Second choreography (25000ms total) - slightly longer for better pacing
export const JUDGE_SCENES: JudgeSceneDefinition[] = [
  { id: 'scene-1', startMs: 0, endMs: 3500, title: 'THE HOOK', narrative: "A 200-PAGE REGULATION JUST DROPPED.\nYOUR ENTIRE COMPLIANCE SYSTEM IS OUT OF DATE." },
  { id: 'scene-2', startMs: 3500, endMs: 7000, title: 'DOCUMENT TO STRUCTURE', narrative: "WE DON'T JUST READ PDFs.\nWE DECONSTRUCT THEM INTO A KNOWLEDGE GRAPH." },
  { id: 'scene-3', startMs: 7000, endMs: 11000, title: 'AGENTIC EXTRACTION', narrative: "AI PROPOSES.\nVALIDATORS VERIFY.\nCRITICS TRY TO BREAK IT." },
  { id: 'scene-4', startMs: 11000, endMs: 14500, title: 'PROVENANCE', narrative: "EVERY EXTRACTED OBLIGATION.\nTIED EXACTLY TO THE SOURCE CLAUSE." },
  { id: 'scene-5', startMs: 14500, endMs: 18000, title: 'REGULATORY DIFF', narrative: "KNOW EXACTLY WHAT CHANGED.\nDOWN TO THE SEMANTIC MEANING." },
  { id: 'scene-6', startMs: 18000, endMs: 21500, title: 'OPERATIONAL IMPACT', narrative: "ONE REGULATORY SHIFT.\nEVERY AFFECTED CONTROL AUTOMATICALLY FLAGGED." },
  { id: 'scene-7', startMs: 21500, endMs: 25000, title: 'SUPTECH MIRROR', narrative: "REGULATORS DON'T JUST GET REPORTS.\nTHEY GET A LIVE VIEW OF IMPLEMENTATION." },
];

const TOTAL_DURATION_MS = 25000;

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

// --- Cinematic Overlay Engine ---
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
    <div className="fixed inset-0 z-[100] bg-[#05050A] flex flex-col overflow-hidden font-sans text-white">
      
      {/* Cinematic Top Bar */}
      <header className="h-[72px] flex items-center justify-between px-8 shrink-0 relative z-50">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--primary)] flex items-center justify-center">
            <ShieldAlert size={18} className="text-white" />
          </div>
          <span className="text-[14px] font-bold tracking-[0.2em] text-white/90 uppercase">CircularOS <span className="text-white/40 font-normal">/</span> JUDGE MODE</span>
        </div>
        <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors text-white/60 hover:text-white">
          <X size={24} />
        </button>
      </header>

      {/* Main Presentation Area */}
      <main className="flex-1 relative flex items-center justify-center overflow-hidden">
        
        {/* Background Ambience */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
          <div className="w-[1000px] h-[1000px] bg-[var(--primary)] blur-[150px] rounded-full opacity-30 mix-blend-screen animate-pulse"></div>
        </div>

        <div className="z-10 w-full max-w-6xl px-12 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          
          {/* Left: Narrative */}
          <div className="flex flex-col items-start text-left">
            <motion.div 
              key={`${activeScene.id}-badge`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className="mb-8 px-4 py-1.5 bg-[var(--primary)]/20 border border-[var(--primary)]/50 text-[var(--primary-light)] rounded-full text-[11px] font-bold tracking-[0.3em] uppercase backdrop-blur-md"
            >
              {activeScene.title}
            </motion.div>
            
            <AnimatePresence mode="wait">
              <motion.h2 
                key={activeScene.id}
                initial={{ opacity: 0, y: 20, filter: "blur(10px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: -20, filter: "blur(10px)" }}
                transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                className="text-[48px] md:text-[56px] font-bold tracking-tight text-white whitespace-pre-line leading-[1.1] drop-shadow-2xl"
              >
                {activeScene.narrative}
              </motion.h2>
            </AnimatePresence>
          </div>
          
          {/* Right: Dynamic Cinematic Visualization */}
          <div className="relative h-[400px] w-full flex items-center justify-center">
            <AnimatePresence mode="wait">
              <SceneVisualizer key={activeScene.id} sceneId={activeScene.id} />
            </AnimatePresence>
          </div>

        </div>
      </main>

      {/* Bottom Timeline & Controls */}
      <footer className="h-[90px] flex flex-col shrink-0 relative z-50">
        <div className="h-1 w-full bg-white/10 relative">
          <div className="h-full bg-[var(--primary)] shadow-[0_0_10px_var(--primary)] transition-all duration-75 ease-linear" style={{ width: `${progressPercent}%` }}></div>
        </div>
        
        <div className="flex-1 flex items-center justify-between px-8 bg-black/50 backdrop-blur-md">
          <div className="flex items-center space-x-6 text-[13px] font-mono text-white/60 tracking-widest">
            <span>{(progressMs / 1000).toFixed(1)}s / {(TOTAL_DURATION_MS / 1000).toFixed(1)}s</span>
          </div>

          <div className="flex items-center space-x-6">
            <button onClick={() => {
              const prevScene = Math.max(activeSceneIdx - 1, 0);
              setProgressMs(JUDGE_SCENES[prevScene].startMs);
            }} className="p-2 hover:bg-white/10 rounded-full text-white/80 transition-colors">
              <SkipBack size={20} />
            </button>
            <button onClick={() => setIsPlaying(!isPlaying)} className="w-14 h-14 bg-white text-black rounded-full flex items-center justify-center hover:scale-105 transition-transform shadow-[0_0_20px_rgba(255,255,255,0.3)]">
              {isPlaying ? <Pause size={24} className="fill-black" /> : <Play size={24} className="fill-black ml-1" />}
            </button>
            <button onClick={() => {
              const nextScene = Math.min(activeSceneIdx + 1, JUDGE_SCENES.length - 1);
              setProgressMs(JUDGE_SCENES[nextScene].startMs);
            }} className="p-2 hover:bg-white/10 rounded-full text-white/80 transition-colors">
              <SkipForward size={20} />
            </button>
            <button onClick={() => {
              setProgressMs(0);
              setIsPlaying(true);
            }} className="p-2 hover:bg-white/10 rounded-full text-white/50 hover:text-white transition-colors ml-4">
              <RotateCcw size={18} />
            </button>
          </div>

          <div className="w-[120px] flex justify-end">
             <div className="flex space-x-1 items-end h-4 opacity-50">
               {[1,2,3,4,5].map(i => (
                 <div key={i} className="w-1 bg-white rounded-t-sm" style={{ height: `${Math.random() * 100}%` }}></div>
               ))}
             </div>
          </div>
        </div>
      </footer>

    </div>
  );
}

// --- Cinematic Visualizations for Each Scene ---
function SceneVisualizer({ sceneId }: { sceneId: string }) {
  switch (sceneId) {
    case 'scene-1':
      return (
        <motion.div 
          initial={{ opacity: 0, scale: 0.9, rotateY: 15 }}
          animate={{ opacity: 1, scale: 1, rotateY: 0 }}
          exit={{ opacity: 0, scale: 1.1, filter: "blur(10px)" }}
          transition={{ duration: 0.8 }}
          className="w-3/4 aspect-[1/1.2] bg-white rounded-lg shadow-[0_0_50px_rgba(255,255,255,0.1)] p-6 flex flex-col space-y-4 overflow-hidden relative"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/80 z-10"></div>
          <div className="w-1/2 h-4 bg-gray-200 rounded"></div>
          <div className="w-full h-2 bg-gray-100 rounded mt-4"></div>
          <div className="w-full h-2 bg-gray-100 rounded"></div>
          <div className="w-3/4 h-2 bg-gray-100 rounded"></div>
          <div className="w-full h-32 bg-red-500/20 border border-red-500/50 rounded flex items-center justify-center mt-8">
            <span className="text-red-600 font-bold tracking-widest text-[10px] uppercase">New Mandate Detected</span>
          </div>
          {[...Array(10)].map((_, i) => (
             <div key={i} className="w-full h-2 bg-gray-100 rounded"></div>
          ))}
        </motion.div>
      );
    case 'scene-2':
      return (
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="w-full h-full flex items-center justify-center relative"
        >
          <Database size={64} className="text-[var(--primary)] absolute top-0" />
          <motion.div 
             initial={{ height: 0 }} 
             animate={{ height: 100 }} 
             transition={{ duration: 1, delay: 0.5 }}
             className="w-0.5 bg-[var(--primary)]/50 absolute top-16"
          ></motion.div>
          <div className="absolute top-40 flex space-x-12">
            {[1,2,3].map((i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.8 + (i * 0.2) }}
                className="w-24 h-24 bg-white/5 border border-white/20 rounded-xl flex flex-col items-center justify-center p-4 backdrop-blur-md"
              >
                <div className="w-8 h-2 bg-[var(--primary)]/50 rounded mb-2"></div>
                <div className="w-full h-1 bg-white/20 rounded mb-1"></div>
                <div className="w-3/4 h-1 bg-white/20 rounded"></div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      );
    case 'scene-3':
      return (
        <motion.div 
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 1.2 }}
          className="w-full h-full flex items-center justify-center relative"
        >
          <div className="absolute w-[300px] h-[300px] border border-white/10 rounded-full animate-[spin_10s_linear_infinite]"></div>
          <div className="absolute w-[200px] h-[200px] border border-[var(--primary)]/30 rounded-full animate-[spin_5s_linear_infinite_reverse]"></div>
          
          <div className="w-20 h-20 bg-[var(--primary)] rounded-full flex items-center justify-center shadow-[0_0_40px_var(--primary)] z-10 relative">
            <Cpu size={32} className="text-white" />
            
            {/* Orbiting Agents */}
            {[0, 120, 240].map((deg, i) => (
              <motion.div
                key={i}
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                className="absolute inset-[-100px]"
                style={{ originX: 0.5, originY: 0.5, rotate: deg }}
              >
                <div className="absolute top-0 left-1/2 w-8 h-8 -ml-4 bg-white text-[var(--primary)] rounded-full shadow-[0_0_20px_white] flex items-center justify-center">
                  <Activity size={14} />
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      );
    case 'scene-4':
      return (
        <motion.div 
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -50 }}
          className="w-full h-full flex items-center justify-center"
        >
          <div className="flex space-x-8 items-center w-full">
            <div className="flex-1 bg-white/5 border border-white/10 rounded-xl p-6 relative">
              <p className="text-white/40 text-[10px] uppercase tracking-widest mb-4">Source PDF</p>
              <div className="w-full h-2 bg-white/10 rounded mb-2"></div>
              <div className="w-full h-2 bg-white/10 rounded mb-2"></div>
              <div className="w-3/4 h-2 bg-[var(--primary)]/60 rounded mb-2 shadow-[0_0_10px_var(--primary)]"></div>
              <div className="w-full h-2 bg-white/10 rounded mb-2"></div>
            </div>
            
            <div className="w-16 h-0.5 bg-gradient-to-r from-[var(--primary)] to-white relative">
              <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 bg-white rounded-full shadow-[0_0_10px_white]"></div>
            </div>

            <div className="flex-1 bg-[var(--primary)]/10 border border-[var(--primary)]/50 rounded-xl p-6 shadow-[0_0_30px_rgba(99,91,255,0.2)]">
              <p className="text-[var(--primary-light)] text-[10px] uppercase tracking-widest mb-4 font-bold">Extracted Obligation</p>
              <div className="font-mono text-[11px] text-white/80 space-y-2">
                <p><span className="text-[var(--primary)]">"actor":</span> "Clearing Member",</p>
                <p><span className="text-[var(--primary)]">"action":</span> "Report shortfalls",</p>
                <p><span className="text-[var(--primary)]">"citation":</span> "Page 4, Para 2"</p>
              </div>
            </div>
          </div>
        </motion.div>
      );
    case 'scene-5':
      return (
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="w-full h-full flex flex-col justify-center space-y-4"
        >
          <div className="bg-red-500/10 border border-red-500/30 p-4 rounded-lg flex items-center space-x-4">
            <div className="w-4 h-4 bg-red-500/20 rounded flex items-center justify-center shrink-0">
              <span className="text-red-500 font-bold text-xs">-</span>
            </div>
            <p className="text-red-500/70 text-[13px] font-mono line-through">Deadline: T+2 days</p>
          </div>
          <div className="bg-green-500/10 border border-green-500/30 p-4 rounded-lg flex items-center space-x-4 shadow-[0_0_20px_rgba(16,185,129,0.1)]">
            <div className="w-4 h-4 bg-green-500/20 rounded flex items-center justify-center shrink-0">
              <span className="text-green-500 font-bold text-xs">+</span>
            </div>
            <p className="text-green-400 text-[13px] font-mono">Deadline: T+1 day (Accelerated)</p>
          </div>
        </motion.div>
      );
    case 'scene-6':
      return (
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          className="w-full h-full flex items-center justify-center relative"
        >
          <GitCommit size={48} className="text-red-500 absolute top-1/4 left-1/4" />
          
          <motion.div 
             initial={{ width: 0 }} 
             animate={{ width: 120 }} 
             transition={{ duration: 0.5, delay: 0.3 }}
             className="h-0.5 bg-gradient-to-r from-red-500 to-yellow-500 absolute top-[30%] left-[30%]"
             style={{ transformOrigin: 'left center', rotate: '30deg' }}
          ></motion.div>

          <div className="w-16 h-16 bg-yellow-500/20 border border-yellow-500/50 rounded-full flex items-center justify-center absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 shadow-[0_0_30px_rgba(234,179,8,0.3)]">
            <ShieldAlert className="text-yellow-500" size={24} />
          </div>

          <motion.div 
             initial={{ opacity: 0 }} 
             animate={{ opacity: 1 }} 
             transition={{ delay: 0.8 }}
             className="absolute top-[65%] left-1/2 -translate-x-1/2 bg-yellow-500/10 border border-yellow-500/30 text-yellow-500 px-4 py-2 rounded-lg text-[11px] uppercase tracking-widest font-bold"
          >
            Control 4B: Review Required
          </motion.div>
        </motion.div>
      );
    case 'scene-7':
      return (
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, filter: "blur(10px)" }}
          className="w-full h-full bg-white/5 border border-white/10 rounded-2xl p-6 flex flex-col"
        >
          <div className="flex justify-between items-center mb-8 border-b border-white/10 pb-4">
            <div className="text-[10px] text-white/40 uppercase tracking-widest">Systemic Risk Dashboard</div>
            <div className="flex space-x-2">
              <div className="w-2 h-2 rounded-full bg-green-500"></div>
              <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
            </div>
          </div>
          <div className="flex-1 flex items-end space-x-2">
             {[30, 45, 25, 60, 40, 80, 55, 90, 75, 100].map((h, i) => (
               <motion.div 
                 key={i}
                 initial={{ height: 0 }}
                 animate={{ height: `${h}%` }}
                 transition={{ duration: 0.5, delay: i * 0.1 }}
                 className={cn(
                   "flex-1 rounded-t-sm",
                   h > 70 ? "bg-[var(--primary)] shadow-[0_0_15px_var(--primary)]" : "bg-white/20"
                 )}
               ></motion.div>
             ))}
          </div>
        </motion.div>
      );
    default:
      return null;
  }
}
