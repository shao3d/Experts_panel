import React, { useState } from 'react';
import type { ProgressEvent } from '../types/api';
import { getLatestPipelineState, getAnimMix, type AnimState } from '../utils/pipelineAnimState';
import PixelCharacter from './PixelCharacter';

interface PixelMascotProps {
  progressEvents: ProgressEvent[];
  isProcessing: boolean;
}

const PixelMascot: React.FC<PixelMascotProps> = ({ progressEvents, isProcessing }) => {
  const [charIndex] = useState(() => Math.floor(Math.random() * 6));

  let animState: AnimState = 'idle';
  if (isProcessing) {
    const pipelineState = getLatestPipelineState(progressEvents);
    const mix = getAnimMix(pipelineState);
    // Single mascot: pick dominant animation
    if (mix.typeWeight > 0 || mix.readWeight > 0) {
      animState = mix.typeWeight >= mix.readWeight ? 'type' : 'read';
    }
  }

  return (
    <div className="flex flex-col items-center py-6">
      <PixelCharacter
        expertName=""
        characterIndex={charIndex}
        animState={animState}
        direction="down"
        staggerIndex={0}
      />
      <span className="text-xs text-gray-400 mt-2">
        {isProcessing ? 'Эксперты думают...' : 'Задайте вопрос'}
      </span>
    </div>
  );
};

export default PixelMascot;
