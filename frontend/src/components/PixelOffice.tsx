import React, { useRef, useEffect, useState } from 'react';
import type { ProgressEvent } from '../types/api';
import { getLatestPipelineState, getAnimState, animStateToToolName } from '../utils/pipelineAnimState';
import { initializeOffice } from '../pixel-office/browserAssetLoader';
import { startGameLoop } from '../pixel-office/engine/gameLoop';
import { renderFrame } from '../pixel-office/engine/renderer';
import type { OfficeState } from '../pixel-office/engine/officeState';

interface PixelOfficeProps {
  selectedExperts: Set<string>;
  progressEvents: ProgressEvent[];
  isProcessing: boolean;
}

const MAX_CHARACTERS = 10;
const ASSET_BASE_PATH = '/pixel-office';
const CONTAINER_HEIGHT = 300;

// Map string expert ID to stable integer ID (needed by engine API)
function expertToInt(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) % 100000;
}

const PixelOffice: React.FC<PixelOfficeProps> = ({
  selectedExperts, progressEvents, isProcessing,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const officeRef = useRef<OfficeState | null>(null);
  const activeExpertsRef = useRef<string[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  // === Effect 1: Load engine (once) ===
  useEffect(() => {
    let cancelled = false;

    initializeOffice(ASSET_BASE_PATH)
      .then((office) => {
        if (cancelled) return;
        officeRef.current = office;
        setIsLoaded(true);
      })
      .catch((err) => {
        console.error('[PixelOffice] Failed to initialize:', err);
        if (!cancelled) setLoadError(true);
      });

    return () => { cancelled = true; };
  }, []);

  // === Effect 2: Game loop (starts when loaded) ===
  useEffect(() => {
    if (!isLoaded || !canvasRef.current || !officeRef.current) return;

    const canvas = canvasRef.current;
    const office = officeRef.current;
    const dpr = window.devicePixelRatio || 1;
    // Minimum 3x zoom for crisp pixel art on all displays
    const zoom = Math.max(3, Math.floor(dpr) + 1);

    const gridW = office.layout.cols * 16 * zoom;
    const gridH = office.layout.rows * 16 * zoom;
    canvas.width = gridW;
    canvas.height = gridH;
    canvas.style.width = (gridW / dpr) + 'px';
    canvas.style.height = (gridH / dpr) + 'px';

    const stopLoop = startGameLoop(canvas, {
      update: (dt: number) => office.update(dt),
      render: (ctx: CanvasRenderingContext2D) => {
        renderFrame(
          ctx,
          canvas.width,
          canvas.height,
          office.tileMap,
          office.furniture,
          Array.from(office.characters.values()),
          zoom,
          0,
          0,
        );
      },
    });

    return () => {
      stopLoop();
    };
  }, [isLoaded]);

  // === Effect 3: Sync experts → characters + activate/deactivate ===
  useEffect(() => {
    const office = officeRef.current;
    if (!office) return;

    const desired = Array.from(selectedExperts).slice(0, MAX_CHARACTERS);
    const current = activeExpertsRef.current;

    for (const id of current) {
      if (!desired.includes(id)) office.removeAgent(expertToInt(id));
    }
    for (const id of desired) {
      if (!current.includes(id)) office.addAgent(expertToInt(id));
    }

    activeExpertsRef.current = desired;

    for (const id of desired) {
      office.setAgentActive(expertToInt(id), isProcessing);
    }
  }, [selectedExperts, isLoaded, isProcessing]);

  // === Effect 4b: Sync tool type on pipeline events ===
  useEffect(() => {
    const office = officeRef.current;
    if (!office || !isProcessing) return;

    const pipelineState = getLatestPipelineState(progressEvents);
    const animState = getAnimState(pipelineState);
    const toolName = animStateToToolName(animState);

    for (const id of activeExpertsRef.current) {
      office.setAgentTool(expertToInt(id), toolName);
    }
  }, [progressEvents, isProcessing]);

  if (loadError) return null;

  return (
    <div
      className="flex flex-col justify-end items-center bg-gray-100 rounded-lg overflow-hidden mb-4"
      style={{ height: CONTAINER_HEIGHT }}
    >
      {isLoaded ? (
        <canvas
          ref={canvasRef}
          style={{ imageRendering: 'pixelated', display: 'block' }}
        />
      ) : (
        <div className="flex items-center justify-center w-full h-full text-gray-400 text-sm">
          Loading office...
        </div>
      )}
    </div>
  );
};

export default PixelOffice;
