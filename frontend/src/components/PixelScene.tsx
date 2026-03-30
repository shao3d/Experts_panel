import React from 'react';
import { ProgressEvent } from '../types/api';
import { getExpertDisplayName } from '../config/expertConfig';
import PixelCharacter from './PixelCharacter';
import './PixelScene.css';

type AnimState = 'walk' | 'type' | 'read';

interface PixelSceneProps {
  selectedExperts: Set<string>;
  progressEvents: ProgressEvent[];
  isProcessing: boolean;
}

const TYPE_PHASES = [
  'video_map', 'video_resolve', 'video_synthesis', 'video_validation',
  'meta_synthesis', 'reddit_search', 'reddit_synthesis',
];
const READ_PHASES = [
  'resolve', 'reduce', 'language_validation',
  'comment_groups', 'comment_synthesis',
];

function getCharacterIndex(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) % 6;
}

type PhaseStatus = 'pending' | 'active' | 'completed' | 'skipped' | 'error';

function getLatestPipelineState(
  events: ProgressEvent[],
): Record<string, PhaseStatus> | null {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].pipeline_state) return events[i].pipeline_state as Record<string, PhaseStatus>;
  }
  return null;
}

function getAnimState(state: Record<string, PhaseStatus> | null): AnimState {
  if (!state) return 'walk';
  const active = Object.entries(state)
    .filter(([, s]) => s === 'active')
    .map(([p]) => p);
  if (active.length === 0) return 'walk';
  if (active.some(p => TYPE_PHASES.includes(p))) return 'type';
  if (active.some(p => READ_PHASES.includes(p))) return 'read';
  return 'walk';
}

const PixelScene: React.FC<PixelSceneProps> = ({
  selectedExperts, progressEvents, isProcessing,
}) => {
  const pipelineState = getLatestPipelineState(progressEvents);
  const animState = getAnimState(pipelineState);
  const expertsArray = Array.from(selectedExperts);

  return (
    <div className="flex flex-col items-center justify-center min-h-[200px] py-8">
      {expertsArray.length > 0 ? (
        <div className="flex flex-wrap justify-center gap-1 md:gap-3 px-4">
          {expertsArray.map((expertId, index) => (
            <PixelCharacter
              key={expertId}
              expertName={getExpertDisplayName(expertId)}
              characterIndex={getCharacterIndex(expertId)}
              animState={animState}
              direction={animState === 'walk' ? (index % 2 === 0 ? 'right' : 'left') : 'down'}
              staggerIndex={index}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400">Выберите экспертов в боковой панели</p>
      )}
      {!isProcessing && expertsArray.length > 0 && (
        <p className="text-xs text-gray-400 mt-4">Задайте вопрос — эксперты начнут работу</p>
      )}
    </div>
  );
};

export default PixelScene;
