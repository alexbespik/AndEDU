import React from 'react';
import { Volume2, VolumeX, X } from 'lucide-react';
import { useCommissar, setMuted, setEnabled, activePack } from '../lib/commissar';

/** Shown in the masthead only while Commissar mode is on. */
export default function CommissarChip() {
  const st = useCommissar();
  const { enabled, muted } = st;
  const pack = activePack(st);
  if (!enabled) return null;
  return (
    <span className="commissar-chip" role="group" aria-label="Commissar mode" title={pack ? `Commissar mode · voice: ${pack.name}` : 'Commissar mode'}>
      {/* one short label: the voice's name when a pack plays, so a long pack name can't stretch the masthead */}
      <span className="commissar-chip-label">{pack ? pack.name : 'Commissar mode'}</span>
      <button type="button" onClick={() => setMuted(!muted)} aria-label={muted ? 'Unmute Commissar voice' : 'Mute Commissar voice'} aria-pressed={muted}>
        {muted ? <VolumeX size={14} aria-hidden="true" /> : <Volume2 size={14} aria-hidden="true" />}
      </button>
      <button type="button" onClick={() => setEnabled(false)} aria-label="Turn off Commissar mode">
        <X size={14} aria-hidden="true" />
      </button>
    </span>
  );
}
