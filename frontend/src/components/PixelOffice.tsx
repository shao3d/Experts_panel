import React, { useRef, useEffect, useState } from 'react';
import type { ProgressEvent } from '../types/api';
import { getLatestPipelineState, getAnimMix, mixToKey } from '../utils/pipelineAnimState';
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
const CONTAINER_HEIGHT = 360;

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
  const prevMixKeyRef = useRef('');
  const staggerTimersRef = useRef<number[]>([]);
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

    // Scale canvas to fit container height (handles non-retina displays)
    let displayW = gridW / dpr;
    let displayH = gridH / dpr;
    if (displayH > CONTAINER_HEIGHT) {
      const scale = CONTAINER_HEIGHT / displayH;
      displayW = displayW * scale;
      displayH = CONTAINER_HEIGHT;
    }
    canvas.style.width = displayW + 'px';
    canvas.style.height = displayH + 'px';

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
          undefined,  // selection
          undefined,  // editor
          office.layout.tileColors ?? undefined,
          office.layout.cols,
          office.layout.rows,
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
      // First phases are always search (read) — set default tool so characters
      // don't show typing sprite while waiting for first pipeline_state SSE event
      if (isProcessing) {
        office.setAgentTool(expertToInt(id), 'Read');
      }
    }
  }, [selectedExperts, isLoaded, isProcessing]);

  // === Effect 4b: Cleanup stagger timers on unmount ===
  useEffect(() => {
    return () => {
      staggerTimersRef.current.forEach(t => clearTimeout(t));
    };
  }, []);

  // === Effect 4c: Distribute animations proportionally with stagger ===
  useEffect(() => {
    const office = officeRef.current;
    if (!office || !isProcessing) {
      prevMixKeyRef.current = '';
      staggerTimersRef.current.forEach(t => clearTimeout(t));
      staggerTimersRef.current = [];
      return;
    }

    const pipelineState = getLatestPipelineState(progressEvents);
    const mix = getAnimMix(pipelineState);

    // No active phases (brief gap between transitions) — keep previous animations
    if (mix.typeWeight === 0 && mix.readWeight === 0) return;

    // Only redistribute when the mix changes significantly (~20% buckets)
    const key = mixToKey(mix);
    if (key === prevMixKeyRef.current) return;
    prevMixKeyRef.current = key;

    // Cancel any in-flight stagger from previous mix
    staggerTimersRef.current.forEach(t => clearTimeout(t));
    staggerTimersRef.current = [];

    const experts = activeExpertsRef.current;
    const total = experts.length;
    if (total === 0) return;

    // How many characters should be typing (writing) vs reading
    const typeSlots = Math.round(mix.typeWeight * total);

    // Fisher-Yates shuffle: randomize WHO types vs reads
    const indices = Array.from({ length: total }, (_, i) => i);
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }

    // Random number of characters rotate desks (0 to total-1, skewed toward fewer)
    // Math.random()² skews toward 0 — most transitions move 0-2, occasionally more
    const rotateCount = Math.floor(Math.random() * Math.random() * total);

    // Stagger transitions so characters switch one-by-one (cascade effect)
    indices.forEach((originalIdx, order) => {
      const toolName = order < typeSlots ? 'Edit' : 'Read';
      // Wider stagger range for more organic feel: 500-1200ms between characters
      const delay = order * 500 + Math.random() * 700;

      const timer = window.setTimeout(() => {
        const agentId = expertToInt(experts[originalIdx]);
        // First N characters in shuffled order rotate to a different desk
        if (order < rotateCount) {
          office.rotateAgentSeat(agentId);
        }
        office.setAgentTool(agentId, toolName);
      }, delay);
      staggerTimersRef.current.push(timer);
    });
  }, [progressEvents, isProcessing]);

  if (loadError) return null;

  return (
    <div
      className="flex flex-col justify-center items-center bg-gray-100 rounded-lg overflow-hidden mb-4"
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
