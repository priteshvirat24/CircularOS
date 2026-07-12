"use client";

import React, { useRef, useState, useMemo, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Line, Html, Environment, ContactShadows } from '@react-three/drei';
import * as THREE from 'three';

// Data structure for the layers
const LAYERS = [
  { id: 'source', label: 'SOURCE CIRCULAR', z: 3, color: '#ffffff', opacity: 0.9 },
  { id: 'clause', label: 'CLAUSE GRAPH', z: 1.5, color: '#f0f0f5', opacity: 0.7 },
  { id: 'obligation', label: 'OBLIGATION REGISTRY', z: 0, color: '#635BFF', opacity: 1, isCore: true },
  { id: 'control', label: 'CONTROL MAP', z: -1.5, color: '#f0f0f5', opacity: 0.7 },
  { id: 'evidence', label: 'EVIDENCE LEDGER', z: -3, color: '#ffffff', opacity: 0.9 },
];

function ArchitectureSlab({ 
  position, 
  color, 
  opacity, 
  isCore, 
  isActive, 
  label, 
  onHover 
}: any) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  // Parallax and gentle rotation
  useFrame((state) => {
    if (meshRef.current) {
      // Very slow idle rotation
      meshRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.2) * 0.05;
      meshRef.current.rotation.x = Math.cos(state.clock.elapsedTime * 0.2) * 0.05;
    }
  });

  return (
    <group position={position}>
      <Float speed={1.5} rotationIntensity={0.1} floatIntensity={0.5}>
        <mesh 
          ref={meshRef} 
          onPointerOver={() => onHover(true)} 
          onPointerOut={() => onHover(false)}
        >
          {isCore ? (
            <octahedronGeometry args={[1, 0]} />
          ) : (
            <boxGeometry args={[3, 4, 0.05]} />
          )}
          <meshStandardMaterial 
            color={isActive ? '#635BFF' : color} 
            transparent 
            opacity={isActive ? 0.9 : opacity}
            roughness={0.2}
            metalness={0.1}
          />
        </mesh>
        
        {/* Connection lines simulating the graph logic */}
        {!isCore && (
          <Line 
            points={[[0, 0, 0], [0, 0, position[2] > 0 ? -1.5 : 1.5]]} 
            color={isActive ? '#635BFF' : '#DED9E8'} 
            lineWidth={isActive ? 2 : 1}
            transparent
            opacity={0.5}
          />
        )}
        
        {/* Label (visible on hover) */}
        {isActive && (
          <Html position={[1.8, 2, 0]} center>
            <div className="bg-white border border-[var(--primary-light)] px-3 py-1.5 rounded shadow-lg text-[10px] font-bold tracking-widest text-[var(--primary)] whitespace-nowrap uppercase pointer-events-none transition-all animate-fade-in">
              {label}
            </div>
          </Html>
        )}
      </Float>
    </group>
  );
}

function SupTechRing({ isActive }: { isActive: boolean }) {
  const ringRef = useRef<THREE.Mesh>(null);
  
  useFrame((state) => {
    if (ringRef.current) {
      ringRef.current.rotation.z = state.clock.elapsedTime * -0.1;
      ringRef.current.rotation.x = Math.PI / 2 + Math.sin(state.clock.elapsedTime * 0.5) * 0.1;
    }
  });

  return (
    <mesh ref={ringRef} position={[0, 0, 0]}>
      <torusGeometry args={[3.5, 0.02, 16, 100]} />
      <meshStandardMaterial 
        color={isActive ? '#635BFF' : '#DED9E8'} 
        transparent 
        opacity={0.6}
      />
      {isActive && (
        <Html position={[3.6, 0, 0]} center>
          <div className="bg-white border border-[var(--primary-light)] px-3 py-1.5 rounded shadow-lg text-[10px] font-bold tracking-widest text-[var(--primary)] whitespace-nowrap uppercase pointer-events-none animate-fade-in">
            SUPTECH MIRROR
          </div>
        </Html>
      )}
    </mesh>
  );
}

function Scene() {
  const [activeLayer, setActiveLayer] = useState<string | null>(null);

  // Group parallax based on pointer
  const groupRef = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = THREE.MathUtils.lerp(groupRef.current.rotation.y, (state.pointer.x * Math.PI) / 8, 0.05);
      groupRef.current.rotation.x = THREE.MathUtils.lerp(groupRef.current.rotation.x, (state.pointer.y * Math.PI) / 16, 0.05);
    }
  });

  return (
    <group ref={groupRef} rotation={[0, -Math.PI / 6, 0]}>
      {LAYERS.map((layer) => (
        <ArchitectureSlab
          key={layer.id}
          position={[0, 0, layer.z]}
          color={layer.color}
          opacity={layer.opacity}
          isCore={layer.isCore}
          label={layer.label}
          isActive={activeLayer === layer.id || activeLayer === 'all'}
          onHover={(hovering: boolean) => setActiveLayer(hovering ? layer.id : null)}
        />
      ))}
      
      {/* Outer SupTech Ring */}
      <mesh onPointerOver={() => setActiveLayer('suptech')} onPointerOut={() => setActiveLayer(null)}>
        <cylinderGeometry args={[4, 4, 10, 32, 1, true]} />
        <meshBasicMaterial transparent opacity={0} side={THREE.BackSide} />
      </mesh>
      
      <SupTechRing isActive={activeLayer === 'suptech'} />
    </group>
  );
}

export default function RegulatoryCore3D() {
  return (
    <div className="w-full h-full relative">
      <Canvas
        camera={{ position: [5, 2, 8], fov: 45 }}
        dpr={[1, 2]} // Cap pixel ratio for performance
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} color="#ffffff" />
        <pointLight position={[-10, -10, -10]} intensity={0.5} color="#635BFF" />
        
        <Suspense fallback={null}>
          <Scene />
          <Environment preset="city" />
          <ContactShadows position={[0, -3.5, 0]} opacity={0.4} scale={10} blur={2} far={4} resolution={256} color="#635BFF" />
        </Suspense>
      </Canvas>
    </div>
  );
}
