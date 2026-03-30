import React from 'react';

type AnimState = 'walk' | 'type' | 'read' | 'idle';

interface PixelCharacterProps {
  expertName: string;
  characterIndex: number;
  animState: AnimState;
  direction: 'down' | 'right' | 'left';
  staggerIndex: number;
}

const PixelCharacter: React.FC<PixelCharacterProps> = ({
  expertName, characterIndex, animState, direction, staggerIndex,
}) => {
  const row = direction === 'down' ? 0 : 2; // row 2 = right; left uses row 2 + scaleX flip
  const isLeft = direction === 'left';
  const jitter = (staggerIndex * 7) % 12 - 6; // -6..+5px vertical offset

  return (
    <div
      className="pixel-char-wrapper flex flex-col items-center"
      style={{
        marginTop: `${jitter}px`,
        animationDelay: `${staggerIndex * 60}ms`,
      }}
    >
      <div
        className={`pixel-char anim-${animState}${isLeft ? ' face-left' : ''}`}
        data-row={row}
        style={{
          backgroundImage: `url('/sprites/char_${characterIndex}.png')`,
          animationDelay: `${-(staggerIndex * 100)}ms`,
        }}
      />
      <span className="text-[10px] text-gray-500 text-center truncate block max-w-[72px] mt-0.5">
        {expertName}
      </span>
    </div>
  );
};

export default PixelCharacter;
