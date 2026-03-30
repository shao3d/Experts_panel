import React, { useState } from 'react';
import type { ProgressEvent } from '../types/api';
import { getLatestPipelineState, getAnimState, type AnimState } from '../utils/pipelineAnimState';
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
    const raw = getAnimState(pipelineState);
    animState = raw === 'walk' ? 'idle' : raw;
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
